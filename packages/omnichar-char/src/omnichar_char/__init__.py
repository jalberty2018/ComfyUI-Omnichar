# SPDX-License-Identifier: Apache-2.0
"""Read Omnichar Studio ``.char`` character files; images need the ``images`` extra."""

from .character import Character, CharacterInfo
from .charfile import (
    FORMAT_VERSION,
    MAGIC,
    ORIGIN_HARVESTED,
    ORIGIN_ORIGINAL,
    ROLE_BODY,
    ROLE_CLOTH,
    ROLE_FACE,
    ROLES,
    CharChanged,
    CharDoc,
    CharError,
    Manifest,
    looks_like_char,
    payload_key,
    read,
)
from .lora import (
    KEY_SUFFIXES,
    KEY_WRAPPERS,
    Lora,
    Portability,
    module_stem,
    safe_output_name,
)
from .prompt import STYLES, prompt_prefix
from .references import FIT_MODES, SIZE_POLICIES, Reference, allocate_roles, common_size, fit_roles
from .sheet import reference_sheet, sheet_png

__version__ = "0.0.1"

__all__ = [
    "FIT_MODES",
    "KEY_SUFFIXES",
    "KEY_WRAPPERS",
    "FORMAT_VERSION",
    "MAGIC",
    "ORIGIN_HARVESTED",
    "ORIGIN_ORIGINAL",
    "ROLES",
    "ROLE_BODY",
    "ROLE_CLOTH",
    "ROLE_FACE",
    "SIZE_POLICIES",
    "STYLES",
    "CharChanged",
    "CharDoc",
    "CharError",
    "Character",
    "CharacterInfo",
    "Lora",
    "Manifest",
    "Portability",
    "Reference",
    "__version__",
    "allocate_roles",
    "common_size",
    "fit_roles",
    "looks_like_char",
    "module_stem",
    "payload_key",
    "prompt_prefix",
    "reference_sheet",
    "sheet_png",
    "read",
    "safe_output_name",
]
