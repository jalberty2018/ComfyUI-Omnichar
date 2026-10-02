"""Every cap in limits.py, each against a file crafted to defeat it.

This package opens archives supplied by strangers inside a host process that has model weights in
memory. A cap without a test proving it fires is a cap nobody knows is wired up.
"""

import json
import struct
import zipfile
import zlib

import pytest
from conftest import FIXTURES, MANIFEST, build
from omnichar_sdk import Character, CharError, Portability, limits, safe_output_name
from omnichar_sdk.lora import measure_portability, read_safetensors_header


def test_symlink_member_is_refused(tmp_path):
    # 0o120777: S_IFLNK. A link in an archive points at a file the archive does not contain.
    target = build(
        tmp_path,
        {"refs/000.png": b"/etc/passwd"},
        attrs={"refs/000.png": (0o120777 << 16)},
    )
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "symbolic link" in str(excinfo.value)
    assert "refs/000.png" in str(excinfo.value)


def test_nested_archive_member_is_refused(tmp_path):
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("payload.bin", b"x" * 64)
    manifest = dict(MANIFEST, text={"path": "text/description.md"})
    target = build(tmp_path, {"text/description.md": inner.read_bytes()}, manifest)
    with pytest.raises(CharError) as excinfo:
        Character.open(target).get_description()
    assert "itself a zip archive" in str(excinfo.value)


def test_oversized_manifest_is_refused_before_it_is_parsed(tmp_path):
    # Incompressible, so this proves the manifest cap rather than the compression-ratio cap. A
    # compressible one trips the ratio check first, which is correct but tests a different rule.
    import os

    fat = dict(MANIFEST, hints=[os.urandom(limits.MAX_MANIFEST_BYTES // 2 + 4096).hex()])
    target = build(tmp_path, {}, fat)
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "byte manifest" in str(excinfo.value)
    assert str(limits.MAX_MANIFEST_BYTES) in str(excinfo.value)
    assert "source you trust" in str(excinfo.value)


def test_a_compressible_oversized_manifest_trips_the_ratio_cap_first(tmp_path):
    fat = dict(MANIFEST, hints=["x" * (limits.MAX_MANIFEST_BYTES * 4)])
    target = build(tmp_path, {}, fat)
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "expands" in str(excinfo.value)


def test_compression_bomb_is_refused(tmp_path):
    # 8 MiB of zeroes deflates to a few kilobytes, far past the ratio a real member reaches.
    target = build(tmp_path, {"refs/000.png": b"\x00" * (8 * 1024 * 1024)})
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "expands" in str(excinfo.value)
    assert str(limits.MAX_COMPRESSION_RATIO) in str(excinfo.value)


def test_too_many_members_is_refused(tmp_path):
    members = {f"scoring/{i:05d}.json": b"{}" for i in range(limits.MAX_MEMBERS + 1)}
    target = build(tmp_path, members)
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert str(limits.MAX_MEMBERS) in str(excinfo.value)


def test_oversized_member_is_refused(tmp_path, monkeypatch):
    # The real cap is gigabytes, so the mechanism is proven against a lowered one.
    monkeypatch.setattr(limits, "MAX_MEMBER_BYTES", 1024)
    monkeypatch.setattr(limits, "MAX_COMPRESSION_RATIO", 10**9)
    target = build(tmp_path, {"refs/000.png": bytes(range(256)) * 16})
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "one file in a character may be" in str(excinfo.value)


def test_total_uncompressed_size_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(limits, "MAX_TOTAL_UNCOMPRESSED_BYTES", 2048)
    monkeypatch.setattr(limits, "MAX_COMPRESSION_RATIO", 10**9)
    members = {f"refs/{i:03d}.png": bytes(range(256)) * 4 for i in range(8)}
    target = build(tmp_path, members)
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "expands to over" in str(excinfo.value)


def test_safetensors_header_length_is_bounded(tmp_path):
    # The declared length is chosen by whoever wrote the file, and costs 8 bytes to inflate.
    forged = struct.pack("<Q", limits.MAX_SAFETENSORS_HEADER_BYTES + 1) + b"{}"
    with pytest.raises(CharError) as excinfo:
        read_safetensors_header(forged, "adapter.safetensors")
    assert "the limit is" in str(excinfo.value)
    assert str(limits.MAX_SAFETENSORS_HEADER_BYTES) in str(excinfo.value)


def test_safetensors_header_shorter_than_declared_is_refused():
    forged = struct.pack("<Q", 4096) + b'{"a":1}'
    with pytest.raises(CharError) as excinfo:
        read_safetensors_header(forged, "adapter.safetensors")
    assert "truncated" in str(excinfo.value)


def test_image_pixel_cap_is_applied_before_decode(tmp_path):
    from PIL import Image

    def chunk(tag, data):
        body = tag + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + body + crc

    # A PNG that claims 40000x40000 (1.6 gigapixels) in 70 bytes of file.
    ihdr = struct.pack(">IIBBBBB", 40000, 40000, 8, 2, 0, 0, 0)
    bomb = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )
    manifest = dict(
        MANIFEST,
        refs=[{"path": "refs/000.png", "sha256": "", "width": 40000, "height": 40000}],
    )
    target = build(tmp_path, {"refs/000.png": bomb}, manifest)
    ref = Character.open(target).get_references()[0]
    with pytest.raises(Image.DecompressionBombError):
        ref.open()
    assert Image.MAX_IMAGE_PIXELS == limits.MAX_IMAGE_PIXELS


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../../etc/cron.d/backdoor",
        "/etc/passwd",
        "..\\..\\Windows\\System32\\evil",
        "....//....//escape",
        "adapter/../../../../../../tmp/pwned",
    ],
)
def test_output_names_cannot_escape_their_directory(hostile):
    safe = safe_output_name(hostile)
    assert "/" not in safe and "\\" not in safe
    assert not safe.startswith(".")
    assert safe.endswith(".safetensors")


