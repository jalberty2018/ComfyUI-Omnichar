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
    from .nodes.decode import OmnicharDecodeCharacter
    from .nodes.encode import OmnicharEncodeCharacter, OmnicharSaveCharacter
    from .nodes.external import OmnicharLoadCharacterExternal, OmnicharSaveCharacterExternal
    from .nodes.latent import OmnicharCharacterReferenceLatent
    from .nodes.load import OmnicharLoadCharacter
    from .nodes.lora import OmnicharApplyCharacterLoRA
    from .nodes.pick import OmnicharCharacterReference
    from .nodes.split import OmnicharCharacterReferencesSplit
except ImportError as error:
    logger.error(
        "Omnichar character nodes are not loaded: %s\n"
        "Install the reader with:  pip install omnichar-sdk\n"
        "If ComfyUI runs in its own environment, use that environment's pip.",
        error,
    )
else:
    folders.register()
    try:
        from server import PromptServer
    except ImportError:
        pass  # Node tests can run without the ComfyUI server.
    else:
        from .nodes.external import register_routes

        register_routes(PromptServer.instance.routes)

    NODE_CLASS_MAPPINGS = {
        "OmnicharLoadCharacter": OmnicharLoadCharacter,
        "OmnicharDecodeCharacter": OmnicharDecodeCharacter,
        "OmnicharCharacterReference": OmnicharCharacterReference,
        "OmnicharCharacterReferenceLatent": OmnicharCharacterReferenceLatent,
        "OmnicharCharacterReferencesSplit": OmnicharCharacterReferencesSplit,
        "OmnicharApplyCharacterLoRA": OmnicharApplyCharacterLoRA,
        "OmnicharEncodeCharacter": OmnicharEncodeCharacter,
        "OmnicharSaveCharacter": OmnicharSaveCharacter,
        "OmnicharLoadCharacterExternal": OmnicharLoadCharacterExternal,
        "OmnicharSaveCharacterExternal": OmnicharSaveCharacterExternal,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "OmnicharLoadCharacter": "Load Character",
        "OmnicharDecodeCharacter": "Decode Character",
        "OmnicharCharacterReference": "Character Reference",
        "OmnicharCharacterReferenceLatent": "Character Reference Latent",
        "OmnicharCharacterReferencesSplit": "Character References Split",
        "OmnicharApplyCharacterLoRA": "Apply Character LoRA",
        "OmnicharEncodeCharacter": "Encode Character",
        "OmnicharSaveCharacter": "Save Character",
        "OmnicharLoadCharacterExternal": "Load Character (Upload)",
        "OmnicharSaveCharacterExternal": "Save Character (Download)",
    }
