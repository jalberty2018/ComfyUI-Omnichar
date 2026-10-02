# SPDX-License-Identifier: Apache-2.0
"""A character's adapter, with portability measured from its own key names, not its arch label."""

from __future__ import annotations

import json
import re
import struct
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from . import limits
from .charfile import CharError

_UNSAFE = re.compile(r"[^A-Za-z0-9 ._-]+")


class Portability(Enum):
    """Whether an adapter's keys match what tools outside Omnichar Studio expect."""

    PORTABLE = "portable"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"
    UNMEASURED = "unmeasured"


#: Published checkpoint prefixes; an adapter keyed to the diffusers ones loads only in Omnichar.
_REFERENCE_PREFIXES: dict[str, tuple[str, ...]] = {
    "flux2": ("double_blocks.", "single_blocks."),
    "flux2-klein": ("double_blocks.", "single_blocks."),
    "minimax-h3": ("blocks.", "token_refiner.blocks."),
}
_DIFFUSERS_PREFIXES: dict[str, tuple[str, ...]] = {
    "flux2": ("transformer_blocks.", "single_transformer_blocks."),
    "flux2-klein": ("transformer_blocks.", "single_transformer_blocks."),
    "minimax-h3": ("transformer_blocks.", "token_refiner.refiner_blocks."),
}

#: Archs whose diffusers names already match what other tools publish, with the measured share.
_NAME_MATCHED: dict[str, tuple[Portability, str]] = {
    "krea2": (
        Portability.PORTABLE,
        "Krea 2 adapter keys match the published checkpoint exactly (232 of 232 module stems).",
    ),
    "z-image": (
        Portability.PARTIAL,
        "Z-Image adapter keys match 210 of 238 module stems. The remaining 12 percent will not "
        "be applied, so the result is a near miss rather than a failure.",
    ),
}

#: Exported so every caller strips the same set; three private copies had already drifted.
KEY_WRAPPERS = ("diffusion_model.", "transformer.", "base_model.model.", "lora_unet_")

#: Suffixes that reduce an adapter tensor name to the module it attaches to.
KEY_SUFFIXES = (
    ".lora_A.weight", ".lora_B.weight", ".lora_down.weight", ".lora_up.weight",
    ".lora_a.weight", ".lora_b.weight", ".alpha", ".dora_scale", ".diff", ".diff_b",
)


def module_stem(key: str) -> str | None:
    """The module an adapter tensor attaches to, or None when the key is not one."""
    for suffix in KEY_SUFFIXES:
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    else:
        return None
    return _strip_wrappers(key)


def _strip_wrappers(key: str) -> str:
    for wrapper in KEY_WRAPPERS:
        if key.startswith(wrapper):
            return key[len(wrapper) :]
    return key


def _header_length(prefix: bytes, label: str) -> int:
    """The declared header length, bounded before anything is allocated against it."""
    if len(prefix) < 8:
        raise CharError(
            f"{label} is {len(prefix)} bytes long, and a safetensors file starts with an 8 byte "
            "length. The adapter in this character is damaged; export it again from Omnichar "
            "Studio."
        )
    (length,) = struct.unpack("<Q", prefix)
    if length > limits.MAX_SAFETENSORS_HEADER_BYTES:
        raise CharError(
            f"{label} declares a {length} byte safetensors header, and the limit is "
            f"{limits.MAX_SAFETENSORS_HEADER_BYTES}. The file is not a usable adapter and should "
            "not be loaded."
        )
    return length


def _parse_header(body: bytes, length: int, label: str) -> dict[str, Any]:
    """The header JSON, once its declared length has been honoured."""
    if len(body) < length:
        raise CharError(
            f"{label} declares a {length} byte safetensors header but carries only {len(body)} "
            "bytes of it. The file was truncated in transfer; download the character again."
        )
    try:
        header = json.loads(body[:length])
    except json.JSONDecodeError as error:
        raise CharError(
            f"{label} has a safetensors header that is not valid JSON. The adapter is damaged; "
            "export it again from Omnichar Studio."
        ) from error
    if not isinstance(header, dict):
        raise CharError(
            f"{label} has a safetensors header holding {type(header).__name__}, and it must be a "
            "JSON object. The adapter is damaged; export it again from Omnichar Studio."
        )
    return header


