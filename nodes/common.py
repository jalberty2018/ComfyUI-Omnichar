# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared pieces for every node: the socket type, image conversion, and the mid-run failure."""

from __future__ import annotations

from typing import Any

import torch
from omnichar_sdk import Character, CharChanged, CharError, Reference

#: forceInput on every CHARACTER input, or the frontend draws a widget for a type it cannot know.
CHARACTER = "CHARACTER"
CHARACTER_INPUT = (CHARACTER, {"forceInput": True})

CATEGORY = "Omnichar"


def to_image(images: list[Any]) -> torch.Tensor:
    """Pillow images to a ComfyUI IMAGE batch: float 0 to 1, shape [B, H, W, 3]."""
    import numpy as np

    if not images:
        raise CharError("No references to convert. Check the role filter and the maximum.")
    frames = [torch.from_numpy(np.array(image, dtype=np.float32) / 255.0) for image in images]
    return torch.stack(frames)


def fail_on_change(error: CharChanged) -> CharError:
    """Fail a render whose character was replaced mid-run; retrying would use a different one."""
    return CharError(
        "The character file changed while this render was running. "
        f"Queue it again to use the new version. ({error})"
    )


def references_of(
    char: Character, arch: str, role: str, maximum: int
) -> list[Reference]:
    """References for a node's settings, with the widget sentinels turned into arguments."""
    refs = char.get_references(
        arch=None if arch in ("", "originals") else arch,
        role=None if role == "any" else role,
        limit=None if maximum <= 0 else maximum,
    )
    if not refs:
        raise CharError(
            f"{char.name} has no {role} references"
            + (f" compiled for {arch}" if arch not in ("", "originals") else "")
            + ". Change the role or the reference set on this node."
        )
    return refs
