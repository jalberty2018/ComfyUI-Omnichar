# The `.char` format

A `.char` file holds one character: the reference images that define it, a written description, and
sometimes a trained LoRA. This document describes the container and the manifest completely enough
to write a reader in any language. It describes format version 1.

## Container

A `.char` is a ZIP archive. Two rules go beyond ordinary ZIP:

1. `manifest.json` is the first member.
2. The manifest's first bytes are `{"magic":"INLINECHAR","format_version":`.

Together these mean a reader can identify a `.char` from the first 32 bytes of the manifest without
parsing JSON, while the manifest stays valid JSON. Writers keep a fixed key order to guarantee it.

PNG members are stored without compression, because they are already compressed. Everything else is
deflated. A reader does not depend on this.

### Members

| Path | Required | Contents |
| --- | --- | --- |
| `manifest.json` | yes | The record below. Always first. |
| `refs/NNN.png` | no | Reference images as the user supplied them, rotation applied, otherwise untouched. |
| `harvested/NNN.png` | no | Generated images approved back into the reference pool. |
| `quarantined/NNN.png` | no | References set aside by verification. Reversible. |
| `derived/face_NNN.png` | no | 512 pixel face crops, generated. |
| `text/description.md` | no | The character description, UTF-8. |
| `payloads/<arch>/ref_NNN.png` | no | References normalised for one model family. |
| `payloads/<arch>-lora/adapter.safetensors` | no | A trained adapter for one model family. |
| `scoring/*.json` | no | Identity vectors. A reader that does not score identity ignores these. |

Member names are always ASCII and always of the form above. A reader must not join a member name
onto an output path: treat the name as data and choose output names itself.

### What is truth and what is cache

`refs/` and `text/description.md` are truth. Everything under `payloads/` and `scoring/` is derived
from them and can be rebuilt. A reader that finds a stale or missing payload has not found a corrupt
file; it has found a cache that needs regenerating, which only a writer can do.

## The manifest

Keys appear in this order. A reader must not depend on the order, only on the first key being
`magic`.

| Key | Type | Required | Meaning |
| --- | --- | --- | --- |
| `magic` | string | yes | Always `INLINECHAR`. |
| `format_version` | integer | yes | `1`. See below. |
| `char_id` | string | yes | A UUID, stable across edits. |
| `name` | string | yes | The display name. The filename is separate and may differ. |
| `created_at` | integer | yes | Unix seconds. |
| `modified_at` | integer | yes | Unix seconds. |
| `app` | string | yes | The writing application. `inline-studio` for files written by Omnichar Studio, which kept its original internal name. |
| `app_version` | string | no | The writing application's version. |
| `refs` | array | yes | Reference records. May be empty. |
| `derived` | array | no | Generated crop records, same shape as `refs`. |
| `text` | object | no | `{"path": "text/description.md", "sha256": "..."}`. |
| `payloads` | object | no | Architecture key to payload record. |
| `scoring` | object | no | Identity vectors and encoder versions. |
| `hints` | array of strings | no | Advice for improving the character. |
| `apply` | object | no | Architecture key to `"reference"` or `"lora"`. Absent means the reader chooses. |
| `reserved` | object | no | See Reserved. |

### A reference record

```json
{
  "path": "refs/000.png",
  "sha256": "a5f3...",
  "width": 1024,
  "height": 1536,
  "source_name": "ada-portrait.png",
  "origin": "original",
  "role": "face"
}
```

`path` and `sha256` are required. `origin` is `original` or `harvested`, and **absent means
`original`**. `role` is `face`, `body` or `cloth`, and **absent means `face`**. An unrecognised role
reads as `face` rather than raising: a manifest is user data, and refusing to open a character over
one bad string helps nobody.

`width` and `height` are present on entries under `refs`. They are **not** present on payload file
entries, so a reader that needs the dimensions of a payload image reads them from the PNG's IHDR
chunk, at byte offset 16 for width and 20 for height.

### A reference payload record

```json
{
  "payload_version": 1,
  "type": "ref",
  "encoder": { "id": "flux2-klein-refset", "version": "1" },
  "source_sha256": "...",
  "policy": { "max_pixels": 1048576, "multiple_of": 16 },
  "harvested_count": 0,
  "files": [
    { "path": "payloads/flux2-klein/ref_000.png", "sha256": "...", "role": "face" }
  ]
}
```

The key is the architecture alone. Known values are `flux2-klein`, `minimax-h3` and `fal-ref`, each
with its own `policy` describing how references were resized for it.

`source_sha256` is a fingerprint of the **original** references and the policy, in order. A reader
that wants to know whether the payload is current recomputes it: SHA-256 over the `sha256` of every
reference whose origin is `original`, in manifest order, then the policy serialised as compact JSON
with sorted keys, all joined by the byte `0x1F`. Harvested references are deliberately excluded.

