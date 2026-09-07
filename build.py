#!/usr/bin/env python3
"""Build the site: markdown in content/ -> flat HTML in _site/.

Usage:  python build.py            (writes to _site/)
        BASE_PATH=/repo python build.py   (for hosting under a sub-path)
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

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "_site"

MD = markdown.Markdown(extensions=["extra", "smarty"])


# ---------------------------------------------------------------- helpers

def read_page(path):
    """Read a markdown file with optional YAML front matter."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
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


def sort_key_year(item):
    # Newest first; missing year sorts last.
    year = item.get("year")
    try:
        return -int(str(year)[:4])
    except (TypeError, ValueError):
        return 1


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


# ----------------------------------------------------------------- build

def main():
    site = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    base = os.environ.get("BASE_PATH", site.get("base_path", "")).rstrip("/")

    def url(path=""):
        return base + "/" + path.lstrip("/")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    env.filters["fmt_date"] = format_date
    env.globals.update(site=site, url=url, year=date.today().year)

    # --- load content
    works = read_dir(CONTENT / "works")
    groups = read_dir(CONTENT / "groups")
    activity = read_dir(CONTENT / "activity")

    for w in works:
        w["tags"] = as_list(w.get("tags"))
        w["images"] = as_list(w.get("images")) or as_list(w.get("image"))
        w["url"] = url(f"works/{w['slug']}/")
    works.sort(key=sort_key_year)

    # A group collects every work carrying one of its tags. Works keep the
    # order of the group's `works:` list if given, else newest first.
    for g in groups:
        g["tags"] = as_list(g.get("tags")) or as_list(g.get("tag")) or [g["slug"]]
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
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    if STATIC.is_dir():
        shutil.copytree(STATIC, OUT, dirs_exist_ok=True)
    for extra in ("CNAME", ".nojekyll"):
        if (ROOT / extra).exists():
            shutil.copy(ROOT / extra, OUT / extra)

    written = 0

    def render(template, out_path, **ctx):
        nonlocal written
        target = OUT / out_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written += 1

    # Simple pages: content/*.md -> /<slug>/ (index.md -> /)
    for page in read_dir(CONTENT):
        out = "index.html" if page["slug"] == "index" else f"{page['slug']}/index.html"
        template = page.get("template", "home.html" if page["slug"] == "index" else "page.html")
        render(template, out, page=page, groups=groups, activity=activity[:5])

    render("works.html", "works/index.html",
           page={"title": site["nav"].get("works", "Works")},
           groups=groups, ungrouped=ungrouped)
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


if __name__ == "__main__":
    sys.exit(main())
