# jamescarruthers.com

A static site built from markdown. `build.py` reads `content/`, renders it
with the templates in `templates/`, resizes the photographs in `images/`,
copies `static/`, and writes flat HTML to `_site/`. GitHub Actions builds
and deploys it to GitHub Pages on every push to `main`.

## Holding page

While `holding: true` is set in `site.yml`, the public index is the holding
page (`content/holding.md`) and the real home page is published at the
address given by `holding_preview` (default `index2.html`), so you can check
the site at `/index2.html` while visitors see the holding page. Pages carry a
noindex tag in this mode. Set `holding` to `false` when the site is ready.

## Editing content

Everything lives in `content/`. Each file is markdown with a YAML header
between `---` lines. The file name becomes the URL slug.

```
content/
  index.md            home page text
  contact.md          contact page
  works/              one file per work
  groups/             one file per group of works
  activity/           exhibitions, talks, commissions, etc.
images/
  works/              full-size photographs, resized by the build
static/
  style.css
```

### Works

`content/works/sound-mirror-i.md`:

```
---
title: Sound Mirror I
year: 2023
medium: Cast concrete, steel
dimensions: 240 × 180 × 90 cm
tags: [sound-mirrors, sculpture]
images:
  - images/works/sound-mirror-i.jpg
  - images/works/sound-mirror-i-detail.jpg
---
Text about the work. Markdown is fine here.
```

Optional fields: `location`, `credit` (photo credit), `date` (`2024-03` or
`2024-03-14`, to order works within a year). The first image is used as the
thumbnail. Every tag gets its own page at `/tags/<tag>/`.

`/latest/` lists every work, newest first.

### Available works

Mark a work for sale with `available: true` and give it a `price`. The price
is free text, so `£1,200`, `£1,200 + VAT` or `Price on request` all work.

```
---
title: Untitled (estuary)
year: 2023
available: true
price: £450
---
```

`/available/` lists every available work. Availability and price also show
wherever the work appears: the Works, Latest, group and tag pages, and the
work's own page, which links to the contact page. Remove `available` (or
set it to `false`) when a work sells.

### Groups

A group is a title and an introduction, followed by every work carrying its
tag. `content/groups/sound-mirrors.md`:

```
---
title: Sound Mirrors
tag: sound-mirrors
order: 1
summary: >
  One or two sentences shown on the Works page, with a "Read more" link.
---
The full introduction, shown on the group's own page. Any length, any
markdown.
```

`summary` is optional. Without it the full introduction is shown in both
places.

Optional fields:

- `tags: [a, b]` to collect several tags into one group.
- `works: [slug, slug]` to fix the order of works. Otherwise newest first.
- `image:` to choose the cover thumbnail on the home page.

Groups appear on `/works/` in `order`, each with its own page at
`/works/<slug>/`. A work can be in more than one group. Works that match no
group are listed under "Other works".

### Exhibitions, talks, commissions

`content/activity/listening-in.md`:

```
---
title: Listening In
type: Solo exhibition
date: 2024-03-14
venue: Example Gallery
location: London
link: https://example.com
---
```

`date` can be `2024`, `2024-03` or `2024-03-14`. `type` is free text. If the
file has body text below the header, the entry gets its own page with the text
and any `images:` listed; otherwise it is a single line in the list.

### Images

Put full-size photographs in `images/` (JPEG, PNG, TIFF or WebP) and refer to
them from the markdown by path, e.g. `images/works/sound-mirror-i.jpg`. The
build resizes each one to 800, 1600 and 2400 pixels wide (never larger than
the original), saves them as JPEG with metadata stripped, and writes a
`srcset` so browsers pick the right size. Resized files are cached in
`.cache/` locally and in the GitHub Actions cache, so unchanged images are
not processed again. SVG files are copied unchanged.

### Site settings

`site.yml` holds the site title, description and the navigation labels.

## Building locally

```
pip install -r requirements.txt
python build.py
python -m http.server -d _site
```

Then open http://localhost:8000.

## Custom domain

Add a `CNAME` file containing the domain to the repository root. The build
copies it into `_site/`. For a project site served under a sub-path, the
workflow sets `BASE_PATH` automatically.
