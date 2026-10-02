"""The ComfyUI node pack, against a stub of the parts of ComfyUI it touches."""

import shutil
import sys
from pathlib import Path

import pytest
from comfystub import FakeModel, install
from conftest import FIXTURES

ROOT = Path(__file__).resolve().parents[1]

DOUBLE = [f"transformer_blocks.0.attn.{p}" for p in ("to_q", "to_k", "to_v", "to_out.0")]


@pytest.fixture
def pack(tmp_path, monkeypatch):
    """The pack, loaded fresh against a stub ComfyUI whose models dir is empty but real."""
    models = tmp_path / "models"
    (models / "characters").mkdir(parents=True)
    (models / "loras").mkdir(parents=True)
    shutil.copy(FIXTURES / "ada.char", models / "characters" / "Ada.char")
    install(models, unet_stems=DOUBLE)
    monkeypatch.syspath_prepend(str(ROOT.parent))
    # Restored afterwards: dropping omnichar_char permanently would leave later tests patching a
    # stale module object, and a size cap that silently stops applying is worse than a failure.
    saved = {n: m for n, m in sys.modules.items() if n.startswith("omnichar_char")}
    for name in list(saved):
        del sys.modules[name]
    sys.path.insert(0, str(ROOT / "packages/omnichar-char/src"))
    for name in [m for m in list(sys.modules) if "nodes." in m or m.endswith(".nodes")]:
        del sys.modules[name]
    import importlib

    spec = importlib.util.spec_from_file_location(
        "omnichar_pack", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["omnichar_pack"] = module
    spec.loader.exec_module(module)
    yield module, models
    sys.modules.update(saved)


def test_every_node_registers_with_a_display_name(pack):
    module, _ = pack
    assert len(module.NODE_CLASS_MAPPINGS) == 8
    assert set(module.NODE_CLASS_MAPPINGS) == set(module.NODE_DISPLAY_NAME_MAPPINGS)


def test_every_character_input_is_forced_to_a_socket(pack):
    module, _ = pack
    for name, cls in module.NODE_CLASS_MAPPINGS.items():
        spec = cls.INPUT_TYPES()
        for group in ("required", "optional"):
            for field, definition in spec.get(group, {}).items():
                if definition[0] == "CHARACTER":
                    # Without forceInput the frontend draws a widget for a type it does not know.
                    assert definition[1].get("forceInput") is True, f"{name}.{field}"


def test_the_loader_lists_and_opens_a_character(pack):
    module, _ = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    assert "Ada.char" in module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"].INPUT_TYPES()[
        "required"
    ]["character"][0]
    (char,) = loader.load("Ada.char")
    assert char.name == "Ada"


def test_is_changed_is_a_stat_not_a_hash(pack):
    module, models = pack
    cls = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]
    stamp = cls.IS_CHANGED("Ada.char")
    assert isinstance(stamp, tuple) and len(stamp) == 2
    target = models / "characters" / "Ada.char"
    target.touch()
    assert cls.IS_CHANGED("Ada.char") != stamp


@pytest.mark.parametrize(
    "override",
    ["/etc/passwd", "../../../../etc/shadow", "~/.ssh/id_rsa"],
)
def test_char_path_cannot_read_outside_the_character_directories(pack, override):
    module, _ = pack
    from omnichar_char import CharError

    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    with pytest.raises(CharError) as excinfo:
        loader.load("Ada.char", override)
    assert "outside the character directories" in str(excinfo.value)


def test_char_path_inside_a_registered_directory_is_allowed(pack):
    module, models = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("", str(models / "characters" / "Ada.char"))
    assert char.name == "Ada"


def test_references_batch_is_one_tensor_and_the_list_is_many(pack):
    module, _ = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")

    batch, count = module.NODE_CLASS_MAPPINGS["OmnicharCharacterReferences"]().load(
        char, "originals", "any", 0, "largest", "pad"
    )
    assert count == 2
    # common_size returns (width, height); the largest by area is the 128x72 reference, so the
    # batch is 72 high and 128 wide and the taller reference is letterboxed into it.
    assert batch.shape == (2, 72, 128, 3)

    images, n = module.NODE_CLASS_MAPPINGS["OmnicharCharacterReferenceList"]().load(
        char, "originals", "any", 0
    )
    assert n == 2
    assert [tuple(img.shape) for img in images] == [(1, 96, 64, 3), (1, 72, 128, 3)]


def test_reference_at_reports_the_last_valid_index(pack):
    module, _ = pack
    from omnichar_char import CharError

    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    node = module.NODE_CLASS_MAPPINGS["OmnicharCharacterReferenceAt"]()
    image, role = node.load(char, "originals", 1)
    assert role == "body"
    with pytest.raises(CharError) as excinfo:
        node.load(char, "originals", 9)
    assert "The last one is 1" in str(excinfo.value)


def test_prompt_node_appends_the_users_text(pack):
    module, _ = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    (text,) = module.NODE_CLASS_MAPPINGS["OmnicharCharacterPrompt"]().build(
        char, "ordinal", 1, "in the rain"
    )
    assert text.startswith("Images 1 and 2 show Ada,")
    assert text.endswith("in the rain")


def test_applying_a_lora_the_model_cannot_receive_is_refused(pack):
    module, _ = pack
    from omnichar_char import CharError

    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    node = module.NODE_CLASS_MAPPINGS["OmnicharApplyCharacterLoRA"]()

    # A model with none of the adapter's modules.
    with pytest.raises(CharError) as excinfo:
        node.apply(FakeModel(["something.else"]), char, -1.0)
    message = str(excinfo.value)
    assert "0 of 1 modules" in message
    assert "0%" in message and "90%" in message
    assert "near miss" in message
    assert "lower min_key_coverage" in message


def test_applying_a_lora_the_model_accepts_uses_the_recorded_strength(pack):
    module, _ = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    node = module.NODE_CLASS_MAPPINGS["OmnicharApplyCharacterLoRA"]()
    model, _clip = node.apply(FakeModel(DOUBLE), char, -1.0)
    # -1 means "the strength the character recorded", which the fixture sets to 0.8.
    assert model[2] == pytest.approx(0.8)


def test_exporting_writes_into_the_loras_folder(pack):
    module, models = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    name, strength = module.NODE_CLASS_MAPPINGS["OmnicharExportCharacterLoRA"]().export(char)
    assert name == "Ada-z-image.safetensors"
    assert (models / "loras" / name).is_file()
    assert strength == pytest.approx(0.8)


def test_validate_inputs_applies_the_caps(pack, tmp_path):
    module, models = pack
    from conftest import MANIFEST, build

    cls = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]
    assert cls.VALIDATE_INPUTS("Ada.char") is True

    # This runs on every queue, before the node does, and was the one path that skipped limits.py.
    bomb = build(tmp_path, {"refs/000.png": b"\x00" * (8 * 1024 * 1024)}, MANIFEST)
    planted = models / "characters" / "bomb.char"
    planted.write_bytes(bomb.read_bytes())
    message = cls.VALIDATE_INPUTS("bomb.char")
    assert message is not True
    assert "expands" in message


def test_validate_inputs_rejects_a_path_outside_the_character_directories(pack):
    module, _ = pack
    cls = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]
    message = cls.VALIDATE_INPUTS("Ada.char", "/etc/passwd")
    assert message is not True
    assert "outside the character directories" in message
