# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn a character into the references, sheet and conditioning a sampler can take."""

from __future__ import annotations

from omnichar_sdk import FIT_MODES, SIZE_POLICIES, STYLES, CharChanged, CharError, common_size

from .common import CATEGORY, CHARACTER_INPUT, fail_on_change, to_image

_ARCH_TOOLTIP = (
    "Which reference set to send. 'originals' is what the character was built from; naming a "
    "model family sends the set compiled for it."
)


class OmnicharApplyCharacter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "char": CHARACTER_INPUT,
                "clip": (
                    "CLIP",
                    {"tooltip": "Encodes the prompt, so this node can output CONDITIONING."},
                ),
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
            },
            "optional": {
                "prompt": (
                    "STRING",
                    {"default": "", "multiline": True, "tooltip": "Appended after the character."},
                ),
                "arch": ("STRING", {"default": "originals", "tooltip": _ARCH_TOOLTIP}),
                "max_references": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 64,
                        "tooltip": (
                            "Cap the number sent. Slots divide between face, body and outfit "
                            "rather than cutting the end, so a character keeps its wardrobe. "
                            "0 means no cap."
                        ),
                    },
                ),
                "size_from": (list(SIZE_POLICIES), {"default": "first"}),
                "fit": (list(FIT_MODES), {"default": "pad"}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("conditioning", "references", "sheet", "prompt")
    FUNCTION = "apply"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "A character as conditioning, reference images and a contact sheet. Wire only what you "
        "need; the sheet is there to check the reference numbers against the prompt."
    )

    def apply(
        self, char, clip, style, prompt="", arch="originals",
        max_references=0, size_from="first", fit="pad",
    ):
        try:
            selected = None if arch in ("", "originals") else arch
            refs = char.get_references(
                arch=selected, limit=None if max_references <= 0 else max_references
            )
            if not refs:
                raise CharError(
                    f"{char.name} has no references"
                    + (f" compiled for {arch}" if selected else "")
                    + ". Change the reference set on this node."
                )
            text = char.get_prompt(style=style, arch=selected, count=len(refs))
            full = f"{text}{prompt}".strip()
            size = common_size(refs, size_from)
            images = to_image([ref.fit(size, fit) for ref in refs])
            sheet = to_image(
                [char.reference_sheet(arch=selected, limit=max_references or None)]
            )
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (clip.encode_from_tokens_scheduled(clip.tokenize(full)), images, sheet, full)
