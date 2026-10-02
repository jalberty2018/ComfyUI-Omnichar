# SPDX-License-Identifier: GPL-3.0-or-later
"""Where ``.char`` files are looked for, and the guard confining the manual path override."""

from __future__ import annotations

import os
from pathlib import Path

import folder_paths
from omnichar_char import CharError

CATEGORY = "characters"
SUFFIX = ".char"


def _default_roots() -> list[Path]:
    roots = [Path(folder_paths.models_dir) / CATEGORY]
    shared = os.environ.get("INLINE_CHARACTERS_DIR")
    if shared:
        roots.append(Path(shared))
    return roots


def register() -> None:
    """Add the ``characters`` category, keeping any paths another extension already registered."""
    existing = folder_paths.folder_names_and_paths.get(CATEGORY)
    paths: list[str] = list(existing[0]) if existing else []
    extensions = set(existing[1]) if existing else set()
    for root in _default_roots():
        root.mkdir(parents=True, exist_ok=True)
        if str(root) not in paths:
            paths.append(str(root))
    extensions.add(SUFFIX)
    folder_paths.folder_names_and_paths[CATEGORY] = (paths, extensions)


def listed() -> list[str]:
    """Character filenames for the loader dropdown."""
    try:
        return sorted(folder_paths.get_filename_list(CATEGORY))
    except (KeyError, OSError):
        # Before register() runs, or an unreadable directory; anything else is a fault worth seeing.
        return []


def roots() -> list[Path]:
    """Every directory a character may be read from, resolved."""
    try:
        registered = folder_paths.get_folder_paths(CATEGORY)
    except KeyError:
        registered = [str(root) for root in _default_roots()]
    out: list[Path] = []
    for path in registered:
        try:
            out.append(Path(path).resolve())
        except OSError:
            continue
    return out


def resolve(name: str, override: str = "") -> Path:
    """The file to open, confined to a registered directory after symlinks are resolved."""
    allowed = roots()
    if override.strip():
        try:
            target = Path(override.strip()).expanduser().resolve()
        except OSError as error:
            raise CharError(f"{override} cannot be resolved to a file.") from error
        if not any(target == root or root in target.parents for root in allowed):
            listing = "\n  ".join(str(root) for root in allowed) or "(none registered)"
            raise CharError(
                f"{target} is outside the character directories this node may read. "
                f"Move the file into one of these, or set INLINE_CHARACTERS_DIR:\n  {listing}"
            )
        if not target.is_file():
            raise CharError(f"{target} does not exist.")
        return target

    if not name:
        raise CharError(
            "No character was chosen. Put a .char file in "
            f"{allowed[0] if allowed else 'models/characters'} and reload the node."
        )
    found = folder_paths.get_full_path(CATEGORY, name)
    if not found:
        raise CharError(
            f"{name} is not in the character directories. Reload ComfyUI if you just added it."
        )
    return Path(found).resolve()
