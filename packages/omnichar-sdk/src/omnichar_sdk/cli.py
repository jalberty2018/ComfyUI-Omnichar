# SPDX-License-Identifier: Apache-2.0
"""``omnichar-sdk``: read a character file from a shell, so a non-Python tool can use one too."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .character import Character
from .charfile import ROLES, CharError
from .lora import safe_output_name
from .prompt import STYLES
from .references import FIT_MODES


def _inspect(char: Character, as_json: bool) -> int:
    info = char.get_info()
    if as_json:
        loras: list[dict[str, Any]] = []
        payload: dict[str, Any] = {
            "name": info.name,
            "charId": info.char_id,
            "description": info.description,
            "hints": info.hints,
            "refCount": info.ref_count,
            "refArchs": info.ref_archs,
            "loraArchs": info.lora_archs,
            "formatVersion": info.format_version,
            "createdAt": info.created_at,
            "modifiedAt": info.modified_at,
            "sizeBytes": info.size_bytes,
            "references": [
                {
                    "path": ref.path,
                    "role": ref.role,
                    "origin": ref.origin,
                    "width": ref.width,
                    "height": ref.height,
                    "sha256": ref.sha256,
                }
                for ref in char.get_references()
            ],
            "loras": loras,
        }
        for arch in info.lora_archs:
            lora = char.get_lora(arch)
            if lora is None:
                continue
            loras.append(
                {
                    "arch": lora.arch,
                    "base": lora.base,
                    "rank": lora.rank,
                    "steps": lora.steps,
                    "resolution": lora.resolution,
                    "strength": lora.strength,
                    "filename": lora.filename,
                    "portability": lora.portability.value,
                    "reason": lora.reason,
                }
            )
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"{info.name}  ({info.ref_count} references, format {info.format_version})")
    if info.description:
        print(f"\n{info.description}\n")
    counts: dict[str, int] = {}
    for ref in char.get_references():
        counts[ref.role] = counts.get(ref.role, 0) + 1
    if counts:
        print("references: " + ", ".join(f"{n} {role}" for role, n in sorted(counts.items())))
    print("reference sets: " + (", ".join(info.ref_archs) or "none"))
    for arch in info.lora_archs:
        lora = char.get_lora(arch)
        if lora is None:
            continue
        print(
            f"adapter {arch}: rank {lora.rank}, {lora.steps} steps, strength {lora.strength}\n"
            f"  {lora.portability.value}: {lora.reason}"
        )
    if not info.lora_archs:
        print("adapters: none")
    for hint in info.hints:
        print(f"hint: {hint}")
    return 0


def _extract(char: Character, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    refs_dir = out / "refs"
    refs_dir.mkdir(exist_ok=True)
    written = 0
    for index, ref in enumerate(char.get_references()):
        # The member name is attacker-controlled, so the output name is built here, not from it.
        target = refs_dir / f"{index:03d}_{ref.role}.png"
        target.write_bytes(ref.bytes())
        written += 1
    description = char.get_description()
    if description:
        (out / "description.md").write_text(description, encoding="utf-8")
    for arch in char.get_lora_archs():
        lora = char.get_lora(arch)
        if lora is None:
            continue
        lora.save_to(out, safe_output_name(f"{char.name}-{arch}"))
    print(f"Wrote {written} references to {refs_dir}")
    return 0


def _sheet(char: Character, args) -> int:
    written = char.save_reference_sheet(
        args.out,
        arch=None if args.arch in (None, "", "originals") else args.arch,
        role=None if args.role == "any" else args.role,
        limit=None if args.max_references <= 0 else args.max_references,
        first_position=args.first_position,
        columns=args.columns,
        cell=(args.cell, args.cell),
        fit=args.fit,
        labels=not args.no_labels,
    )
    print(f"Wrote {written}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omnichar-sdk", description="Read an Omnichar Studio .char character file."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="print what a character holds")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--json", action="store_true", help="machine-readable output")

    extract = sub.add_parser(
        "extract", help="write references, description and adapters to a folder"
    )
    extract.add_argument("file", type=Path)
    extract.add_argument("-o", "--out", type=Path, required=True)

    prompt = sub.add_parser("prompt", help="print the prompt text for a character")
    prompt.add_argument("file", type=Path)
    prompt.add_argument("--style", choices=STYLES, default="ordinal")
    prompt.add_argument("--first-position", type=int, default=1)
    prompt.add_argument("--role-lines", action="store_true")
    prompt.add_argument("--arch", default=None)

    sheet = sub.add_parser("sheet", help="write the references out as one numbered PNG")
    sheet.add_argument("file", type=Path)
    sheet.add_argument("-o", "--out", type=Path, required=True)
    sheet.add_argument("--arch", default="originals")
    sheet.add_argument("--role", choices=["any", *ROLES], default="any")
    sheet.add_argument("--max-references", type=int, default=0)
    sheet.add_argument("--first-position", type=int, default=1)
    sheet.add_argument("--columns", type=int, default=None)
    sheet.add_argument("--cell", type=int, default=384)
    sheet.add_argument("--fit", choices=list(FIT_MODES), default="pad")
    sheet.add_argument("--no-labels", action="store_true")

    args = parser.parse_args(argv)
    try:
        char = Character.open(args.file)
        if args.command == "inspect":
            return _inspect(char, args.json)
        if args.command == "extract":
            return _extract(char, args.out)
        if args.command == "sheet":
            return _sheet(char, args)
        print(
            char.get_prompt(
                style=args.style,
                first_position=args.first_position,
                role_lines=args.role_lines,
                arch=args.arch,
            )
        )
        return 0
    except CharError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
