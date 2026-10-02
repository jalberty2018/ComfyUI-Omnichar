# SPDX-License-Identifier: GPL-3.0-or-later
"""What a character holds, as plain strings."""

from __future__ import annotations

from omnichar_sdk import CharChanged

from .common import CATEGORY, CHARACTER_INPUT, fail_on_change


class OmnicharCharacterInfo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"character": CHARACTER_INPUT}}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("name", "description", "hints", "ref_count", "available")
    FUNCTION = "read"
    CATEGORY = CATEGORY
    DESCRIPTION = "Read a character's name, description, hints and the model families it supports."

    def read(self, character):
        try:
            info = character.get_info()
        except CharChanged as error:
            raise fail_on_change(error) from error
        available = ", ".join(
            [f"references: {', '.join(info.ref_archs) or 'none'}"]
            + [f"adapters: {', '.join(info.lora_archs) or 'none'}"]
        )
        return (info.name, info.description, "\n".join(info.hints), info.ref_count, available)
