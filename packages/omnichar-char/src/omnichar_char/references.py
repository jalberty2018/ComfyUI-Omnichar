# SPDX-License-Identifier: Apache-2.0
"""Reference images, the role allocation that caps them, and resizing onto a chosen size."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import limits
from .charfile import ROLE_BODY, ROLE_CLOTH, ROLE_FACE, ROLES, CharError

if TYPE_CHECKING:  # pragma: no cover
    from PIL.Image import Image

#: Face gets half, body and cloth a quarter each, because identity is carried by the face.
ROLE_RATIO: dict[str, int] = {ROLE_FACE: 2, ROLE_BODY: 1, ROLE_CLOTH: 1}

FIT_MODES = ("pad", "cover", "stretch")
SIZE_POLICIES = ("first", "largest", "smallest")


def allocate_roles(counts: dict[str, int], cap: int) -> dict[str, int]:
    """How many of each role to send, split by `ROLE_RATIO` and reassigning slots nobody fills."""
    wanted = {role: max(0, int(counts.get(role, 0))) for role in ROLES}
    if sum(wanted.values()) <= cap:
        return wanted

    total_weight = sum(ROLE_RATIO.values())
    exact = {role: cap * ROLE_RATIO[role] / total_weight for role in ROLES}
    share = {role: min(wanted[role], int(exact[role])) for role in ROLES}

    # Largest remainder first, then whoever still has references left, so no slot goes unused.
    spare = cap - sum(share.values())
    order = sorted(ROLES, key=lambda r: (-(exact[r] - int(exact[r])), -ROLE_RATIO[r], r))
    while spare > 0:
        moved = False
        for role in order:
            if spare and share[role] < wanted[role]:
                share[role] += 1
                spare -= 1
                moved = True
        if not moved:
            break
    return share


def fit_roles(refs: Sequence[Reference], limit: int) -> list[Reference]:
    """Cap by role rather than by arrival, so a character does not lose its wardrobe to a trim."""
    if limit >= len(refs) or limit <= 0:
        return list(refs[: max(0, limit)])
    roles = [ref.role for ref in refs]
    counts = {role: roles.count(role) for role in ROLES}
    share = allocate_roles(counts, limit)
    keep: list[int] = []
    taken = dict.fromkeys(ROLES, 0)
    for index, role in enumerate(roles):
        if taken[role] < share.get(role, 0):
            taken[role] += 1
            keep.append(index)
    return [refs[i] for i in keep]


def _require_pillow() -> None:
    """Pillow is an extra, so say what to install rather than raising ImportError at the caller."""
    try:
        from PIL import Image
    except ImportError as error:
        raise CharError(
            "Decoding reference images needs Pillow, which is not installed. "
            "Install it with: pip install 'omnichar-char[images]'"
        ) from error
    # A reference is untrusted input, so cap the decode before any image is opened.
    Image.MAX_IMAGE_PIXELS = limits.MAX_IMAGE_PIXELS


@dataclass(frozen=True)
class Reference:
    """One reference image. Bytes are fetched on demand, never held for the character's lifetime."""

    path: str
    role: str
    origin: str
    width: int
    height: int
    sha256: str
    _read: Callable[[str], bytes] = field(compare=False, repr=False, default=lambda _: b"")

    def bytes(self) -> bytes:
        return self._read(self.path)

    def open(self) -> Image:
        """Decode to a Pillow image in RGB. Needs the ``images`` extra."""
        import io

        _require_pillow()
        from PIL import Image as PILImage

        return PILImage.open(io.BytesIO(self.bytes())).convert("RGB")

    def fit(self, size: tuple[int, int], mode: str = "pad", pad_color: str = "black") -> Image:
        """Resize onto ``size``: ``pad`` letterboxes in ``pad_color``, ``cover`` crops."""
        if mode not in FIT_MODES:
            raise ValueError(f"Unknown fit mode {mode!r}. Use one of {', '.join(FIT_MODES)}.")
        # After open(), which carries the guard that says what to install.
        source = self.open()
        from PIL import Image as PILImage

        target_w, target_h = size
        if target_w <= 0 or target_h <= 0:
            raise ValueError(f"Fit size must be positive, got {size!r}.")
        if mode == "stretch":
            return source.resize((target_w, target_h), PILImage.Resampling.LANCZOS)

        scale_w = target_w / source.width
        scale_h = target_h / source.height
        scale = max(scale_w, scale_h) if mode == "cover" else min(scale_w, scale_h)
        scaled = source.resize(
            (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
            PILImage.Resampling.LANCZOS,
        )
        if mode == "cover":
            left = (scaled.width - target_w) // 2
            top = (scaled.height - target_h) // 2
            return scaled.crop((left, top, left + target_w, top + target_h))
        canvas = PILImage.new("RGB", (target_w, target_h), pad_color)  # type: ignore[arg-type]  # Pillow ships no stubs; a colour string is valid for RGB
        canvas.paste(scaled, ((target_w - scaled.width) // 2, (target_h - scaled.height) // 2))
        return canvas


def common_size(refs: Sequence[Reference], policy: str = "first") -> tuple[int, int]:
    """One size every reference fits onto, separate from `fit` so either can be overridden."""
    if policy not in SIZE_POLICIES:
        raise ValueError(f"Unknown size policy {policy!r}. Use one of {', '.join(SIZE_POLICIES)}.")
    if not refs:
        raise ValueError(
            "common_size needs at least one reference and was given none. Check the role filter "
            "and the limit that produced this list."
        )
    if policy == "first":
        return (refs[0].width, refs[0].height)
    def area(ref: Reference) -> tuple[int, int, int]:
        return (ref.width * ref.height, ref.width, ref.height)

    chosen = max(refs, key=area) if policy == "largest" else min(refs, key=area)
    return (chosen.width, chosen.height)
