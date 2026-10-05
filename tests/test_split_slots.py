"""Split output contract without requiring torch for image conversion."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.mark.parametrize("count", [0, 2, 9, 11])
def test_nine_slots_preserve_order_and_report_total(count, monkeypatch):
    package = types.ModuleType("split_test_nodes")
    package.__path__ = []
    common = types.ModuleType("split_test_nodes.common")
    common.CATEGORY = "Omnichar"
    common.REFS_INPUT = ("CHARACTER_REFS", {"forceInput": True})
    common.fail_on_change = lambda error: error
    common.to_image = lambda images: images[0]
    for module in (package, common):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    spec = importlib.util.spec_from_file_location(
        "split_test_nodes.split", Path(__file__).resolve().parents[1] / "nodes/split.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    node = module.OmnicharCharacterReferencesSplit()
    assert node.RETURN_NAMES == tuple(f"image_{i}" for i in range(9)) + ("count",)
    assert node.RETURN_TYPES == ("IMAGE",) * 9 + ("INT",)
    references = [types.SimpleNamespace(open=lambda i=i: f"image-{i}") for i in range(count)]
    result = node.split(references)
    expected = tuple(f"image-{i}" for i in range(min(count, 9)))
    assert result == expected + (None,) * (9 - len(expected)) + (count,)
