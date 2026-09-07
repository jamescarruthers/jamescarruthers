# jamescarruthers.com

A static site built from markdown. `build.py` reads `content/`, renders it
with the templates in `templates/`, copies `static/`, and writes flat HTML to
`_site/`. GitHub Actions builds and deploys it to GitHub Pages on every push
to `main`.

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
static/
  images/works/       photographs
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

Optional fields: `location`, `credit` (photo credit). The first image is used
as the thumbnail. Every tag gets its own page at `/tags/<tag>/`.

### Groups

A group is a title and an introduction, followed by every work carrying its
tag. `content/groups/sound-mirrors.md`:

```
---
title: Sound Mirrors
tag: sound-mirrors
order: 1
---
Introduction to the series.
```

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
