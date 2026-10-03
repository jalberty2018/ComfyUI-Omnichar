# SPDX-License-Identifier: GPL-3.0-or-later
"""Attach a character's references to conditioning, for a model that reads them as latents."""

from __future__ import annotations

import node_helpers
from omnichar_sdk import CharChanged, CharError

from .common import CATEGORY, REFS_INPUT, fail_on_change, to_image


class OmnicharCharacterReferenceLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "refs": REFS_INPUT,
                "vae": ("VAE", {"tooltip": "Encodes each reference. Use the model's own VAE."}),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "attach"
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Attach every reference to the conditioning as a latent, for an edit model like FLUX.2. "
        "Replaces a chain of Set Reference Latent nodes, and takes as many references as the "
        "character has. Feed it to the positive and the negative conditioning both."
    )

    def attach(self, conditioning, refs, vae):
        try:
            if not refs:
                raise CharError(
                    "Decode Character sent no references. Check its reference set and maximum."
                )
            # One append of the whole list, which is how ComfyUI's own multi-reference nodes do it.
            latents = [vae.encode(to_image([ref.open()])[:, :, :, :3]) for ref in refs]
        except CharChanged as error:
            raise fail_on_change(error) from error
        return (
            node_helpers.conditioning_set_values(
                conditioning, {"reference_latents": latents}, append=True
            ),
        )
