# SPDX-License-Identifier: GPL-3.0-or-later
"""ComfyUI nodes for Omnichar character files; registers nothing if the reader is missing."""

import logging

logger = logging.getLogger("omnichar")

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

try:
    from .nodes import folders
    from .nodes.info import OmnicharCharacterInfo
    from .nodes.load import OmnicharLoadCharacter
    from .nodes.lora import OmnicharApplyCharacterLoRA, OmnicharExportCharacterLoRA
    from .nodes.prompt import OmnicharCharacterPrompt
    from .nodes.references import (
        OmnicharCharacterReferenceAt,
        OmnicharCharacterReferenceList,
        OmnicharCharacterReferences,
    )
except ImportError as error:
    logger.error(
        "Omnichar character nodes are not loaded: %s\n"
        "Install the reader with:  pip install omnichar-char\n"
        "If ComfyUI runs in its own environment, use that environment's pip.",
        error,
    )
else:
    folders.register()

    NODE_CLASS_MAPPINGS = {
        "OmnicharLoadCharacter": OmnicharLoadCharacter,
        "OmnicharCharacterInfo": OmnicharCharacterInfo,
        "OmnicharCharacterPrompt": OmnicharCharacterPrompt,
        "OmnicharCharacterReferences": OmnicharCharacterReferences,
        "OmnicharCharacterReferenceList": OmnicharCharacterReferenceList,
        "OmnicharCharacterReferenceAt": OmnicharCharacterReferenceAt,
        "OmnicharApplyCharacterLoRA": OmnicharApplyCharacterLoRA,
        "OmnicharExportCharacterLoRA": OmnicharExportCharacterLoRA,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "OmnicharLoadCharacter": "Load Character (.char)",
        "OmnicharCharacterInfo": "Character Info",
        "OmnicharCharacterPrompt": "Character Prompt",
        "OmnicharCharacterReferences": "Character References",
        "OmnicharCharacterReferenceList": "Character Reference List",
        "OmnicharCharacterReferenceAt": "Character Reference At",
        "OmnicharApplyCharacterLoRA": "Apply Character LoRA",
        "OmnicharExportCharacterLoRA": "Export Character LoRA",
    }
