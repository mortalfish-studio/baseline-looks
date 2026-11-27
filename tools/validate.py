#!/usr/bin/env python3
"""Check every look in looks/ the way Baseline does before it uses one.

A look is data only: look.json, colors.toml (the palette) and an optional
pictures.json of links. Run: python3 tools/validate.py
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

FORMAT = 1
MAX_PICTURES = 8
KEYS = ("accent", "selection", "muted", "background", "dark_background", "darker_background",
        "lighter_background", "foreground", "dark_foreground", "light_foreground", "bright_foreground",
        "red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown",
        "bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta")
PICTURE_HOSTS = {"w.wallhaven.cc", "images.unsplash.com", "upload.wikimedia.org"}
STOCK_HOSTS = ("istockphoto.", "shutterstock.", "gettyimages.", "stock.adobe.", "alamy.", "dreamstime.", "123rf.",
               "depositphotos.")


def text(value, limit, name):
    value = str(value or "")
    if re.search(r"[\x00-\x1f\x7f<>]", value) or len(value) > limit:
        raise ValueError(f"{name} must be plain text, at most {limit} characters")
    return value


def small(path, limit=65536):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError(f"{path.name} is missing or too large")
    return path.read_text()


def check(folder):
    extra = sorted(p.name for p in folder.iterdir() if p.name not in {"look.json", "colors.toml", "pictures.json"})
    if extra:
        raise ValueError("only look.json, colors.toml and pictures.json are allowed, not " + ", ".join(extra))
    meta = json.loads(small(folder / "look.json"))
    if meta.get("format") != FORMAT:
        raise ValueError("look.json must say \"format\": 1")
    if meta.get("id") != folder.name or not re.fullmatch(r"[a-z0-9-]{1,32}", folder.name):
        raise ValueError("look.json's id must match the folder name (a-z, 0-9, -)")
    if not text(meta.get("name"), 40, "name").strip():
        raise ValueError("a look needs a name")
    text(meta.get("tagline"), 120, "tagline")
    text(meta.get("author"), 40, "author")
    if not isinstance(meta.get("version"), int) or not 1 <= meta["version"] <= 9999:
        raise ValueError("version must be a whole number")
    unknown = set(meta) - {"format", "id", "name", "tagline", "author", "version"}
    if unknown:
        raise ValueError("look.json has unknown keys: " + ", ".join(sorted(unknown)))
    found = set()
    for line in small(folder / "colors.toml").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r'([a-z_]+)\s*=\s*"([^"]*)"', line)
        if not match:
            raise ValueError(f"colors.toml: unexpected line {line[:40]!r}")
        key, value = match.groups()
        if key == "mode":
            if value not in {"dark", "light"}:
                raise ValueError("colors.toml: mode must be dark or light")
        elif key in KEYS:
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError(f"colors.toml: {key} must be #rrggbb")
            found.add(key)
        elif not key.startswith("hyprland_"):
            raise ValueError(f"colors.toml: unknown key {key}")
    if set(KEYS) - found:
        raise ValueError("colors.toml is missing " + ", ".join(k for k in KEYS if k not in found))
    if (folder / "pictures.json").exists():
        pictures = json.loads(small(folder / "pictures.json"))
        if not isinstance(pictures, list) or len(pictures) > MAX_PICTURES:
            raise ValueError(f"pictures.json must be a list of at most {MAX_PICTURES}")
        for p in pictures:
            if set(p) - {"title", "page", "image", "credit", "source"}:
                raise ValueError("pictures.json entries take title, page, image, credit, source")
            for key, limit in (("title", 60), ("page", 300), ("image", 300), ("credit", 120), ("source", 300)):
                text(p.get(key), limit, key)
            image, page, source = p.get("image", ""), p.get("page", ""), p.get("source", "")
            if not page.startswith("https://") or not image.startswith("https://") \
                    or (source and not source.startswith("https://")):
                raise ValueError("picture links must be https")
            if urlparse(image).hostname not in PICTURE_HOSTS:
                raise ValueError(f"pictures must come from {', '.join(sorted(PICTURE_HOSTS))}")
            if not re.search(r"\.(jpe?g|png|webp)$", urlparse(image).path, flags=re.I):
                raise ValueError("pictures must be jpg, png or webp")
            if any(s in (urlparse(source).hostname or "") for s in STOCK_HOSTS):
                raise ValueError("no paid stock photos, even as links")


def main():
    root = Path(__file__).resolve().parent.parent / "looks"
    failed = 0
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            check(folder)
            print(f"ok   {folder.name}")
        except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            failed += 1
            print(f"FAIL {folder.name}: {error}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