def read_safetensors_header(data: bytes, label: str) -> dict[str, Any]:
    """The header of a safetensors file, without loading a single tensor."""
    length = _header_length(data[:8], label)
    return _parse_header(data[8:], length, label)


def read_safetensors_header_stream(stream: Any, label: str) -> dict[str, Any]:
    """The header, read from a stream so a large adapter is never fully decompressed."""
    length = _header_length(stream.read(8), label)
    return _parse_header(stream.read(length), length, label)


def measure_portability(arch: str, keys: list[str]) -> tuple[Portability, str]:
    """Whether these adapter keys will load outside Omnichar Studio, and why."""
    if arch in _NAME_MATCHED:
        return _NAME_MATCHED[arch]
    reference = _REFERENCE_PREFIXES.get(arch)
    diffusers = _DIFFUSERS_PREFIXES.get(arch)
    if reference is None or diffusers is None:
        return (
            Portability.UNMEASURED,
            f"No published measurement exists for {arch} adapter keys. Check the key coverage "
            "against the model you are loading before trusting the result.",
        )
    stripped = [_strip_wrappers(key) for key in keys]
    if any(key.startswith(reference) for key in stripped):
        return (
            Portability.PORTABLE,
            f"The adapter uses the published {arch} checkpoint's key names, so other "
            "tools load it.",
        )
    if any(key.startswith(diffusers) for key in stripped):
        return (
            Portability.INCOMPATIBLE,
            f"The adapter uses Omnichar Studio's internal {arch} key names, which no other tool "
            "reads. It was trained before the key export was added. Retrain it to use it here.",
        )
    return (
        Portability.UNMEASURED,
        f"The adapter's key names match neither the published {arch} checkpoint nor Omnichar "
        "Studio's internal names. Check the key coverage before trusting the result.",
    )


def safe_output_name(raw: str, suffix: str = ".safetensors") -> str:
    """A safe filename from the last path component only; a member name is attacker-controlled."""
    base = str(raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    folded = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    cleaned = _UNSAFE.sub("", folded).strip().strip(".")
    if cleaned.lower().endswith(suffix):
        cleaned = cleaned[: -len(suffix)]
    cleaned = cleaned[: limits.MAX_OUTPUT_NAME_BYTES]
    return f"{cleaned or 'adapter'}{suffix}"


@dataclass(frozen=True)
class Lora:
    """A trained adapter filed against one architecture, with its provenance and its verdict."""

    arch: str
    base: str
    rank: int
    steps: int
    resolution: int
    strength: float
    filename: str
    portability: Portability
    reason: str
    _read: Callable[[str], bytes] = field(compare=False, repr=False, default=lambda _: b"")
    #: Header only: going through `bytes()` would pull a whole adapter to read a few kilobytes.
    _read_header: Callable[[], dict[str, Any]] | None = field(
        compare=False, repr=False, default=None
    )
    _member: str = field(compare=False, repr=False, default="")

    def bytes(self) -> bytes:
        return self._read(self._member)

    def header(self) -> dict[str, Any]:
        """The safetensors header, tensors excluded."""
        if self._read_header is not None:
            return self._read_header()
        return read_safetensors_header(self.bytes(), self.filename)

    def metadata(self) -> dict[str, str]:
        """What the trainer recorded: ``inline_arch``, ``inline_base``, ``inline_rank``."""
        raw = self.header().get("__metadata__")
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    def keys(self) -> list[str]:
        """Tensor names, which is what decides whether another tool can load this."""
        return [k for k in self.header() if k != "__metadata__"]

    def save_to(self, directory: Path | str, name: str | None = None) -> Path:
        """Write the adapter into ``directory``, under a name that cannot escape it."""
        root = Path(directory).resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / safe_output_name(name or self.filename)).resolve()
        # Belt and braces: the name is already stripped to one component, and this proves it.
        if target.parent != root:
            raise CharError(
                f"Refusing to write {name or self.filename!r}, which resolves outside {root}. "
                "Pass a plain filename with no directory part."
            )
        target.write_bytes(self.bytes())
        return target
