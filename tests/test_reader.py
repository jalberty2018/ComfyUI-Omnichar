"""The reader, against a fixture written by Omnichar Studio's own writer."""

import json

import pytest
from conftest import FIXTURES
from omnichar_char import Character, CharError, Portability


def char():
    return Character.open(FIXTURES / "ada.char")


def test_identity():
    c = char()
    assert c.name == "Ada"
    assert c.char_id == "7c1f0a2e-0000-4000-8000-000000000001"
    assert c.format_version == 1
    assert c.created_at == 1740000000


def test_description_and_hints():
    c = char()
    assert c.get_description().startswith("Ada, a woman in her thirties")
    assert c.get_hints() == ["Add a profile view."]


def test_info():
    info = char().get_info()
    assert info.ref_count == 2
    assert info.ref_archs == ["flux2-klein"]
    assert info.lora_archs == ["z-image"]
    assert info.size_bytes > 0


def test_original_references_keep_manifest_order_and_sizes():
    refs = char().get_references()
    assert [r.path for r in refs] == ["refs/000.png", "refs/001.png"]
    assert [r.role for r in refs] == ["face", "body"]
    assert [(r.width, r.height) for r in refs] == [(64, 96), (128, 72)]
    assert all(r.origin == "original" for r in refs)


def test_payload_references_read_size_from_the_png_header():
    # The real format records no width or height on a payload entry, so these come from IHDR.
    refs = char().get_references(arch="flux2-klein")
    assert [r.path for r in refs] == [
        "payloads/flux2-klein/ref_000.png",
        "payloads/flux2-klein/ref_001.png",
    ]
    assert [(r.width, r.height) for r in refs] == [(48, 72), (96, 54)]


def test_reference_bytes_are_the_hashed_bytes():
    import hashlib

    for ref in char().get_references():
        assert hashlib.sha256(ref.bytes()).hexdigest() == ref.sha256


def test_role_filter():
    assert [r.role for r in char().get_references(role="face")] == ["face"]
    assert char().get_references(role="cloth") == []


def test_origin_filter():
    assert len(char().get_references(origin="original")) == 2
    assert char().get_references(origin="harvested") == []


def test_arch_and_origin_do_not_compose():
    with pytest.raises(ValueError) as excinfo:
        char().get_references(arch="flux2-klein", origin="original")
    message = str(excinfo.value)
    assert "arch or origin, not both" in message
    assert "origin='original'" in message and "arch='flux2-klein'" in message


def test_unknown_arch_names_what_is_available():
    with pytest.raises(CharError) as excinfo:
        char().get_references(arch="minimax-h3")
    assert "flux2-klein" in str(excinfo.value)


def test_missing_file_is_readable():
    with pytest.raises(CharError) as excinfo:
        Character.open(FIXTURES / "does-not-exist.char")
    assert "does not exist" in str(excinfo.value)


def test_truncated_download_is_readable_not_a_badzipfile():
    with pytest.raises(CharError) as excinfo:
        Character.open(FIXTURES / "ada-truncated.char")
    message = str(excinfo.value)
    assert "ada-truncated.char" in message
    assert "download it again" in message


def test_from_bytes_matches_open():
    data = (FIXTURES / "ada.char").read_bytes()
    assert Character.from_bytes(data, "ada.char").get_description() == char().get_description()


def test_lora_is_measured_not_looked_up():
    lora = char().get_lora()
    assert lora is not None
    assert lora.arch == "z-image"
    assert lora.rank == 16 and lora.steps == 600 and lora.resolution == 512
    assert lora.strength == 0.8
    assert lora.portability is Portability.PARTIAL
    assert "210 of 238" in lora.reason
    assert lora.metadata()["inline_base"] == "z-image-turbo"


def test_lora_by_name_and_missing_arch():
    assert char().get_lora("z-image") is not None
    assert char().get_lora("krea2") is None


def test_json_inspect_is_machine_readable(capsys):
    from omnichar_char.cli import main

    assert main(["inspect", str(FIXTURES / "ada.char"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "Ada"
    assert payload["loras"][0]["portability"] == "partial"
    assert len(payload["references"]) == 2


def test_format_version_is_the_files_own_not_the_readers_constant(tmp_path):
    from conftest import MANIFEST, build

    # A v1 file read by a v1 reader is the easy case; the bug was reporting the constant always.
    assert char().format_version == 1
    target = build(tmp_path, {}, dict(MANIFEST, format_version=1))
    assert Character.open(target).get_info().format_version == 1


def test_a_non_zip_blob_in_memory_raises_a_readable_error():
    # from_bytes used to let zipfile.BadZipFile escape, which no caller catches.
    with pytest.raises(CharError) as excinfo:
        Character.from_bytes(b"this is not a zip at all", "pasted.char")
    assert "not a readable character file" in str(excinfo.value)


def test_from_file_refuses_an_endless_stream(monkeypatch):
    import io

    from omnichar_char import character as character_module

    # Patched on the module character.py reads, so a test that reloaded the package cannot leave
    # this pointing at a stale copy and let the real gigabyte cap run.
    limits = character_module.limits
    monkeypatch.setattr(limits, "MAX_TOTAL_UNCOMPRESSED_BYTES", 8192)
    monkeypatch.setattr(limits, "STREAM_CHUNK_BYTES", 1024)

    class Endless(io.RawIOBase):
        def read(self, size=-1):
            return b"\x00" * (size if size and size > 0 else 1024)

    with pytest.raises(CharError) as excinfo:
        Character.from_file(Endless(), "endless.char")
    assert "source you trust" in str(excinfo.value)


def test_from_file_reads_a_real_character(tmp_path):
    with open(FIXTURES / "ada.char", "rb") as handle:
        assert Character.from_file(handle, "ada.char").name == "Ada"
