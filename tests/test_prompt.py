"""The prompt port, pinned byte for byte to Omnichar Studio's own output.

A model resolves the phrasing it was tuned on, so "close enough" is a regression here.
"""

import json

import pytest
from conftest import FIXTURES
from omnichar_char import Character, prompt_prefix

GOLDEN = json.loads((FIXTURES / "prompt_golden.json").read_text())
NAME = "Ada"


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: f"{c['style']}-n{c['n']}-f{c['first']}")
def test_matches_omnichar_byte_for_byte(case):
    assert (
        prompt_prefix(
            NAME,
            case["desc"],
            case["roles"],
            first_position=case["first"],
            style=case["style"],
            role_lines=case["role_lines"],
        )
        == case["out"]
    )


def test_golden_covers_every_style():
    assert {c["style"] for c in GOLDEN} == {"ordinal", "token", "at-image", "description-only"}


def test_description_only_drops_positions_even_with_references():
    out = prompt_prefix(
        NAME, "A dark haired woman.", ["face", "body"], style="description-only"
    )
    assert out == "A dark haired woman. "


def test_unknown_style_names_the_valid_ones():
    with pytest.raises(ValueError) as excinfo:
        prompt_prefix(NAME, "x", ["face"], style="sdxl")
    assert "ordinal" in str(excinfo.value) and "token" in str(excinfo.value)


def test_from_a_real_character():
    char = Character.open(FIXTURES / "ada.char")
    text = char.get_prompt(style="token")
    assert text.startswith("<Picture 1> <Picture 2> show Ada, the same character in every image.")
    assert "scar through her left eyebrow." in text
