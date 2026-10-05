# SPDX-License-Identifier: GPL-3.0-or-later
"""Every reference on its own output, for a model with numbered reference slots."""

from __future__ import annotations

from omnichar_sdk import CharChanged

from .common import CATEGORY, REFS_INPUT, fail_on_change, to_image

#: Nine reference outputs, with unused slots left empty.
SLOTS = 9


class OmnicharCharacterReferencesSplit:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"refs": REFS_INPUT}}

    RETURN_TYPES = ("IMAGE",) * SLOTS + ("INT",)
    RETURN_NAMES = tuple(f"image_{i}" for i in range(SLOTS)) + ("count",)
    FUNCTION = "split"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Every reference on its own output, numbered to match a model's reference slots. One of "
        "these replaces a Character Reference node per slot. Outputs past the character's "
        "reference count are empty, so leave those slots unwired."
    )

    def split(self, refs):
        try:
            images = [to_image([ref.open()]) for ref in refs[:SLOTS]]
        except CharChanged as error:
            raise fail_on_change(error) from error
        # None rather than a blank image: a model given a placeholder would treat it as a
        # reference, and the prompt's numbering would stop matching what it received.
        padded = images + [None] * (SLOTS - len(images))
        return (*padded, len(refs))
