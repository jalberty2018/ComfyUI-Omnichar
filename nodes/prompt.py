# SPDX-License-Identifier: GPL-3.0-or-later
"""Prompt text that binds a character to the reference positions a model will see."""

from __future__ import annotations

from omnichar_char import STYLES, CharChanged

from .common import CATEGORY, CHARACTER_INPUT, fail_on_change


class OmnicharCharacterPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character": CHARACTER_INPUT,
                "style": (
                    list(STYLES),
                    {
                        "default": "ordinal",
                        "tooltip": (
                            "How the model addresses reference positions. FLUX.2 reads ordinal "
                            "prose, MiniMax H3 reads <Picture N>, Seedance reads @ImageN. "
                            "description-only drops positions, which is what a LoRA needs."
                        ),
                    },
                ),
                "first_position": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 64,
                        "tooltip": "The position the character's first reference lands on.",
                    },
                ),
            },
            "optional": {
                "prompt": (
                    "STRING",
                    {"default": "", "multiline": True, "tooltip": "Appended after the character."},
                ),
                "arch": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Count a compiled reference set instead of the originals.",
                    },
                ),
                "role_lines": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": (
                            "Name which positions carry the face, body and outfit. Off by default: "
                            "the bindings are unverified and one phrasing made H3 replay the "
                            "references as opening frames."
                        ),
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = CATEGORY
    DESCRIPTION = "Build prompt text naming the positions a character's references occupy."

    def build(self, character, style, first_position, prompt="", arch="", role_lines=False):
        try:
            prefix = character.get_prompt(
                style=style,
                first_position=first_position,
                role_lines=role_lines,
                arch=arch or None,
            )
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (f"{prefix}{prompt}".strip(),)
