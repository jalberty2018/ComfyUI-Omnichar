"""Browser transfer integration tests with HTTP and the real character SDK."""

import asyncio
import importlib.util
import io
import math
import sys
import types
from pathlib import Path

import pytest
from aiohttp import FormData, web
from aiohttp.test_utils import TestClient, TestServer
from omnichar_sdk import CharError

from conftest import FIXTURES


@pytest.fixture
def external(monkeypatch, tmp_path):
    package = types.ModuleType("external_test_nodes")
    package.__path__ = []
    common = types.ModuleType("external_test_nodes.common")
    common.CATEGORY = "Omnichar"
    common.CHARACTER = "CHARACTER"
    common.CHARACTER_INPUT = ("CHARACTER", {"forceInput": True})
    folders = types.ModuleType("folder_paths")
    folders.get_input_directory = lambda: str(tmp_path / "input")
    folders.get_temp_directory = lambda: str(tmp_path / "temp")
    for module in (package, common, folders):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    spec = importlib.util.spec_from_file_location(
        "external_test_nodes.external",
        Path(__file__).resolve().parents[1] / "nodes/external.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def client_for(external, limit=1024 * 1024):
    routes = web.RouteTableDef()
    external.register_routes(routes)
    app = web.Application(client_max_size=limit)
    app.add_routes(routes)
    return TestClient(TestServer(app))


@pytest.mark.parametrize("name,expected", [("Ada", "Ada.char"), ("Ada.char", "Ada.char"), ("../Ada", "Ada.char")])
def test_encode_filename_connects_directly_to_download(external, monkeypatch, name, expected):
    from PIL import Image

    common = sys.modules["external_test_nodes.common"]
    monkeypatch.setattr(common, "from_image", lambda images: images, raising=False)
    def unexpected_audio(*args):
        raise AssertionError("Encoding without voice must not convert audio")

    monkeypatch.setattr(common, "audio_to_voice", unexpected_audio, raising=False)
    monkeypatch.setitem(sys.modules, "external_test_nodes.folders", types.ModuleType("external_test_nodes.folders"))
    spec = importlib.util.spec_from_file_location(
        "external_test_nodes.encode", Path(__file__).resolve().parents[1] / "nodes/encode.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    node = module.OmnicharEncodeCharacter()
    assert node.RETURN_TYPES == ("CHARACTER", "STRING")
    assert node.RETURN_NAMES == ("char", "filename")
    char, filename = node.encode(name, "A character", 64, face=[Image.new("RGB", (64, 64))])
    assert filename == expected
    assert char.name == name
    saved = external.OmnicharSaveCharacterExternal().save(char, filename)
    assert saved["result"] == (expected,)


async def upload(client, data, filename="Ada.char"):
    form = FormData()
    form.add_field("file", data, filename=filename, content_type="application/octet-stream")
    return await client.post("/omnichar/upload", data=form)


def test_upload_load_save_download_preserves_entire_archive(external):
    async def run():
        data = (FIXTURES / "ada.char").read_bytes()
        async with client_for(external) as client:
            response = await upload(client, data)
            assert response.status == 200, await response.text()
            uploaded = await response.json()
            loader = external.OmnicharLoadCharacterExternal()
            assert loader.VALIDATE_INPUTS(**uploaded) is True
            char, = loader.load(**uploaded)
            assert char.name == "Ada"
            assert char.to_bytes() == data
            preview = await client.get(f"/omnichar/preview/{uploaded['upload_id']}/{uploaded['filename']}")
            assert preview.status == 200
            assert preview.content_type == "image/png"
            from PIL import Image
            with Image.open(io.BytesIO(await preview.read())) as actual:
                expected = char.get_references()[0].open()
                expected.thumbnail((512, 512), Image.Resampling.LANCZOS)
                assert actual.size == expected.size
                assert actual.tobytes() == expected.tobytes()
            saver = external.OmnicharSaveCharacterExternal()
            saved = saver.save(char, "exported")
            item, = saved["ui"]["omnichar_download"]
            route = f"/omnichar/download/{item['id']}/{item['filename']}"
            assert (await client.head(route)).status == 200
            response = await client.get(route)
            assert response.status == 200
            assert await response.read() == data
            assert response.headers["Content-Disposition"].startswith("attachment;")
            assert saved["result"] == ("exported.char",)
            second = saver.save(char, "exported")
            assert second["ui"]["omnichar_download"][0]["id"] != item["id"]
            assert math.isnan(saver.IS_CHANGED(char, "exported"))
            external.stored_path(external.download_root(), item["id"], item["filename"]).unlink()
            assert (await client.get(route)).status == 404
            # Same-name uploads must not clobber files referenced by other workflows.
            other = await (await upload(client, data)).json()
            assert other["upload_id"] != uploaded["upload_id"]
            assert loader.load(**uploaded)[0].to_bytes() == data
    asyncio.run(run())


@pytest.mark.parametrize("filename,data", [
    ("wrong.zip", b"invalid"), ("broken.char", b"invalid"),
    ("truncated.char", (FIXTURES / "ada-truncated.char").read_bytes()),
])
def test_invalid_uploads_are_rejected_and_removed(external, filename, data):
    async def run():
        async with client_for(external) as client:
            response = await upload(client, data, filename)
            assert response.status == 400
            assert "error" in await response.json()
        assert not list(external.upload_root().rglob("*.char"))
    asyncio.run(run())


def test_upload_limit_cleans_partial_file(external):
    async def run():
        async with client_for(external, limit=32) as client:
            response = await upload(client, b"x" * 100)
            assert response.status == 413
        assert not list(external.upload_root().rglob("*.char"))
    asyncio.run(run())


@pytest.mark.parametrize("token,filename", [
    ("../outside", "Ada.char"), ("a" * 32, "../Ada.char"),
    ("a" * 32, "C:\\outside.char"), ("", "Ada.char"),
])
def test_paths_cannot_escape_transfer_folders(external, token, filename):
    with pytest.raises(CharError):
        external.stored_path(external.upload_root(), token, filename)
    assert external.OmnicharLoadCharacterExternal.VALIDATE_INPUTS(filename, token) is not True


def test_missing_upload_and_download(external):
    loader = external.OmnicharLoadCharacterExternal
    assert loader.VALIDATE_INPUTS("missing.char", "a" * 32) is not True
    assert math.isnan(loader.IS_CHANGED("missing.char", "a" * 32))

    async def run():
        async with client_for(external) as client:
            assert (await client.get('/omnichar/download/invalid/missing.char')).status == 404
            assert (await client.get('/omnichar/preview/invalid/missing.char')).status == 404
            assert (await client.get(f"/omnichar/preview/{'a' * 32}/missing.char")).status == 404
    asyncio.run(run())


def test_preview_without_references(external, tmp_path):
    from conftest import build

    data = build(tmp_path, {}).read_bytes()

    async def run():
        async with client_for(external) as client:
            response = await upload(client, data)
            assert response.status == 200
            item = await response.json()
            response = await client.get(f"/omnichar/preview/{item['upload_id']}/{item['filename']}")
            assert response.status == 404
            assert external.OmnicharLoadCharacterExternal.VALIDATE_INPUTS(**item) is True
    asyncio.run(run())
