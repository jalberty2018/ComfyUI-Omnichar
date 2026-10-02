# SPDX-License-Identifier: GPL-3.0-or-later
"""One reference by position, for a model whose references arrive in numbered slots."""

from __future__ import annotations

from omnichar_sdk import CharChanged, CharError

from .common import CATEGORY, REFS_INPUT, fail_on_change, to_image


class OmnicharCharacterReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "refs": REFS_INPUT,
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
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "INT")
    RETURN_NAMES = ("image", "role", "count")
    FUNCTION = "pick"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "One reference image, by position, from Decode Character's refs output. Use this for a "
        "model that takes references in numbered slots. The image comes out at its own size, "
        "because a slot takes one picture and does not need a common one."
    )

    def pick(self, refs, index):
        try:
            if not refs:
                raise CharError(
                    "Decode Character sent no references. Check its reference set and maximum."
                )
            if index >= len(refs):
                raise CharError(
                    f"Decode Character sent {len(refs)} references, so index {index} does not "
                    f"exist. The last one is {len(refs) - 1}. Leave the extra slots on the model "
                    "empty rather than repeating a reference."
                )
            chosen = refs[index]
            image = to_image([chosen.open()])
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (image, chosen.role, len(refs))
