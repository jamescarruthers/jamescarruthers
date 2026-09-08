#!/usr/bin/env python3
"""Build the site: markdown in content/ -> flat HTML in _site/.

Usage:  python build.py                     (writes to _site/)
        HOLDING=0 python build.py           (build as if `holding: false`)
        BASE_PATH=/repo python build.py     (for hosting under a sub-path)

Images: put full-size photographs in images/. The build resizes each one to
several widths (see SIZES), strips metadata, and writes them to _site/images/.
Resized files are cached in .cache/ so unchanged images are not redone.
"""

import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageOps

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
IMAGES = ROOT / "images"
CACHE = ROOT / ".cache" / "images"
OUT = ROOT / "_site"

# Widths (px) to generate for each photograph. Images are never upscaled.
SIZES = [800, 1600, 2400]
JPEG_QUALITY = 82
RASTER = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".gif", ".bmp"}

MD = markdown.Markdown(extensions=["extra", "smarty"])


# ---------------------------------------------------------------- helpers

SIMPLE_LINE = re.compile(r"^([A-Za-z_][\w-]*):[ \t]+(.+?)\s*$")


def parse_front_matter(raw, path):
    """Parse the YAML header, forgiving unquoted colons and hashes in values.

    Plain YAML rejects `title: Plotting: the joy of analogue` and silently
    truncates `title: Work #3`. Any simple `key: value` line that YAML cannot
    read as written, or that contains ' #', is wrapped in quotes first.
    """
    fixed = []
    for line in raw.splitlines():
        m = SIMPLE_LINE.match(line)
        if m:
            key, value = m.groups()
            needs_quotes = " #" in value
            if not needs_quotes:
                try:
                    yaml.safe_load(line)
                except yaml.YAMLError:
                    needs_quotes = True
            if needs_quotes and not (value[0] in "\"'" and value[-1] == value[0]):
                value = value.replace("\\", "\\\\").replace('"', '\\"')
                line = f'{key}: "{value}"'
        fixed.append(line)
    try:
        return yaml.safe_load("\n".join(fixed)) or {}
    except yaml.YAMLError as e:
        raise SystemExit(f"\n{path}: cannot read the header between the --- lines.\n{e}\n")


