"""Encoding a character, and whether Omnichar Studio would accept the result."""

import pytest
from omnichar_sdk import (
    FLUX2_KLEIN_ARCH,
    MINIMAX_H3_ARCH,
    Character,
    CharError,
    charfile,
    encode_character,
    normalise_reference,
    write,
)
from PIL import Image


def imgs():
    return [
        (Image.new("RGB", (900, 1200), (200, 120, 90)), "face"),
        (Image.new("RGB", (1400, 900), (90, 140, 200)), "body"),
        (Image.new("RGB", (800, 800), (120, 200, 120)), "cloth"),
    ]


def test_originals_are_stored_untouched():
    # Everything else is derived from them, so a resized original poisons every later rebuild.
    doc = encode_character("Ada", "d", imgs())
    char = Character.from_bytes(_bytes(doc))
    sizes = [(r.width, r.height) for r in char.get_references()]
    assert sizes == [(900, 1200), (1400, 900), (800, 800)]


def _bytes(doc, tmp=None):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        return write(Path(d) / "c.char", doc).read_bytes()


def test_roles_are_ordered_face_body_cloth():
    # Position is what a prompt names, so the ordering cannot depend on wiring order.
    shuffled = [imgs()[2], imgs()[1], imgs()[0]]
    doc = encode_character("Ada", "d", shuffled)
    assert [charfile.role_of(r) for r in doc.manifest.refs] == ["face", "body", "cloth"]


def test_a_reference_set_is_compiled_for_each_arch():
    doc = encode_character("Ada", "d", imgs())
    assert sorted(doc.manifest.payloads) == [FLUX2_KLEIN_ARCH, MINIMAX_H3_ARCH]
    for arch in (FLUX2_KLEIN_ARCH, MINIMAX_H3_ARCH):
        assert charfile.payload_valid(doc.manifest, arch, "1"), arch


def test_the_payload_fingerprint_matches_so_nothing_rebuilds():
    doc = encode_character("Ada", "d", imgs())
    payload = doc.manifest.payloads[FLUX2_KLEIN_ARCH]
    assert payload["source_sha256"] == charfile.refs_fingerprint(doc.manifest, payload["policy"])


@pytest.mark.parametrize(
    ("size", "policy", "expected"),
    [
        ((2048, 2048), {"max_pixels": 1024 * 1024, "multiple_of": 16}, (1024, 1024)),
        ((900, 1200), {"max_pixels": 1024 * 1024, "multiple_of": 16}, (880, 1168)),
        ((512, 512), {"short_edge": 2048, "multiple_of": 32}, (2048, 2048)),
    ],
)
def test_normalisation_follows_the_model_budget(size, policy, expected):
    assert normalise_reference(Image.new("RGB", size), policy).size == expected


def test_an_over_wide_reference_is_refused_for_a_model_with_an_aspect_limit():
    with pytest.raises(CharError) as excinfo:
        policy = {"short_edge": 2048, "multiple_of": 32, "max_aspect": 4.0}
        normalise_reference(Image.new("RGB", (4000, 400)), policy)
    assert "Crop it closer to square" in str(excinfo.value)


def test_resolution_lowers_what_is_stored_but_not_the_originals():
    # resolution caps area, not an edge: 256 means a 256x256 budget, so a wide reference stays
    # wide and gets shorter. This matches Omnichar Studio's own capped_policy.
    doc = encode_character("Ada", "d", imgs(), resolution=256)
    char = Character.from_bytes(_bytes(doc))
    assert char.get_references()[0].width == 900
    compiled = char.get_references(arch=FLUX2_KLEIN_ARCH)
    assert all(r.width * r.height <= 256 * 256 for r in compiled)
    assert max(r.width for r in compiled) > 256


def test_the_description_round_trips():
    doc = encode_character("Ada", "  A woman with  short dark hair.  ", imgs())
    assert Character.from_bytes(_bytes(doc)).get_description() == "A woman with  short dark hair."


def test_encoding_nothing_is_refused():
    with pytest.raises(CharError, match="at least one reference"):
        encode_character("Ada", "d", [])


def test_a_written_character_reads_back_identically(tmp_path):
    doc = encode_character("Ada", "A woman.", imgs())
    path = write(tmp_path / "ada.char", doc)
    again = charfile.read(path)
    assert again.manifest.to_json() == doc.manifest.to_json()
    assert again.members == doc.members


def test_the_writer_is_atomic_and_leaves_no_part_file(tmp_path):
    write(tmp_path / "ada.char", encode_character("Ada", "d", imgs()))
    assert [p.name for p in tmp_path.iterdir()] == ["ada.char"]


def test_a_fresh_character_carries_no_scoring_vectors():
    # Identity scoring needs face encoders this package does not ship; the file still applies.
    assert encode_character("Ada", "d", imgs()).manifest.scoring == {}
