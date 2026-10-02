# SPDX-License-Identifier: Apache-2.0
"""Every cap this package enforces, each one blocking a specific attack on an untrusted zip."""

from __future__ import annotations

#: Applied before `json.loads`: an unbounded read of `manifest.json` is memory exhaustion.
MAX_MANIFEST_BYTES = 256 * 1024

#: A character with many references and a rank-32 adapter lands near 1 GiB.
MAX_TOTAL_UNCOMPRESSED_BYTES = 4 * 1024**3

#: The largest legitimate member is an adapter.
MAX_MEMBER_BYTES = 2 * 1024**3

#: References, crops, payloads and scoring files across several archs stay well under.
MAX_MEMBERS = 4096

#: Real members sit near 1:1 and the JSON near 10:1, so anything past this is padding.
MAX_COMPRESSION_RATIO = 200

#: The declared header length is chosen by whoever wrote the file, so bound it before allocating.
MAX_SAFETENSORS_HEADER_BYTES = 16 * 1024 * 1024

#: Applied to Pillow before any reference is decoded.
MAX_IMAGE_PIXELS = 64 * 1024 * 1024

#: Long enough for a character name plus an architecture suffix.
MAX_OUTPUT_NAME_BYTES = 200

#: Asking for the whole cap in one read allocates it, which is the exhaustion the cap prevents.
STREAM_CHUNK_BYTES = 4 * 1024 * 1024

#: A member starting with these is a nested archive, which nothing in this format uses.
ZIP_MAGIC = b"PK\x03\x04"
