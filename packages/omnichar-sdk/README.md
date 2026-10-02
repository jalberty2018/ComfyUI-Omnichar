# omnichar-sdk

Read Omnichar Studio `.char` character files from Python.

A `.char` holds a character's reference images, its locked description, and often a trained LoRA.
This package opens one and hands back those parts. It reads; it never writes.

```python
from omnichar_sdk import Character

char = Character.open("Ada.char")

char.get_description()                       # the locked description
char.get_references(arch="flux2-klein")      # the compiled reference set, in prompt order
char.get_lora()                              # the trained adapter, with a portability verdict
char.get_prompt(style="ordinal")             # text that binds the character to its positions
char.save_reference_sheet("ada.png")         # all the references as one numbered PNG
```

## Reference sheets

`reference_sheet()` lays the references out in a grid and numbers each cell. The numbers are the
point: a position is what a prompt refers to, so a sheet without them cannot be checked against
the prompt it belongs to. Pass the same `first_position` to both and they agree.

```python
char.reference_sheet(arch="flux2-klein", first_position=1)  # a PIL image
char.reference_sheet_png()                                  # PNG bytes
char.save_reference_sheet("out/ada.png")                    # writes it, adds .png if missing
```

It takes the same `arch`, `role`, `limit` and `origin` filters as `get_references`, plus
`columns`, `cell`, `fit`, `labels` and `background`. It needs the `images` extra.

## Install

```
pip install omnichar-sdk              # reads everything; needs only the standard library
pip install 'omnichar-sdk[images]'    # adds Pillow, for decoding and resizing references
```

The base install has no dependencies on purpose. It is meant to drop into ComfyUI, A1111, SwarmUI
or a batch job without competing with whatever that host has pinned, so it never converts images to
tensors. That belongs to the host.

## From a shell

```
omnichar-sdk inspect Ada.char --json
omnichar-sdk extract Ada.char -o out/
omnichar-sdk prompt Ada.char --style token
```

`inspect --json` prints the whole character record, so a tool in any language can read a `.char`
through this command without a Python binding.

## The format

`docs/char-format.md` in this repository describes the container and the manifest well enough to
write a reader in another language.

## Licence

Apache-2.0. The rest of the repository, including the node pack, is GPL-3.0-or-later.
