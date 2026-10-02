# ComfyUI Omnichar Custom Node

Official `.char` integration with ComfyUI.

A `.char` holds a character's reference images, its locked description, and often a trained LoRA.
Characters are built in [Omnichar Studio](https://omnichar.org) on your own GPU, or in
[Omnichar Cloud](https://cloud.omnichar.org).

## Features

- **Character Files**: Open a `.char` built in Omnichar Studio or Cloud
- **Reference Images**: One batch, or one per numbered slot, both from the same resolved set
- **Positions Kept**: Reference order is preserved, because a prompt addresses images by number
- **Conditioning**: Wire a CLIP to get conditioning straight out, or take the prompt as text
- **Trained LoRA**: Applied to MODEL and CLIP when the character carries one
- **Build Characters**: Encode face, body and wardrobe references into a new `.char`, three slots each
- **Python Library**: The reader is a standalone package with no dependencies

## Requirements

- ComfyUI
- Python 3.10+
- `omnichar-sdk` (installed from `requirements.txt`)

## Installation

1. Go to your ComfyUI custom nodes directory:
   ```bash
   cd ComfyUI/custom_nodes
   ```

2. Clone this repository:
   ```bash
   git clone https://github.com/omnichar/ComfyUI-Omnichar
   cd ComfyUI-Omnichar
   ```

3. Install the reader:
   ```bash
   pip install -r requirements.txt
   ```

4. Restart ComfyUI

## Where Characters Live

Put `.char` files in `ComfyUI/models/characters/`. The loader lists whatever is there.

To share one folder with Omnichar Studio, set `INLINE_CHARACTERS_DIR` to its characters directory
and both read the same files.

## Nodes

| Node | Inputs | Outputs |
| --- | --- | --- |
| Load Character | `char`, `char_path` | `char` |
| Decode Character | `char`, `style`, `clip`, `prompt`, `arch`, `max_references`, `size_from`, `fit` | `conditioning`, `references`, `refs`, `sheet`, `prompt` |
| Character Reference | `refs`, `index` | `image`, `role`, `count` |
| Apply Character LoRA | `model`, `clip`, `char`, `strength`, `arch`, `min_key_coverage` | `model`, `clip` |
| Encode Character | `name`, `description`, `resolution`, `face`/`body`/`cloths` (3 slots each) | `char` |
| Save Character | `char`, `filename`, `overwrite` | `path` |

Ready-made graphs are in [`workflows/`](workflows/).

## Python Library

The reader is a standalone package. Install it anywhere, not just in ComfyUI:

```bash
pip install omnichar-sdk
```

See [packages/omnichar-sdk/README.md](packages/omnichar-sdk/README.md).

## License

`packages/omnichar-sdk/` is Apache-2.0, so closed-source tools can read `.char` files.
Everything else is GPL-3.0-or-later, because ComfyUI is.

## Links

- [Omnichar Studio](https://omnichar.org)
- [Omnichar Cloud](https://cloud.omnichar.org)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Report an issue](https://github.com/omnichar/ComfyUI-Omnichar/issues)
