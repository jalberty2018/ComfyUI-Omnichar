# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a character from reference images, and write one to disk."""

from __future__ import annotations

from pathlib import Path

from omnichar_sdk import (
    FLUX2_KLEIN_ARCH,
    MINIMAX_H3_ARCH,
    Character,
    CharError,
    encode_character,
    safe_output_name,
    write,
)

from . import folders
from .common import CATEGORY, CHARACTER_INPUT, from_image

#: Several slots per role, because a ComfyUI input takes one link. Each still accepts a batch, so
#: three Load Image nodes or one batch of three both give three references.
SLOTS_PER_ROLE = 3

_ROLE_HINTS = {
    "face": "Face references. Identity comes from these.",
    "body": "Full-body references, for build and proportions.",
    "cloths": "Wardrobe references.",
}
_ROLE_SLOTS = [
    (slot if n == 1 else f"{slot}_{n}", "cloth" if slot == "cloths" else slot)
    for slot in _ROLE_HINTS
    for n in range(1, SLOTS_PER_ROLE + 1)
]


def _role_inputs() -> dict[str, object]:
    out: dict[str, object] = {}
    for name, _role in _ROLE_SLOTS:
        base = name.split("_")[0]
        out[name] = ("IMAGE", {"tooltip": _ROLE_HINTS[base]})
    return out


class OmnicharEncodeCharacter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "name": ("STRING", {"default": "Character"}),
                "description": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": (
                            "What the character looks like. Every model reads this, and a LoRA "
                            "binds to it, so write it once and keep it."
                        ),
                    },
                ),
                "resolution": (
                    "INT",
                    {
                        "default": 512,
                        "min": 0,
                        "max": 4096,
                        "step": 64,
                        "tooltip": (
                            "What the compiled reference sets are stored at. 0 uses each model's "
                            "own budget. Originals are always kept untouched."
                        ),
                    },
                ),
            },
            "optional": _role_inputs(),
        }

    RETURN_TYPES = ("CHARACTER",)
    RETURN_NAMES = ("char",)
    FUNCTION = "encode"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Build a character from reference images. Compiles a reference set for FLUX.2 and "
        "MiniMax H3, so it applies on any model that takes references."
    )

    def encode(self, name, description, resolution, **images):
        pairs = []
        for slot, role in _ROLE_SLOTS:
            batch = images.get(slot)
            if batch is None:
                continue
            pairs.extend((image, role) for image in from_image(batch))
        if not pairs:
            raise CharError(
                "A character needs at least one reference image. Wire a face, body or cloths "
                "input on this node."
            )
        doc = encode_character(
            name,
            description,
            pairs,
            archs=(FLUX2_KLEIN_ARCH, MINIMAX_H3_ARCH),
            resolution=resolution or None,
        )
        return (Character.from_bytes(_to_bytes(doc), f"{name}.char"),)


def _to_bytes(doc) -> bytes:
    """Through a temporary file, so the character in memory is the bytes that would be saved."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        return write(Path(tmp) / "c.char", doc).read_bytes()


class OmnicharSaveCharacter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "char": CHARACTER_INPUT,
                "filename": (
                    "STRING",
                    {
                        "default": "model.char",
                        "tooltip": "Written into the characters folder. .char is added if missing.",
                    },
                ),
            },
            "optional": {
                "overwrite": (
                    "BOOLEAN",
                    {"default": False, "tooltip": "Off by default, so a character is not lost."},
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "save"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True
    DESCRIPTION = "Write a character into the characters folder so the loader can pick it up."

    def save(self, char, filename, overwrite=False):
        roots = folders.roots()
        if not roots:
            raise CharError(
                "No characters directory is registered. Create ComfyUI/models/characters and "
                "restart."
            )
        target = roots[0] / safe_output_name(filename, ".char")
        if target.exists() and not overwrite:
            raise CharError(
                f"{target.name} already exists. Turn on overwrite, or choose another filename."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(char.to_bytes())
        return (str(target),)
