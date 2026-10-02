# SPDX-License-Identifier: Apache-2.0
"""Build a ``.char`` from reference images and a description, matching Omnichar Studio's layout."""

from __future__ import annotations

import io
import time
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from . import charfile as cf
from .references import _require_pillow

if TYPE_CHECKING:  # pragma: no cover
    from PIL.Image import Image

#: Bumping either recompiles every stored reference set, so they track Omnichar Studio exactly.
PAYLOAD_ENCODER_ID = "flux2-klein-refset"
PAYLOAD_ENCODER_VERSION = "1"

FLUX2_KLEIN_ARCH = "flux2-klein"
MINIMAX_H3_ARCH = "minimax-h3"
FAL_REF_ARCH = "fal-ref"

#: What each model accepts as a reference. A video model has its own grid, so this is not one
#: constant, and the policy rides in the payload because the fingerprint is taken against it.
PAYLOAD_POLICY: dict[str, Any] = {"max_pixels": 1024 * 1024, "multiple_of": 16}
MINIMAX_H3_POLICY: dict[str, Any] = {"short_edge": 2048, "multiple_of": 32, "max_aspect": 4.0}
FAL_REF_POLICY: dict[str, Any] = {"max_pixels": 1024 * 1024, "multiple_of": 8}

REFERENCE_POLICIES: dict[str, dict[str, Any]] = {
    FLUX2_KLEIN_ARCH: PAYLOAD_POLICY,
    MINIMAX_H3_ARCH: MINIMAX_H3_POLICY,
    FAL_REF_ARCH: FAL_REF_POLICY,
}


def reference_policy(arch: str) -> dict[str, Any]:
    return REFERENCE_POLICIES.get(arch, PAYLOAD_POLICY)


def capped_policy(arch: str, resolution: int | None) -> dict[str, Any]:
    """A model's policy with its target lowered; this sets what the file stores, not render cost."""
    policy = dict(reference_policy(arch))
    if resolution is None or int(resolution) <= 0:
        return policy
    if "short_edge" in policy:
        policy["short_edge"] = min(int(policy["short_edge"]), int(resolution))
    else:
        policy["max_pixels"] = min(int(policy["max_pixels"]), int(resolution) ** 2)
    return policy


def _png_bytes(image: Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def normalise_reference(image: Image, policy: dict[str, Any] | None = None) -> Image:
    """A reference resized into a model's budget, on its grid, preserving aspect.

    Two policy shapes: ``max_pixels`` is an area cap that only shrinks, ``short_edge`` is a target
    the smaller side is scaled onto, up or down.
    """
    rules = policy or PAYLOAD_POLICY
    grid = int(rules["multiple_of"])
    width, height = image.width, image.height
    limit = rules.get("max_aspect")
    if limit and max(width / height, height / width) > float(limit):
        raise cf.CharError(
            f"A reference must be within 1:{limit:g} and {limit:g}:1 for this model, got "
            f"{width}x{height}. Crop it closer to square before encoding."
        )
    if "short_edge" in rules:
        # Rounded, not floored: flooring a scaled-up edge can land back under the target.
        scale = int(rules["short_edge"]) / min(width, height)
        width = max(grid, round(width * scale / grid) * grid)
        height = max(grid, round(height * scale / grid) * grid)
    else:
        max_pixels = int(rules["max_pixels"])
        if width * height > max_pixels:
            scale = (max_pixels / (width * height)) ** 0.5
            width, height = int(width * scale), int(height * scale)
        width = max(grid, (width // grid) * grid)
        height = max(grid, (height // grid) * grid)
    if (width, height) == (image.width, image.height):
        return image
    _require_pillow()
    from PIL import Image as PILImage

    return image.resize((width, height), PILImage.Resampling.LANCZOS)


def build_payload(
    manifest: cf.Manifest,
    members: dict[str, bytes],
    images: Sequence[Image],
    arch: str = FLUX2_KLEIN_ARCH,
    policy: dict[str, Any] | None = None,
) -> None:
    """(Re)compile one model's reference set into ``payloads/<arch>/``."""
    rules = policy or reference_policy(arch)
    for stale in [m for m in members if m.startswith(f"payloads/{arch}/")]:
        members.pop(stale, None)
    files: list[dict[str, Any]] = []
    for slot, image in enumerate(images):
        member = f"payloads/{arch}/ref_{slot:03d}.png"
        data = _png_bytes(normalise_reference(image, rules))
        members[member] = data
        # The role rides with the compiled file, because apply numbers the prompt from it.
        role = cf.role_of(manifest.refs[slot]) if slot < len(manifest.refs) else cf.ROLE_FACE
        files.append({"path": member, "sha256": cf.sha256_bytes(data), "role": role})
    manifest.payloads[arch] = {
        "payload_version": 1,
        "type": cf.PAYLOAD_REF,
        "encoder": {"id": PAYLOAD_ENCODER_ID, "version": PAYLOAD_ENCODER_VERSION},
        "source_sha256": cf.refs_fingerprint(manifest, rules),
        "policy": dict(rules),
        "harvested_count": 0,
        "files": files,
    }


def encode_character(
    name: str,
    description: str,
    images: Sequence[tuple[Image, str]],
    *,
    archs: Sequence[str] = (FLUX2_KLEIN_ARCH, MINIMAX_H3_ARCH),
    resolution: int | None = None,
    app_version: str = "",
) -> cf.CharDoc:
    """A new character from ``(image, role)`` pairs, with a reference set compiled per arch.

    References go in untouched: everything else is derived from them, so a lossy original would
    poison every payload rebuilt from it later.
    """
    if not images:
        raise cf.CharError("A character needs at least one reference image.")
    _require_pillow()
    now = int(time.time())
    manifest = cf.Manifest(
        char_id=str(uuid.uuid4()),
        name=name.strip() or "Character",
        created_at=now,
        modified_at=now,
        app_version=app_version,
    )
    members: dict[str, bytes] = {}
    ordered: list[Image] = []
    # Originals first and face before body before cloth, because position is what a prompt names.
    by_role = sorted(images, key=lambda pair: cf.ROLES.index(cf.role_of({"role": pair[1]})))
    for index, (image, role) in enumerate(by_role):
        rgb = image.convert("RGB")
        member = cf.member_name("refs", index, ".png")
        data = _png_bytes(rgb)
        members[member] = data
        manifest.refs.append(
            {
                "path": member,
                "sha256": cf.sha256_bytes(data),
                "width": rgb.width,
                "height": rgb.height,
                "origin": cf.ORIGIN_ORIGINAL,
                "role": cf.role_of({"role": role}),
            }
        )
        ordered.append(rgb)

    text = description.strip().encode("utf-8")
    if text:
        members["text/description.md"] = text
        manifest.text = {"path": "text/description.md", "sha256": cf.sha256_bytes(text)}

    for arch in archs:
        build_payload(manifest, members, ordered, arch, capped_policy(arch, resolution))
    return cf.CharDoc(manifest=manifest, members=members)
