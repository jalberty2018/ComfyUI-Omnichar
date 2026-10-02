# ComfyUI Omnichar Character Nodes

Load Omnichar Studio `.char` character files in ComfyUI. A `.char` holds a character's reference
images, its locked description, and often a trained LoRA.

## Features

- **Character Files**: Open a `.char` built in Omnichar Studio
- **Reference Images**: As one batch, as a list, or one at a time
- **Positions Kept**: Reference order is preserved, because a prompt addresses images by number
- **Prompt Text**: Ordinal, `<Picture N>` and `@ImageN` forms, per model family
- **Trained LoRA**: Applied to MODEL and CLIP, or exported to `models/loras`
- **Refuses a Bad Adapter**: Measures key coverage first, so a half match does not render a near-miss face
- **Python Library**: The reader is a standalone package with no dependencies

## Requirements

- ComfyUI
- Python 3.10+
- `omnichar-char` (installed from `requirements.txt`)

## Installation

### Method 1: Git Clone

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

### Method 2: Manual Installation

1. Download the repository as a ZIP
2. Extract to `ComfyUI/custom_nodes/ComfyUI-Omnichar`
3. Install dependencies: `pip install -r requirements.txt`
4. Restart ComfyUI

## Where Characters Live

Put `.char` files in `ComfyUI/models/characters/`. The loader lists whatever is there.

To share one folder with Omnichar Studio, set `INLINE_CHARACTERS_DIR` to its characters directory
and both read the same files.

## Usage

### Basic Workflow

1. Add **Load Character (.char)** and pick a character
2. Feed its `character` output into the nodes you need:
   - **Character References** for the images
   - **Character Prompt** for text that names the reference positions
   - **Apply Character LoRA** if the character carries a trained adapter
3. Wire the IMAGE and STRING outputs into your model

`examples/character-references.json` is a working graph to start from.

A `CHARACTER` wire only reaches these nodes. That is why references, prompt and LoRA are separate
nodes: each one converts the character into something the rest of ComfyUI understands.

### Nodes

| Node | Inputs | Outputs |
| --- | --- | --- |
| Load Character (.char) | `character`, `char_path` | `CHARACTER` |
| Character Info | `character` | `name`, `description`, `hints`, `ref_count`, `available` |
| Character Prompt | `character`, `style`, `first_position`, `prompt`, `arch`, `role_lines` | `prompt` |
| Character References | `character`, `arch`, `role`, `max_references`, `size_from`, `fit` | `images`, `count` |
| Character Reference List | `character`, `arch`, `role`, `max_references` | `images` (one per ref), `count` |
| Character Reference At | `character`, `arch`, `index` | `image`, `role` |
| Apply Character LoRA | `model`, `character`, `strength`, `clip`, `arch`, `min_key_coverage` | `model`, `clip` |
| Export Character LoRA | `character`, `arch` | `lora_name`, `strength` |

### Node Notes

**Character Prompt** `style` picks the addressing a model was trained on. FLUX.2 reads ordinal
prose, MiniMax H3 reads `<Picture N>`, Seedance reads `@ImageN`. `description-only` drops positions,
which is what a LoRA needs. `first_position` sets the number the first reference gets, so a prompt
and a reference batch can be built at the same offset and agree.

**Character References** needs one size for a batch, so `size_from` picks it and `fit` resizes onto
it: `pad` letterboxes, `cover` crops, `stretch` distorts. Use **Character Reference List** to keep
every reference at its own size, but note it makes the rest of the graph run once per image.

**max_references** divides the slots between face, body and outfit rather than cutting the end of
the list, so a character does not lose its wardrobe when a model takes fewer references than it has.

**Apply Character LoRA** `strength` of `-1` uses the strength the character recorded.

## Python Library

The reader is a standalone package. Install it anywhere, not just in ComfyUI:

```bash
pip install omnichar-char
```

```python
from omnichar_char import Character

char = Character.open("Ada.char")
char.get_description()
char.get_references(arch="flux2-klein")
char.get_lora()
char.get_prompt(style="ordinal")
char.save_reference_sheet("ada.png")
```

The base install is standard library only, so it drops into any host without fighting its pins.
Images need Pillow: `pip install 'omnichar-char[images]'`.

```bash
omnichar-char inspect Ada.char --json
omnichar-char extract Ada.char -o out/
omnichar-char sheet   Ada.char -o ada.png
```

Full API in [packages/omnichar-char/README.md](packages/omnichar-char/README.md).

## Troubleshooting

### Nodes Not Appearing in ComfyUI

The reader is missing. The pack logs the reason at startup and registers nothing rather than
breaking every other pack. Install it with ComfyUI's own Python:

```bash
pip install -r requirements.txt
```

### The Character Dropdown Is Empty

Nothing is in `ComfyUI/models/characters/`. Add a `.char` there and restart, or set
`INLINE_CHARACTERS_DIR`.

### "is outside the character directories this node may read"

`char_path` only opens files inside a registered character directory. Move the file there, or point
`INLINE_CHARACTERS_DIR` at the folder it lives in.

### "matches N of M modules on this model"

The adapter was trained against a different base than the model you loaded. Load the base it names,
or lower `min_key_coverage` to accept a partial result on purpose.

### "The character file changed while this render was running"

The `.char` was saved in Omnichar Studio mid-render. Queue it again.

### "not a readable character file"

The file was truncated in transfer. Download it again.

## Project Structure

```
ComfyUI-Omnichar/
├── __init__.py                  node registration
├── nodes/                       the eight node classes
├── web/                         CHARACTER socket colour
├── examples/                    a working workflow
├── docs/char-format.md          the .char format spec
├── packages/omnichar-char/      the reader, published to PyPI
└── tests/
```

## License

`packages/omnichar-char/` is Apache-2.0, so closed-source tools can read `.char` files.
Everything else is GPL-3.0-or-later, because ComfyUI is.

## Links

- [Omnichar Studio](https://omnichar.org)
- [The `.char` format](docs/char-format.md)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Report an issue](https://github.com/omnichar/ComfyUI-Omnichar/issues)
