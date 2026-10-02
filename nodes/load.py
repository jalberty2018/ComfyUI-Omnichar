# SPDX-License-Identifier: GPL-3.0-or-later
"""Load a ``.char`` and put it on a CHARACTER wire."""

from __future__ import annotations

import os

from omnichar_char import Character, CharError

from . import folders
from .common import CATEGORY, CHARACTER


class OmnicharLoadCharacter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character": (
                    folders.listed(),
                    {"tooltip": "A .char file from models/characters."},
                ),
            },
            "optional": {
                "char_path": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": (
                            "Open a file by path instead of by name. It must sit inside a "
                            "registered character directory."
                        ),
                        "advanced": True,
                    },
                ),
            },
        }

    RETURN_TYPES = (CHARACTER,)
    RETURN_NAMES = ("character",)
    FUNCTION = "load"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Open an Omnichar Studio character file. Feed the result to the other Omnichar nodes to "
        "get its references, its description or its trained LoRA."
    )

    @classmethod
    def IS_CHANGED(cls, character, char_path=""):
        # One stat: hashing the archive costs over a second on a character carrying an adapter.
        try:
            stat = os.stat(folders.resolve(character, char_path))
        except (CharError, OSError):
            return float("nan")
        return (stat.st_mtime_ns, stat.st_size)

    @classmethod
    def VALIDATE_INPUTS(cls, character, char_path=""):
        # Through Character.open so the caps apply; this runs on every queue, before the node.
        try:
            Character.open(folders.resolve(character, char_path))
        except CharError as error:
            return str(error)
        except Exception:
            return f"{character} is not a readable character file."
        return True

    def load(self, character, char_path=""):
        return (Character.open(folders.resolve(character, char_path)),)
