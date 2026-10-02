# SPDX-License-Identifier: GPL-3.0-or-later
"""One reference by position, for a model whose references arrive in numbered slots."""

from __future__ import annotations

from omnichar_sdk import CharChanged, CharError

from .common import CATEGORY, CHARACTER_INPUT, fail_on_change, to_image


class OmnicharCharacterReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "char": CHARACTER_INPUT,
                "index": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 63,
                        "tooltip": (
                            "Counting from zero, so index 0 goes in ref_image_0 and the prompt "
                            "calls it image 1."
                        ),
                    },
                ),
            },
            "optional": {
                "arch": (
                    "STRING",
                    {
                        "default": "originals",
                        "tooltip": (
                            "Which reference set to read. Use the same value on every node "
                            "feeding one model, or the positions will not line up."
                        ),
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "INT")
    RETURN_NAMES = ("image", "role", "count")
    FUNCTION = "pick"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "One reference image, by position. Use this for a model that takes references in "
        "numbered slots, so the slot a reference lands in is the number the prompt gives it."
    )

    def pick(self, char, index, arch="originals"):
        try:
            selected = None if arch in ("", "originals") else arch
            refs = char.get_references(arch=selected)
            if not refs:
                raise CharError(
                    f"{char.name} has no references"
                    + (f" compiled for {arch}" if selected else "")
                    + "."
                )
            if index >= len(refs):
                raise CharError(
                    f"{char.name} has {len(refs)} references in its {arch} set, so index {index} "
                    f"does not exist. The last one is {len(refs) - 1}. Leave the extra slots on "
                    "the model empty rather than repeating a reference."
                )
            chosen = refs[index]
            image = to_image([chosen.open()])
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (image, chosen.role, len(refs))
