# SPDX-License-Identifier: GPL-3.0-or-later
"""Reference images as a batch or as a list, since batching costs either pixels or shape."""

from __future__ import annotations

from omnichar_sdk import FIT_MODES, ROLES, SIZE_POLICIES, CharChanged, common_size

from .common import CATEGORY, CHARACTER_INPUT, fail_on_change, references_of, to_image

_ROLES = ["any", *ROLES]
_ARCH_TOOLTIP = (
    "Which reference set to read. 'originals' is what the character was built from; naming a "
    "model family reads the set compiled for it."
)
_MAX_TOOLTIP = (
    "Cap the number sent. Slots divide between face, body and outfit rather than cutting the end "
    "of the list, so a character does not lose its wardrobe. 0 means no cap."
)


def _common_inputs():
    return {
        "character": CHARACTER_INPUT,
        "arch": ("STRING", {"default": "originals", "tooltip": _ARCH_TOOLTIP}),
        "role": (_ROLES, {"default": "any", "tooltip": "Send only references of one kind."}),
        "max_references": (
            "INT",
            {"default": 0, "min": 0, "max": 64, "tooltip": _MAX_TOOLTIP},
        ),
    }


class OmnicharCharacterReferences:
    @classmethod
    def INPUT_TYPES(cls):
        required = _common_inputs()
        required["size_from"] = (
            list(SIZE_POLICIES),
            {"default": "first", "tooltip": "Which reference's size the batch is built at."},
        )
        required["fit"] = (
            list(FIT_MODES),
            {
                "default": "pad",
                "tooltip": (
                    "pad keeps shape and adds black bands, cover crops to fill, stretch distorts."
                ),
            },
        )
        return {"required": required}

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    FUNCTION = "load"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "A character's references as one IMAGE batch, in the order a prompt's positions refer to."
    )

    def load(self, character, arch, role, max_references, size_from, fit):
        try:
            refs = references_of(character, arch, role, max_references)
            size = common_size(refs, size_from)
            images = [ref.fit(size, fit) for ref in refs]
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (to_image(images), len(images))


class OmnicharCharacterReferenceList:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": _common_inputs()}

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    OUTPUT_IS_LIST = (True, False)
    FUNCTION = "load"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "A character's references at their own sizes, one per output. Nothing is resampled, but "
        "every node downstream runs once per reference, so the rest of the graph fans out."
    )

    def load(self, character, arch, role, max_references):
        try:
            refs = references_of(character, arch, role, max_references)
            images = [to_image([ref.open()]) for ref in refs]
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (images, len(images))


class OmnicharCharacterReferenceAt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character": CHARACTER_INPUT,
                "arch": ("STRING", {"default": "originals", "tooltip": _ARCH_TOOLTIP}),
                "index": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 63,
                        "tooltip": "Which reference, counting from zero.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "role")
    FUNCTION = "load"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "One reference image, chosen by position. There is no role filter here on purpose: it "
        "would renumber the references, and the position is what a prompt refers to."
    )

    def load(self, character, arch, index):
        from omnichar_sdk import CharError

        try:
            refs = references_of(character, arch, "any", 0)
            if index >= len(refs):
                raise CharError(
                    f"{character.name} has {len(refs)} references in its {arch} set, so index "
                    f"{index} does not exist. The last one is {len(refs) - 1}."
                )
            chosen = refs[index]
            image = to_image([chosen.open()])
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (image, chosen.role)