def test_output_name_length_is_bounded():
    assert len(safe_output_name("A" * 5000)) <= limits.MAX_OUTPUT_NAME_BYTES + len(".safetensors")


def test_save_to_writes_inside_the_directory(tmp_path):
    lora = Character.open(FIXTURES / "ada.char").get_lora()
    written = lora.save_to(tmp_path, "../../escape.safetensors")
    assert written.parent == tmp_path.resolve()
    assert written.read_bytes() == lora.bytes()


def test_cli_extract_names_files_itself_not_from_the_archive(tmp_path):
    from omnichar_sdk.cli import main

    assert main(["extract", str(FIXTURES / "ada.char"), "-o", str(tmp_path)]) == 0
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert written == [
        "Ada-z-image.safetensors",
        "description.md",
        "refs/000_face.png",
        "refs/001_body.png",
    ]


def test_a_newer_format_version_is_refused(tmp_path):
    future = dict(MANIFEST, format_version=2)
    target = build(tmp_path, {}, future)
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "character format 2" in str(excinfo.value)
    assert "Update to open it" in str(excinfo.value)


def test_a_file_that_is_not_a_char_is_refused(tmp_path):
    target = tmp_path / "notachar.char"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"magic": "SOMETHINGELSE"}))
    with pytest.raises(CharError) as excinfo:
        Character.open(target)
    assert "does not start with the character signature" in str(excinfo.value)


def test_incompatible_adapter_keys_are_measured_not_assumed():
    verdict, reason = measure_portability(
        "flux2", ["transformer_blocks.0.attn.to_q.lora_A.weight"]
    )
    assert verdict is Portability.INCOMPATIBLE
    assert "Retrain" in reason

    verdict, reason = measure_portability("flux2", ["double_blocks.0.img_attn.qkv.lora_A.weight"])
    assert verdict is Portability.PORTABLE

    verdict, _ = measure_portability("ltx-2-5", ["transformer_blocks.0.attn.to_q.lora_A.weight"])
    assert verdict is Portability.UNMEASURED


def _nested_zip(tmp_path, name="inner.zip"):
    inner = tmp_path / name
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("payload.bin", b"x" * 64)
    return inner.read_bytes()


def test_a_nested_archive_hidden_in_an_adapter_is_refused(tmp_path):
    # This member is only ever read as a prefix, so it would miss a check applied to whole reads.
    manifest = dict(
        MANIFEST,
        payloads={
            "z-image-lora": {
                "type": "lora", "base": "b", "strength": 1.0, "training": {},
                "files": [{"path": "payloads/z-image-lora/adapter.safetensors"}],
            }
        },
    )
    target = build(
        tmp_path, {"payloads/z-image-lora/adapter.safetensors": _nested_zip(tmp_path)}, manifest
    )
    with pytest.raises(CharError) as excinfo:
        Character.open(target).get_lora()
    assert "itself a zip archive" in str(excinfo.value)


def test_a_nested_archive_hidden_in_a_payload_image_is_refused(tmp_path):
    # Payload entries record no size, so this member is read as a 24 byte PNG header probe.
    manifest = dict(
        MANIFEST,
        payloads={
            "flux2-klein": {
                "type": "ref",
                "files": [{"path": "payloads/flux2-klein/ref_000.png", "role": "face"}],
            }
        },
    )
    target = build(
        tmp_path, {"payloads/flux2-klein/ref_000.png": _nested_zip(tmp_path)}, manifest
    )
    with pytest.raises(CharError) as excinfo:
        Character.open(target).get_references(arch="flux2-klein")
    assert "itself a zip archive" in str(excinfo.value)
