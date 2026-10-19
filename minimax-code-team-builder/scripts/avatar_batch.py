#!/usr/bin/env python3
"""Build image-generation requests for a team blueprint's agent avatars.

Emits one or more request files, each holding at most 10 requests, in the shape the
MiniMax matrix image generator accepts:

    mcode-tools connector call connector__matrix__generate_image --args-file <file>

The generator is only a text-to-image step: the caller downloads each result and saves
it as <dataDir>/agents/<slug>/avatar.<ext>, then re-runs the scaffolder so the
frontmatter points at it.

Usage:
    python avatar_batch.py --blueprint team.json --out <dir>
    python avatar_batch.py --blueprint team.json --out <dir> --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MAX_PER_CALL = 10

STYLE = (
    "Flat vector app icon. The rounded-square icon fills the entire frame edge to edge, "
    "full bleed background, no white border, no margin, no padding, no drop shadow. "
    "Exactly one single centered symbol, bold simple geometric shapes, minimal interior "
    "detail, high contrast, crisp clean edges, flat solid colors, no gradients, no 3D, "
    "no texture, modern SaaS product icon style, square canvas. "
    "Absolutely no text, no letters, no numbers, no words, no watermark."
)

FALLBACKS = [
    ("a compass rose", "bright gold", "solid deep navy blue"),
    ("a radar target with concentric rings", "bright teal", "solid deep teal"),
    ("a shield with a single checkmark", "bright periwinkle", "solid deep indigo"),
    ("a magnifying glass over three short lines", "bright sky blue", "solid deep teal blue"),
    ("two hands shaking", "bright coral", "solid dark rose"),
    ("a rocket angled upward", "bright crimson", "solid dark maroon"),
    ("a globe with latitude and longitude lines", "bright azure", "solid dark navy"),
    ("a storefront with a striped awning", "bright amber", "solid dark brown"),
    ("a shipping container on a truck", "bright steel blue", "solid dark slate"),
    ("a price tag with a percentage cutout", "bright lime green", "solid dark green"),
    ("a magnifying glass over a funnel", "bright chartreuse", "solid dark olive"),
    ("two interlocking gears with flow nodes", "bright steel grey", "solid dark blue grey"),
    ("an artist palette with a brush", "bright magenta", "solid dark plum"),
    ("a customer service headset with a speech bubble", "bright orange", "solid burnt orange"),
    ("a conversion funnel with descending bars", "bright emerald", "solid dark forest green"),
    ("a stack of product blocks on a shelf", "bright violet", "solid dark purple"),
]


def prompt_for(agent: dict, index: int) -> str:
    avatar = agent.get("avatar") or {}
    symbol = avatar.get("symbol")
    palette = avatar.get("palette")
    background = avatar.get("background")
    if not (symbol and palette and background):
        symbol, palette, background = FALLBACKS[index % len(FALLBACKS)]
    return f"{symbol}. {palette} symbol on a {background}. {STYLE}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--out", required=True, help="directory for the request files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.blueprint, "r", encoding="utf-8") as handle:
        blueprint = json.load(handle)
    agents = blueprint.get("agents") or []
    if not agents:
        print("blueprint has no agents", file=sys.stderr)
        return 2

    requests = [
        {
            "prompt": prompt_for(agent, index),
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "output_file": f"{agent['slug']}.png",
        }
        for index, agent in enumerate(agents)
    ]

    os.makedirs(args.out, exist_ok=True)
    written = []
    for start in range(0, len(requests), MAX_PER_CALL):
        chunk = requests[start : start + MAX_PER_CALL]
        path = os.path.join(args.out, f"avatars-{start // MAX_PER_CALL + 1}.json")
        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"requests": chunk}, handle, ensure_ascii=False, indent=2)
        written.append((path, len(chunk)))

    print(f"agents     : {len(agents)}")
    print(f"request files: {len(written)}")
    for path, count in written:
        print(f"  {os.path.basename(path):<24} {count} requests")
    if not args.dry_run:
        print("\nGenerate with (max 10 requests per call):")
        print("  mcode-tools connector call connector__matrix__generate_image --args-file <file>")
        print("\nThen download each result into <dataDir>/agents/<slug>/avatar.<ext>")
        print("and re-run scripts/scaffold_team.py so the frontmatter points at it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
