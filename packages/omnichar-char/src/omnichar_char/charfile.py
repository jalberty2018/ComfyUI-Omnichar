# SPDX-License-Identifier: Apache-2.0
"""The ``.char`` container, extracted from Omnichar Studio; the layout is in docs/char-format.md."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import limits

#: A reader refuses anything above this rather than half-loading the wrong face.
FORMAT_VERSION = 1

MAGIC = "INLINECHAR"

#: Valid JSON *and* a signature, so a file is identifiable from 32 bytes without parsing.
SIGNATURE = f'{{"magic":"{MAGIC}","format_version":'.encode()

MANIFEST_NAME = "manifest.json"

#: Fixed so the signature lands at byte 0 and two writes produce identical bytes.
_KEY_ORDER = (
    "magic", "format_version", "char_id", "name", "created_at", "modified_at", "app",
    "app_version", "refs", "derived", "text", "payloads", "scoring", "hints", "apply", "reserved",
)


#: Nested inside `refs`: a new top-level key is destroyed by any older build that rewrites a file.
ORIGIN_ORIGINAL: str = "original"
ORIGIN_HARVESTED: str = "harvested"

#: Absent means face, so a character written before roles existed behaves as it did.
ROLE_FACE: str = "face"
ROLE_BODY: str = "body"
ROLE_CLOTH: str = "cloth"
ROLES: tuple[str, ...] = (ROLE_FACE, ROLE_BODY, ROLE_CLOTH)

#: What a payload is, not which model it targets; one arch can carry both kinds.
PAYLOAD_REF: str = "ref"
PAYLOAD_LORA: str = "lora"


class CharError(Exception):
    """A ``.char`` that cannot be trusted. The message is shown to the user."""


#: Omnichar Studio's name for the same error, kept so its call sites read unchanged.
CharFileError = CharError


class CharChanged(CharError):
    """The file changed underneath an open character, so its members no longer agree."""


def origin_of(ref: dict[str, Any]) -> str:
    """Absent means original: every reference written before harvesting existed is one."""
    return str(ref.get("origin") or ORIGIN_ORIGINAL)


def role_of(ref: dict[str, Any]) -> str:
    """A reference's role. An unknown value reads as face rather than failing the whole open."""
    role = str(ref.get("role") or ROLE_FACE)
    return role if role in ROLES else ROLE_FACE


