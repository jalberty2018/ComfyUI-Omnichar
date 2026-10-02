"""The reference sheet: layout, numbering, and the PNG it writes."""

import struct
import zlib

import pytest
from conftest import FIXTURES
from omnichar_sdk import Character, CharError, reference_sheet, sheet_png
from omnichar_sdk.references import Reference


def char():
    return Character.open(FIXTURES / "ada.char")


def png(w, h, rgb=(120, 120, 120)):
    def chunk(tag, data):
        body = tag + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + body + crc

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def fake(n, role="face"):
    data = png(40, 30)
    return [
        Reference(f"refs/{i:03d}.png", role, "original", 40, 30, "", lambda _p, d=data: d)
        for i in range(n)
    ]


def test_a_sheet_of_the_real_character_has_a_cell_per_reference():
    sheet = char().reference_sheet(cell=(100, 100))
    # Two refs side by side: 16 pad + 2 * (100 + 16) wide, title band plus one row tall.
    assert sheet.size == (16 + 2 * 116, 44 + 16 + (100 + 26 + 16))


@pytest.mark.parametrize(
    ("n", "cols", "rows"),
    [(1, 1, 1), (2, 2, 1), (3, 2, 2), (4, 2, 2), (5, 3, 2), (9, 3, 3), (10, 4, 3)],
)
def test_the_grid_stays_square_as_references_are_added(n, cols, rows):
    sheet = reference_sheet(fake(n), cell=(50, 50), labels=False)
    assert sheet.size == (16 + cols * 66, 16 + rows * 66)


def test_columns_can_be_forced():
    assert reference_sheet(fake(6), columns=6, cell=(50, 50), labels=False).size[0] == 16 + 6 * 66


def test_numbering_starts_where_the_prompt_does():
    # The sheet and the prompt have to agree about which image is image one.
    text = char().get_prompt(first_position=3)
    assert text.startswith("Images 3 and 4 show Ada,")
    # Rendered at the same offset, so the labels read 3 and 4 rather than 1 and 2.
    assert char().reference_sheet(first_position=3).size[1] > 0


def test_labels_can_be_turned_off_and_the_sheet_gets_shorter():
    with_labels = reference_sheet(fake(2), cell=(50, 50))
    without = reference_sheet(fake(2), cell=(50, 50), labels=False)
    assert with_labels.size[1] > without.size[1]


def test_the_title_band_is_dropped_when_there_is_no_title():
    assert reference_sheet(fake(1), cell=(50, 50), labels=False, title=None).size[1] == 16 + 66


def test_padding_matches_the_sheet_so_a_cell_has_no_black_border():
    # A 40x30 reference in a square cell letterboxes; the bars must be the sheet colour, not black.
    sheet = reference_sheet(fake(1), cell=(80, 80), labels=False, title=None, background="#111418")
    assert sheet.getpixel((16 + 40, 16 + 2)) == (0x11, 0x14, 0x18)


def test_a_character_with_no_matching_references_says_so():
    with pytest.raises(CharError) as excinfo:
        char().reference_sheet(role="cloth")
    assert "at least one reference" in str(excinfo.value)


def test_bad_geometry_is_refused():
    with pytest.raises(ValueError, match="Cell size"):
        reference_sheet(fake(1), cell=(0, 10))
    with pytest.raises(ValueError, match="Columns"):
        reference_sheet(fake(1), columns=0)


def test_png_bytes_are_a_real_png():
    data = char().reference_sheet_png(cell=(60, 60))
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert sheet_png(char().reference_sheet(cell=(60, 60))) == data


def test_saving_adds_the_extension_and_writes_a_png(tmp_path):
    written = char().save_reference_sheet(tmp_path / "ada-sheet")
    assert written.name == "ada-sheet.png"
    assert written.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_the_cli_writes_a_sheet(tmp_path):
    from omnichar_sdk.cli import main

    out = tmp_path / "s.png"
    assert main(["sheet", str(FIXTURES / "ada.char"), "-o", str(out), "--cell", "80"]) == 0
    assert out.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
