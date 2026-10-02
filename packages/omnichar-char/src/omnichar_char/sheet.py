# SPDX-License-Identifier: Apache-2.0
"""References laid out as one contact sheet, numbered because a position is what a prompt names."""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from .charfile import CharError
from .references import Reference, _require_pillow

if TYPE_CHECKING:  # pragma: no cover
    from PIL.Image import Image

#: Dark by default, because the app and ComfyUI are both dark.
BACKGROUND = "#111418"
FOREGROUND = "#e8eaed"
MUTED = "#9aa0a6"
EDGE = "#2a2f36"

_PAD = 16
_CAPTION = 26
_TITLE = 44


def _font(size: int) -> Any:
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow below 10.1 takes no size; the bitmap default is small but always present.
        return ImageFont.load_default()


def reference_sheet(
    refs: Sequence[Reference],
    *,
    title: str | None = None,
    subtitle: str | None = None,
    columns: int | None = None,
    cell: tuple[int, int] = (384, 384),
    fit: str = "pad",
    first_position: int = 1,
    labels: bool = True,
    background: str = BACKGROUND,
    foreground: str = FOREGROUND,
) -> Image:
    """Lay references out in a grid, numbered from ``first_position`` as `prompt_prefix` is."""
    if not refs:
        raise CharError(
            "A reference sheet needs at least one reference and this character has none "
            "matching the filters. Widen the role or the limit, or pick another reference set."
        )
    if cell[0] <= 0 or cell[1] <= 0:
        raise ValueError(f"Cell size must be positive, got {cell!r}.")
    if columns is not None and columns <= 0:
        raise ValueError(f"Columns must be positive, got {columns!r}.")

    _require_pillow()
    from PIL import Image as PILImage
    from PIL import ImageDraw

    cols = columns or min(len(refs), max(1, math.ceil(math.sqrt(len(refs)))))
    rows = math.ceil(len(refs) / cols)
    caption = _CAPTION if labels else 0
    head = _TITLE if title else 0
    cw, ch = cell

    width = _PAD + cols * (cw + _PAD)
    height = head + _PAD + rows * (ch + caption + _PAD)
    sheet = PILImage.new("RGB", (width, height), background)  # type: ignore[arg-type]  # Pillow ships no stubs; a colour string is valid for RGB
    draw = ImageDraw.Draw(sheet)

    if title:
        draw.text((_PAD, _PAD - 4), title, fill=foreground, font=_font(22))
        if subtitle:
            draw.text(
                (_PAD + draw.textlength(title, font=_font(22)) + 12, _PAD + 2),
                subtitle,
                fill=MUTED,
                font=_font(15),
            )

    for index, ref in enumerate(refs):
        col, row = index % cols, index // cols
        x = _PAD + col * (cw + _PAD)
        y = head + _PAD + row * (ch + caption + _PAD)
        sheet.paste(ref.fit(cell, fit, pad_color=background), (x, y))
        # A hairline, because a letterboxed cell that matches the sheet has no edge of its own.
        draw.rectangle((x, y, x + cw - 1, y + ch - 1), outline=EDGE)
        if labels:
            draw.text(
                (x, y + ch + 5),
                f"{first_position + index}  {ref.role}",
                fill=MUTED,
                font=_font(15),
            )
    return sheet


def sheet_png(sheet: Image) -> bytes:
    """The sheet as PNG bytes, which is what a caller almost always wants next."""
    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    return buffer.getvalue()
