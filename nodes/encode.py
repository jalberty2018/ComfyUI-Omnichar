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
            "optional": {
                "face": ("IMAGE", {"tooltip": "Face references. Identity comes from these."}),
                "body": ("IMAGE", {"tooltip": "Full-body references, for build and proportions."}),
                "cloths": ("IMAGE", {"tooltip": "Wardrobe references."}),
            },
        }

    RETURN_TYPES = ("CHARACTER",)
    RETURN_NAMES = ("char",)
    FUNCTION = "encode"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Build a character from reference images. Compiles a reference set for FLUX.2 and "
        "MiniMax H3, so it applies on any model that takes references."
    )

    def encode(self, name, description, resolution, face=None, body=None, cloths=None):
        pairs = []
        for batch, role in ((face, "face"), (body, "body"), (cloths, "cloth")):
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