### A LoRA payload record

```json
{
  "payload_version": 1,
  "type": "lora",
  "encoder": { "id": "z-image-lora", "version": "1" },
  "source_sha256": "...",
  "policy": { "max_pixels": 1048576, "multiple_of": 16 },
  "base": "z-image-turbo",
  "strength": 0.8,
  "training": { "rank": 16, "steps": 600, "resolution": 512 },
  "files": [{ "path": "payloads/z-image-lora/adapter.safetensors", "sha256": "..." }]
}
```

The key is the architecture plus `-lora`, so one architecture can carry both a reference set and an
adapter. `strength` is what the adapter was judged at, and a reader should default to it: an
overfitted adapter is usable only turned down, and nothing else in the file records that.

The adapter is a safetensors file. Its own metadata carries `inline_arch`, `inline_base`,
`inline_rank`, `inline_alpha`, `inline_steps`, `inline_resolution` and `inline_scope`.

**Adapter key names are not uniform across architectures.** Some are written in the published
checkpoint's names and load in other tools; some are written in the diffusers port's names and load
only in Omnichar Studio. A reader that intends to apply an adapter should inspect its tensor names
rather than trusting the architecture label, and should measure how many of them match the target
model before applying any.

### The scoring record

`scoring` holds identity vectors and the encoder versions they came from. A reader that does not
score identity can ignore the whole object, which is why it is not described in the member table
beyond one row.

| Key | Type | Meaning |
| --- | --- | --- |
| `encoders` | array | `[{"id": "sface", "version": "1"}, …]`. Which encoder produced each vector. |
| `centroid_<id>` | object | `{"path": "scoring/centroid_sface.json"}`. The identity centre for one encoder. |
| `embeds_<id>` | object | Per-reference vectors, the gallery a new image is compared against. |
| `originals_<id>` | object | Vectors frozen at verification, so harvesting cannot drift the identity. |
| `harvested_<id>` | object | Vectors for the harvested pool, kept apart from the originals. |
| `flaggedRefs` | array of integers | Reference indices verification set aside. |
| `refFramings` | array of strings | How each reference is framed, such as `face` or `full`. |
| `refCount` | integer | How many references the vectors were computed over. |

Two rules a reader must respect:

- **A vector is only comparable within one encoder build.** Cosine similarity across two builds is
  meaningless, so a reader checks `encoders[].version` before using any vector and recomputes when
  it does not match.
- **`originals_<id>` and `harvested_<id>` are separate on purpose.** Scoring a generated image
  against a gallery that already contains generated images drifts the identity a little further
  each round.

The vector files themselves are JSON arrays of floats. `centroid_sface.json` is 128 numbers and
`centroid_dinov2-base.json` is 768.

## Ordering

**The order of `payloads[<arch>]["files"]` is meaning, not presentation.** Models that accept
several references address them by position: FLUX.2 reads "the jacket in image 2", MiniMax H3 reads
`<Picture 2>`, Seedance reads `@Image2`. A reader that reorders, filters or caps this list changes
which image every position in the prompt refers to. Preserve the order through every operation.

The same applies to `refs`.

## `format_version`

A reader **must refuse** a file whose `format_version` is higher than the version it implements, and
must say so. It must not read the members it recognises and ignore the rest. A later version may
change what an existing key means, so a partial read produces a character that is subtly wrong
rather than one that fails, and nobody investigates a wrong face that renders successfully.

A reader may open any file at or below its own version.

## Reserved

`reserved` holds keys that are written but unused:

| Key | Intended for |
| --- | --- |
| `adapters` | Adapter backends other than LoRA. |
| `video_payloads` | Reference sets for video models. |
| `members` | Multi-character scenes: several identities in one file. |

A reader preserves `reserved` untouched. A writer that drops keys it does not recognise destroys
forward compatibility, and three code paths in Omnichar Studio rewrite a manifest routinely.

**There is no audio in version 1.** No member holds a voice track and no manifest key refers to one.
A character is images and text.

## Reading safely

A `.char` may arrive from anywhere. A reader should:

- Bound the manifest size before parsing it. An unbounded read of a member named `manifest.json` is
  memory exhaustion with no parsing required.
- Bound total uncompressed size, per-member size, member count and compression ratio, all from the
  central directory, before reading any member.
- Reject members that are symbolic links.
- Reject members that are themselves archives. Nothing in this format nests.
- Bound the declared header length of a safetensors member before allocating against it. That
  number is chosen by whoever wrote the file.
- Bound image dimensions before decoding.

The reference implementation keeps all of these in one module, `omnichar_sdk/limits.py`.