def by_role(refs: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    """The references carrying one role, in manifest order."""
    return [ref for ref in refs if role_of(ref) == role]


def payload_key(arch: str, kind: str = PAYLOAD_REF) -> str:
    """Where a payload lives. A reference set keeps the bare arch key, so v1 files stay valid."""
    return arch if kind == PAYLOAD_REF else f"{arch}-{kind}"


@dataclass
class Manifest:
    char_id: str
    name: str
    created_at: int
    modified_at: int
    app_version: str = ""
    refs: list[dict[str, Any]] = field(default_factory=list)
    derived: list[dict[str, Any]] = field(default_factory=list)
    text: dict[str, Any] = field(default_factory=dict)
    payloads: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    hints: list[str] = field(default_factory=list)
    #: Read-only: `to_json` emits FORMAT_VERSION, since a writer declares what it wrote.
    format_version: int = FORMAT_VERSION
    #: arch -> "reference" | "lora". Absent is resolved at apply time, so an older file migrates.
    apply: dict[str, str] = field(default_factory=dict)
    reserved: dict[str, Any] = field(
        default_factory=lambda: {"adapters": {}, "video_payloads": {}, "members": []}
    )

    def to_json(self) -> dict[str, Any]:
        return {
            "magic": MAGIC,
            "format_version": FORMAT_VERSION,
            "char_id": self.char_id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "app": "inline-studio",
            "app_version": self.app_version,
            "refs": self.refs,
            "derived": self.derived,
            "text": self.text,
            "payloads": self.payloads,
            "scoring": self.scoring,
            "hints": self.hints,
            "apply": self.apply,
            "reserved": self.reserved,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Manifest:
        return cls(
            char_id=str(raw.get("char_id", "")),
            name=str(raw.get("name", "")),
            created_at=int(raw.get("created_at", 0)),
            modified_at=int(raw.get("modified_at", 0)),
            app_version=str(raw.get("app_version", "")),
            refs=list(raw.get("refs") or []),
            derived=list(raw.get("derived") or []),
            text=dict(raw.get("text") or {}),
            payloads=dict(raw.get("payloads") or {}),
            scoring=dict(raw.get("scoring") or {}),
            hints=list(raw.get("hints") or []),
            format_version=int(raw.get("format_version", FORMAT_VERSION)),
            apply={str(k): str(v) for k, v in (raw.get("apply") or {}).items()},
            reserved=dict(raw.get("reserved") or {}),
        )


@dataclass
class CharDoc:
    """A whole character in memory: the manifest plus every member's bytes."""

    manifest: Manifest
    members: dict[str, bytes] = field(default_factory=dict)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def member_name(prefix: str, index: int, suffix: str) -> str:
    """``refs/000.png`` - always ASCII, since a user's filename may not extract on Windows."""
    return f"{prefix}/{index:03d}{suffix}"


def dumps_manifest(manifest: Manifest) -> bytes:
    """Manifest bytes with the signature at byte 0."""
    raw = manifest.to_json()
    ordered = {key: raw[key] for key in _KEY_ORDER if key in raw}
    data = json.dumps(ordered, ensure_ascii=True, separators=(",", ":")).encode()
    if not data.startswith(SIGNATURE):
        raise CharError(
            "The manifest was serialised with the wrong key order, so its signature is no longer "
            "at byte 0. Manifest.to_json and _KEY_ORDER have to agree."
        )
    return data


def looks_like_char(data: bytes) -> bool:
    """Whether a manifest blob carries our signature. Cheap enough for an upload gate."""
    return data.startswith(SIGNATURE)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    """Unix mode lives in the top 16 bits of `external_attr`, and is 0 on a Windows-written zip."""
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def check_archive(archive: zipfile.ZipFile, label: str) -> None:
    """Refuse a hostile archive from its central directory alone, before any member is read."""
    infos = [i for i in archive.infolist() if not i.is_dir()]
    if len(infos) > limits.MAX_MEMBERS:
        raise CharError(
            f"{label} holds {len(infos)} files, and a character file may hold "
            f"{limits.MAX_MEMBERS}. Do not open it; get the character from a source you trust."
        )
    total = 0
    for info in infos:
        if _is_symlink(info):
            raise CharError(
                f"{label} contains a symbolic link at {info.filename!r}. "
                "Character files never contain links, so this file is not safe to open."
            )
        if info.file_size > limits.MAX_MEMBER_BYTES:
            raise CharError(
                f"{label} contains {info.filename!r} at {info.file_size} bytes, and one file in a "
                f"character may be {limits.MAX_MEMBER_BYTES}. Do not open it; get the character "
                "from a source you trust."
            )
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > limits.MAX_COMPRESSION_RATIO:
                raise CharError(
                    f"{label} contains {info.filename!r}, which expands {ratio:.0f} times over, "
                    "and the "
                    f"limit is {limits.MAX_COMPRESSION_RATIO}. Do not open it; get the character "
                    "from a source you trust."
                )
        total += info.file_size
        if total > limits.MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise CharError(
                f"{label} expands to over {limits.MAX_TOTAL_UNCOMPRESSED_BYTES} bytes, which no "
                "character "
                "reaches. Do not open it; get the character from a source you trust."
            )


def check_member(name: str, data: bytes, label: str) -> bytes:
    """Reject a member that is itself an archive. Nothing in this format nests."""
    if data.startswith(limits.ZIP_MAGIC):
        raise CharError(
            f"{label} contains {name!r}, which is itself a zip archive. "
            "Character files never nest, so this file is not safe to open."
        )
    return data


def read_manifest_bytes(archive: zipfile.ZipFile, label: str) -> bytes:
    """The manifest, size-capped before it is read, so a hostile one cannot exhaust memory."""
    try:
        info = archive.getinfo(MANIFEST_NAME)
    except KeyError:
        raise CharError(
            f"{label} has no manifest.json, so it is not a character file. "
            "Open a .char exported from Omnichar Studio."
        ) from None
    if info.file_size > limits.MAX_MANIFEST_BYTES:
        raise CharError(
            f"{label} has a {info.file_size} byte manifest, and the limit is "
            f"{limits.MAX_MANIFEST_BYTES}. Do not open it; get the character from a source you "
            "trust."
        )
    return archive.read(MANIFEST_NAME)


def parse_manifest(raw: bytes, label: str) -> Manifest:
    """Validate the signature and version, then model the keys this build knows."""
    if not looks_like_char(raw):
        raise CharError(
            f"{label} has a manifest that does not start with the character signature, so it is "
            "not a .char. Open a character exported from Omnichar Studio."
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CharError(
            f"{label} has a manifest that is not valid JSON, so it cannot be opened. Export the "
            "character again from Omnichar Studio."
        ) from error
    version = int(parsed.get("format_version", 0))
    if version > FORMAT_VERSION:
        # A later version may change what a key means, so a partial read is a wrong character.
        raise CharError(
            f"{label} was written by a newer version of Inline Studio "
            f"(character format {version}, this build reads {FORMAT_VERSION}). Update to open it."
        )
    return Manifest.from_json(parsed)


def open_archive(path: Path | str) -> zipfile.ZipFile:
    """Open and shape-check a ``.char``, translating `BadZipFile` for a truncated download."""
    target = Path(path)
    try:
        archive = zipfile.ZipFile(target, "r")
    except FileNotFoundError:
        raise CharError(f"{target} does not exist. Check the path and the file name.") from None
    except zipfile.BadZipFile as error:
        raise CharError(
            f"{target.name} is not a readable character file. It may have been truncated in "
            "transfer; download it again."
        ) from error
    try:
        check_archive(archive, target.name)
    except Exception:
        archive.close()
        raise
    return archive


def read(path: Path | str) -> CharDoc:
    """Load a whole ``.char`` into memory. Raises `CharError` with user-facing copy on failure."""
    target = Path(path)
    with open_archive(target) as archive:
        raw = read_manifest_bytes(archive, target.name)
        manifest = parse_manifest(raw, target.name)
        members = {
            info.filename: check_member(info.filename, archive.read(info.filename), target.name)
            for info in archive.infolist()
            if not info.is_dir() and info.filename != MANIFEST_NAME
        }
    return CharDoc(manifest=manifest, members=members)


def refs_fingerprint(manifest: Manifest, policy: dict[str, Any]) -> str:
    """Ordered original hashes plus policy; harvested refs are out or every adapter goes stale."""
    kept = [ref for ref in manifest.refs if origin_of(ref) == ORIGIN_ORIGINAL]
    parts = [str(ref.get("sha256", "")) for ref in kept]
    parts.append(json.dumps(policy, sort_keys=True, separators=(",", ":")))
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def refs_identity(manifest: Manifest) -> str:
    """Which reference set this is, order included and policy excluded."""
    parts = [f"{ref.get('sha256', '')}:{origin_of(ref)}" for ref in manifest.refs]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def payload_valid(manifest: Manifest, arch: str, encoder_version: str) -> bool:
    """Whether ``payloads/<arch>/`` can be used as-is, or must be recompiled from ``refs/``."""
    payload = manifest.payloads.get(arch)
    if not isinstance(payload, dict):
        return False
    encoder = payload.get("encoder")
    if not isinstance(encoder, dict) or str(encoder.get("version", "")) != encoder_version:
        return False
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        return False
    return str(payload.get("source_sha256", "")) == refs_fingerprint(manifest, policy)


def centroid_valid(manifest: Manifest, encoder_id: str, encoder_version: str) -> bool:
    """Cosine similarity across two encoder builds is meaningless, so the version must match."""
    encoders = manifest.scoring.get("encoders")
    if not isinstance(encoders, list):
        return False
    for entry in encoders:
        if isinstance(entry, dict) and str(entry.get("id")) == encoder_id:
            return str(entry.get("version", "")) == encoder_version
    return False
