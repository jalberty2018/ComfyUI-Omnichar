"""The ComfyUI node pack, against a stub of the parts of ComfyUI it touches."""

import shutil
import sys
from pathlib import Path

import pytest
from comfystub import FakeClip, FakeModel, install
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
    # Restored afterwards: dropping omnichar_sdk permanently would leave later tests patching a
    # stale module object, and a size cap that silently stops applying is worse than a failure.
    saved = {n: m for n, m in sys.modules.items() if n.startswith("omnichar_sdk")}
    for name in list(saved):
        del sys.modules[name]
    sys.path.insert(0, str(ROOT / "packages/omnichar-sdk/src"))
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
    assert len(module.NODE_CLASS_MAPPINGS) == 5
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
    ]["char"][0]
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
    from omnichar_sdk import CharError

    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    with pytest.raises(CharError) as excinfo:
        loader.load("Ada.char", override)
    assert "outside the character directories" in str(excinfo.value)


def test_char_path_inside_a_registered_directory_is_allowed(pack):
    module, models = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("", str(models / "characters" / "Ada.char"))
    assert char.name == "Ada"


def test_applying_a_lora_the_model_cannot_receive_is_refused(pack):
    module, _ = pack
    from omnichar_sdk import CharError

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


def test_decode_character_gives_conditioning_references_and_a_sheet(pack):
    module, _ = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    clip = FakeClip()

    cond, refs, sheet, prompt = module.NODE_CLASS_MAPPINGS["OmnicharDecodeCharacter"]().decode(
        char, "ordinal", clip, "in the rain"
    )
    assert prompt.startswith("Images 1 and 2 show Ada,")
    assert prompt.endswith("in the rain")
    # The prompt reaches the encoder, which is the whole reason this node takes a CLIP.
    assert clip.seen == prompt
    assert cond[0][0].startswith("cond:Images 1 and 2")
    assert refs.shape[0] == 2
    assert sheet.shape[0] == 1 and sheet.shape[3] == 3


def test_encode_character_round_trips_through_save_and_load(pack, tmp_path):
    import torch

    module, models = pack
    face = torch.rand(1, 96, 64, 3)
    body = torch.rand(2, 72, 128, 3)

    (char,) = module.NODE_CLASS_MAPPINGS["OmnicharEncodeCharacter"]().encode(
        "Bo", "A tall man with a shaved head.", 512, face=face, body=body
    )
    assert char.name == "Bo"
    assert [r.role for r in char.get_references()] == ["face", "body", "body"]
    # Compiled for both reference archs, so it applies without a rebuild.
    assert char.get_info().ref_archs == ["flux2-klein", "minimax-h3"]

    (path,) = module.NODE_CLASS_MAPPINGS["OmnicharSaveCharacter"]().save(char, "bo")
    written = Path(path)
    assert written.name == "bo.char" and written.parent == (models / "characters")

    from omnichar_sdk import Character

    assert Character.open(written).get_description() == "A tall man with a shaved head."


def test_saving_refuses_to_clobber_unless_told(pack):
    module, _ = pack
    from omnichar_sdk import CharError

    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")
    save = module.NODE_CLASS_MAPPINGS["OmnicharSaveCharacter"]()
    with pytest.raises(CharError) as excinfo:
        save.save(char, "Ada.char")
    assert "already exists" in str(excinfo.value)
    assert save.save(char, "Ada.char", overwrite=True)[0].endswith("Ada.char")


def test_encode_with_no_images_says_what_to_wire(pack):
    module, _ = pack
    from omnichar_sdk import CharError

    with pytest.raises(CharError) as excinfo:
        module.NODE_CLASS_MAPPINGS["OmnicharEncodeCharacter"]().encode("X", "", 512)
    assert "at least one reference" in str(excinfo.value)


def test_the_shipped_workflows_match_the_nodes(pack):
    """A workflow that names a node we no longer register is a broken download."""
    import json

    for path in sorted((ROOT / "workflows").glob("*.json")):
        wf = json.loads(path.read_text())
        for node in wf["nodes"]:
            cls = module_for(pack, node["type"])
            if cls is None:
                continue
            spec = cls.INPUT_TYPES()
            widgets = [
                k
                for k, v in list(spec.get("required", {}).items())
                + list(spec.get("optional", {}).items())
                if not (isinstance(v[0], str) and v[0] in ("CHARACTER", "MODEL", "CLIP", "IMAGE"))
            ]
            values = node.get("widgets_values", [])
            assert len(values) <= len(widgets), f"{path.name}: {node['type']} {values} vs {widgets}"


def module_for(pack, node_type):
    module, _ = pack
    return module.NODE_CLASS_MAPPINGS.get(node_type)


def test_decode_works_with_no_clip_so_no_checkpoint_is_needed(pack):
    module, _ = pack
    loader = module.NODE_CLASS_MAPPINGS["OmnicharLoadCharacter"]()
    (char,) = loader.load("Ada.char")

    cond, refs, sheet, prompt = module.NODE_CLASS_MAPPINGS["OmnicharDecodeCharacter"]().decode(
        char, "ordinal"
    )
    # Decoding is extraction, so it must not require a model to be loaded first.
    assert cond is None
    assert refs.shape[0] == 2 and sheet.shape[0] == 1
    assert prompt.startswith("Images 1 and 2 show Ada,")


def test_encode_takes_several_images_per_role(pack):
    """A ComfyUI input takes one link, so each role needs more than one slot."""
    import torch

    module, _ = pack
    (char,) = module.NODE_CLASS_MAPPINGS["OmnicharEncodeCharacter"]().encode(
        "Bo",
        "A tall man.",
        512,
        face=torch.rand(1, 96, 64, 3),
        face_2=torch.rand(1, 96, 64, 3),
        face_3=torch.rand(1, 96, 64, 3),
        body=torch.rand(1, 72, 128, 3),
        cloths_2=torch.rand(1, 64, 64, 3),
    )
    # Slots and batches both contribute, and roles stay grouped face then body then cloth.
    assert [r.role for r in char.get_references()] == ["face", "face", "face", "body", "cloth"]


def test_a_batch_in_one_slot_still_counts_as_several_references(pack):
    import torch

    module, _ = pack
    (char,) = module.NODE_CLASS_MAPPINGS["OmnicharEncodeCharacter"]().encode(
        "Bo", "A tall man.", 512, face=torch.rand(4, 96, 64, 3)
    )
    assert [r.role for r in char.get_references()] == ["face"] * 4
