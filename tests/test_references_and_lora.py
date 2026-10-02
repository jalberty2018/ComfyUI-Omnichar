"""Role allocation, size selection, resizing, and the get_lora arity rules."""

import shutil

import pytest
from conftest import FIXTURES, MANIFEST, build
from omnichar_sdk import (
    Character,
    CharChanged,
    CharError,
    Reference,
    allocate_roles,
    common_size,
    fit_roles,
)


def ref(role, w=100, h=100, i=0):
    return Reference(
        path=f"refs/{i:03d}.png", role=role, origin="original", width=w, height=h, sha256=""
    )


def test_allocate_roles_splits_two_to_one_to_one():
    counts = {"face": 8, "body": 8, "cloth": 8}
    assert allocate_roles(counts, 8) == {"face": 4, "body": 2, "cloth": 2}


def test_allocate_roles_passes_everything_under_the_cap():
    counts = {"face": 2, "body": 1, "cloth": 0}
    assert allocate_roles(counts, 9) == counts


def test_allocate_roles_gives_unfillable_slots_to_roles_that_want_them():
    # No cloth references, so its quarter share goes to the roles that have some.
    share = allocate_roles({"face": 6, "body": 6, "cloth": 0}, 8)
    assert share["cloth"] == 0
    assert sum(share.values()) == 8


def test_fit_roles_divides_rather_than_trimming_the_tail():
    refs = [ref("face", i=i) for i in range(6)] + [ref("body", i=6), ref("cloth", i=7)]
    kept = fit_roles(refs, 4)
    roles = [r.role for r in kept]
    # Trimming the tail would have returned four faces and lost the wardrobe entirely.
    assert "cloth" in roles and "body" in roles
    assert len(kept) == 4


def test_fit_roles_preserves_order_because_order_is_what_the_prompt_numbers():
    refs = [ref("face", i=0), ref("body", i=1), ref("face", i=2), ref("cloth", i=3)]
    kept = fit_roles(refs, 3)
    assert [r.path for r in kept] == sorted(r.path for r in kept)


def test_common_size_policies():
    refs = [ref("face", 64, 96), ref("body", 128, 72), ref("cloth", 32, 32)]
    assert common_size(refs, "first") == (64, 96)
    assert common_size(refs, "largest") == (128, 72)
    assert common_size(refs, "smallest") == (32, 32)


def test_common_size_rejects_an_unknown_policy_and_an_empty_list():
    with pytest.raises(ValueError, match="largest"):
        common_size([ref("face")], "biggest")
    with pytest.raises(ValueError, match="at least one reference"):
        common_size([], "first")


@pytest.mark.parametrize("mode", ["pad", "cover", "stretch"])
def test_fit_returns_the_requested_size(mode):
    refs = Character.open(FIXTURES / "ada.char").get_references()
    out = refs[1].fit((64, 96), mode)
    assert out.size == (64, 96)


def test_pad_letterboxes_rather_than_distorting():
    # A 128x72 reference fitted into a 64x96 box keeps its shape and gains black bands.
    ref_wide = Character.open(FIXTURES / "ada.char").get_references()[1]
    padded = ref_wide.fit((64, 96), "pad")
    assert padded.getpixel((32, 2)) == (0, 0, 0)
    assert padded.getpixel((32, 48)) != (0, 0, 0)


def test_unknown_fit_mode_names_the_valid_ones():
    with pytest.raises(ValueError, match="cover"):
        Character.open(FIXTURES / "ada.char").get_references()[0].fit((10, 10), "squish")


def test_get_lora_with_no_adapters_returns_none(tmp_path):
    assert Character.open(build(tmp_path, {}, MANIFEST)).get_lora() is None


def test_get_lora_with_several_adapters_refuses_to_guess():
    char = Character.open(FIXTURES / "ada.char")
    char.manifest.payloads["krea2-lora"] = {
        "type": "lora", "base": "krea2", "strength": 1.0, "training": {},
        "files": [{"path": "payloads/krea2-lora/adapter.safetensors"}],
    }
    with pytest.raises(CharError) as excinfo:
        char.get_lora()
    message = str(excinfo.value)
    assert "krea2" in message and "z-image" in message
    assert "get_lora(arch=" in message


def test_replacing_the_file_mid_read_raises_rather_than_mixing_versions(tmp_path):
    target = tmp_path / "ada.char"
    shutil.copy(FIXTURES / "ada.char", target)
    char = Character.open(target)
    assert char.get_description().startswith("Ada,")

    # What happens when someone saves in Omnichar Studio while a render is running.
    replacement = build(tmp_path, {}, dict(MANIFEST, name="Someone Else"), name="other.char")
    target.write_bytes(replacement.read_bytes())

    with pytest.raises(CharChanged) as excinfo:
        char.get_description()
    assert "was replaced while it was open" in str(excinfo.value)
    assert "Open it again" in str(excinfo.value)


def test_an_untouched_file_is_not_reported_as_changed(tmp_path):
    target = tmp_path / "ada.char"
    shutil.copy(FIXTURES / "ada.char", target)
    char = Character.open(target)
    for _ in range(3):
        assert char.get_description().startswith("Ada,")
        assert len(char.get_references()) == 2


def test_fit_says_what_to_install_when_pillow_is_missing(monkeypatch):
    """fit() imported PIL above the guard, so it raised a bare ImportError instead of advice."""
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("No module named 'PIL'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    ref = Character.open(FIXTURES / "ada.char").get_references()[0]
    for call in (lambda: ref.open(), lambda: ref.fit((10, 10), "pad")):
        with pytest.raises(CharError) as excinfo:
            call()
        assert "omnichar-sdk[images]" in str(excinfo.value)