def read_page(path):
    """Read a markdown file with optional YAML front matter."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = parse_front_matter(parts[1], path.relative_to(ROOT))
            body = parts[2]
    MD.reset()
    html = MD.convert(body.strip())
    page = dict(meta)
    page["body"] = html
    page["slug"] = meta.get("slug", path.stem)
    page["_path"] = path
    return page


def read_dir(folder):
    if not folder.is_dir():
        return []
    return [read_page(p) for p in sorted(folder.glob("*.md"))]


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def format_date(value):
    """Human date: 2024-03-14 -> 14 March 2024, 2024-03 -> March 2024, 2024 -> 2024."""
    if isinstance(value, date):
        return value.strftime("%-d %B %Y")
    if value is None:
        return ""
    parts = re.findall(r"\d+", str(value))[:3]
    try:
        if len(parts) == 3:
            return date(*map(int, parts)).strftime("%-d %B %Y")
        if len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 1).strftime("%B %Y")
    except ValueError:
        pass
    return str(value)


def parse_date(value):
    """Return a date for sorting. Accepts YYYY, YYYY-MM or YYYY-MM-DD."""
    if isinstance(value, date):
        return value
    if value is None:
        return date.min
    s = str(value)
    parts = [int(p) for p in re.findall(r"\d+", s)[:3]]
    while len(parts) < 3:
        parts.append(1)
    try:
        return date(*parts)
    except ValueError:
        return date.min


# ---------------------------------------------------------------- images

def process_images():
    """Resize images/** into CACHE and copy to OUT/images.

    Returns {relative source path: [(width, height, output path), ...]}
    ordered small to large, or None for files copied unchanged (e.g. SVG).
    """
    variants = {}
    if not IMAGES.is_dir():
        return variants
    for src in sorted(p for p in IMAGES.rglob("*") if p.is_file()):
        rel = src.relative_to(IMAGES)
        if src.suffix.lower() not in RASTER:
            target = OUT / "images" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, target)
            variants[rel.as_posix()] = None
            continue

        (CACHE / rel.parent).mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            full_w, full_h = im.size
            icc = im.info.get("icc_profile")
            outputs = []
            for target_w in sorted({min(w, full_w) for w in SIZES}):
                name = f"{rel.stem}-{target_w}.jpg"
                cached = CACHE / rel.parent / name
                target_h = round(full_h * target_w / full_w)
                if not cached.exists() or cached.stat().st_mtime < src.stat().st_mtime:
                    resized = im.convert("RGB")
                    if target_w < full_w:
                        resized = resized.resize((target_w, target_h), Image.LANCZOS)
                    resized.save(cached, "JPEG", quality=JPEG_QUALITY, optimize=True,
                                 progressive=True, icc_profile=icc)
                    print(f"  resized {rel} -> {name}")
                out_rel = (Path("images") / rel.parent / name).as_posix()
                target = OUT / out_rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cached, target)
                outputs.append((target_w, target_h, out_rel))
        variants[rel.as_posix()] = outputs
    return variants


# ----------------------------------------------------------------- build

def main():
    site = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    base = os.environ.get("BASE_PATH", site.get("base_path", "")).rstrip("/")

    def url(path=""):
        return base + "/" + path.lstrip("/")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    env.filters["fmt_date"] = format_date
    env.globals.update(site=site, url=url, year=date.today().year)

    holding = os.environ.get("HOLDING", "1" if site.get("holding") else "0") == "1"
    # While holding, the public index is the holding page and the real home
    # page is written to a preview file (site.yml: holding_preview).
    home_file = site.get("holding_preview", "index2.html") if holding else "index.html"
    env.globals.update(holding=holding, home_url=url(home_file if holding else ""))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for extra in ("CNAME", ".nojekyll"):
        if (ROOT / extra).exists():
            shutil.copy(ROOT / extra, OUT / extra)

    if holding:
        page = read_page(CONTENT / "holding.md")
        (OUT / "index.html").write_text(
            env.get_template("holding.html").render(page=page), encoding="utf-8")

    variants = process_images()

    def image(path):
        """Template helper: src/srcset/width/height for an image path."""
        rel = path.lstrip("/")
        rel = rel[len("images/"):] if rel.startswith("images/") else rel
        outputs = variants.get(rel)
        if not outputs:
            return {"src": url(path), "srcset": "", "width": None, "height": None}
        w, h, _ = outputs[-1]
        return {
            "src": url(outputs[0][2]),
            "srcset": ", ".join(f"{url(o)} {ow}w" for ow, _, o in outputs),
            "width": w, "height": h,
        }
    env.globals["image"] = image

    # --- load content
    works = read_dir(CONTENT / "works")
    groups = read_dir(CONTENT / "groups")
    activity = read_dir(CONTENT / "activity")

    for w in works:
        w["tags"] = as_list(w.get("tags"))
        w["images"] = as_list(w.get("images")) or as_list(w.get("image"))
        w["url"] = url(f"works/{w['slug']}/")
        # Mark a work for sale with `available: true` (or the tag "available").
        w["available"] = bool(w.get("available")) or "available" in w["tags"]
        # `date` (YYYY, YYYY-MM or YYYY-MM-DD) orders works; `year` is the fallback.
        w["sort_date"] = parse_date(w.get("date") or w.get("year"))
        w.setdefault("year", w["sort_date"].year if w["sort_date"] != date.min else None)
    works.sort(key=lambda w: w["sort_date"], reverse=True)  # newest first

    # A group collects every work carrying one of its tags. Works keep the
    # order of the group's `works:` list if given, else newest first.
    for g in groups:
        g["tags"] = as_list(g.get("tags")) or as_list(g.get("tag")) or [g["slug"]]
        # `summary` is the short introduction shown on listing pages; the
        # body is the long version shown on the group's own page.
        MD.reset()
        g["summary"] = MD.convert(str(g["summary"]).strip()) if g.get("summary") else g["body"]
        g["has_more"] = bool(g.get("summary")) and g["body"].strip() != g["summary"].strip()
        g["url"] = url(f"works/{g['slug']}/")
        members = [w for w in works if set(w["tags"]) & set(g["tags"])]
        if g.get("works"):
            order = {slug: i for i, slug in enumerate(g["works"])}
            members.sort(key=lambda w: order.get(w["slug"], len(order)))
        g["works"] = members
        g["cover"] = g.get("image") or next(
            (w["images"][0] for w in members if w["images"]), None)
    groups.sort(key=lambda g: (g.get("order", 999), g.get("title", "")))

    grouped = {w["slug"] for g in groups for w in g["works"]}
    ungrouped = [w for w in works if w["slug"] not in grouped]

    # Tags -> works, for tag pages.
    tags = {}
    for w in works:
        for t in w["tags"]:
            tags.setdefault(t, []).append(w)

    for a in activity:
        a["sort_date"] = parse_date(a.get("date"))
        a["year_label"] = a["sort_date"].year if a["sort_date"] != date.min else ""
        a["has_page"] = bool(a["body"].strip())
        a["url"] = url(f"activity/{a['slug']}/") if a["has_page"] else None
    activity.sort(key=lambda a: a["sort_date"], reverse=True)
    years = []
    for a in activity:
        if not years or years[-1][0] != a["year_label"]:
            years.append((a["year_label"], []))
        years[-1][1].append(a)

    # --- write output
    if STATIC.is_dir():
        shutil.copytree(STATIC, OUT, dirs_exist_ok=True)

    written = 0

    def render(template, out_path, **ctx):
        nonlocal written
        target = OUT / out_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written += 1

    # Simple pages: content/*.md -> /<slug>/ (index.md -> /)
    for page in read_dir(CONTENT):
        if page["slug"] == "holding":
            continue
        out = home_file if page["slug"] == "index" else f"{page['slug']}/index.html"
        template = page.get("template", "home.html" if page["slug"] == "index" else "page.html")
        render(template, out, page=page, groups=groups, activity=activity[:5])

    render("works.html", "works/index.html",
           page={"title": site["nav"].get("works", "Works")},
           groups=groups, ungrouped=ungrouped)
    render("latest.html", "latest/index.html",
           page={"title": site["nav"].get("latest", "Latest")}, works=works)
    render("available.html", "available/index.html",
           page={"title": site["nav"].get("available", "Available")},
           works=[w for w in works if w["available"]])
    for g in groups:
        render("group.html", f"works/{g['slug']}/index.html", page=g, group=g)
    for i, w in enumerate(works):
        render("work.html", f"works/{w['slug']}/index.html", page=w, work=w,
               groups=[g for g in groups if w in g["works"]])
    for t, ws in tags.items():
        render("tag.html", f"tags/{t}/index.html", page={"title": t}, tag=t, works=ws)

    render("activity.html", "activity/index.html",
           page={"title": site["nav"].get("activity", "Activity")}, years=years)
    for a in activity:
        if a["has_page"]:
            render("activity_entry.html", f"activity/{a['slug']}/index.html", page=a, entry=a)

    print(f"Built {written} pages -> {OUT.relative_to(ROOT)}/")
    if holding:
        print(f"Holding page at index.html; preview the home page at {home_file}")


if __name__ == "__main__":
    sys.exit(main())
