"""Enough of ComfyUI to exercise the node pack without a ComfyUI install.

Only the surfaces the pack actually touches: folder_paths, comfy.lora's key maps, and
comfy.sd.load_lora_for_models. Real ComfyUI is still the thing that proves a workflow runs; this
proves the logic around it.
"""

import sys
import types
from pathlib import Path


class FakeModel:
    def __init__(self, stems):
        self.model = types.SimpleNamespace(stems=stems)


def install(models_dir: Path, unet_stems=(), clip_stems=()):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.models_dir = str(models_dir)
    folder_paths.folder_names_and_paths = {"loras": ([str(models_dir / "loras")], {".safetensors"})}

    def get_filename_list(category):
        paths, exts = folder_paths.folder_names_and_paths[category]
        out = []
        for base in paths:
            for path in Path(base).rglob("*"):
                if path.suffix in exts:
                    out.append(path.name)
        return out

    def get_folder_paths(category):
        return list(folder_paths.folder_names_and_paths[category][0])

    def get_full_path(category, name):
        for base in get_folder_paths(category):
            candidate = Path(base) / name
            if candidate.is_file():
                return str(candidate)
        return None

    folder_paths.get_filename_list = get_filename_list
    folder_paths.get_folder_paths = get_folder_paths
    folder_paths.get_full_path = get_full_path

    comfy = types.ModuleType("comfy")
    lora = types.ModuleType("comfy.lora")
    sd = types.ModuleType("comfy.sd")

    def _offer(stems):
        """The shapes ComfyUI actually offers a module under: a wrapped dotted name and kohya's
        underscored one, both mapping to the model's own key. Neither carries an adapter suffix."""
        out = {}
        for stem in stems:
            out[f"diffusion_model.{stem}"] = stem
            out["lora_unet_" + stem.replace(".", "_")] = stem
        return out

    lora.model_lora_keys_unet = lambda model, key_map: {**key_map, **_offer(model.stems)}
    lora.model_lora_keys_clip = lambda model, key_map: {**key_map, **_offer(clip_stems)}

    def load_lora_for_models(model, clip, state, strength_model, strength_clip):
        return (("patched", model, strength_model), ("patched-clip", clip, strength_clip))

    sd.load_lora_for_models = load_lora_for_models
    comfy.lora = lora
    comfy.sd = sd

    for name, module in {
        "folder_paths": folder_paths,
        "comfy": comfy,
        "comfy.lora": lora,
        "comfy.sd": sd,
    }.items():
        sys.modules[name] = module
    return folder_paths
