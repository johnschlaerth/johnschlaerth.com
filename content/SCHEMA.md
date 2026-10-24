# Portfolio content

`site.json` is the frozen content snapshot imported from the public Adobe
Portfolio. The ordinary website build reads it locally and never contacts Adobe.

## Structure

- `navigation`: original navigation labels and paths.
- `projects`: original project order, titles, years, and cover records.
- `pages`: all 21 original URL paths, including `/` (`slug: index`) and `/work`.
- Each page has `slug`, `title`, `kind` (`index`, `project`, or `page`),
  `source_url`, `description`, `year`, `modules`, `text`, `external_links`,
  `raw_html`, and the original HTML `sha256`.
- Project pages also contain `cover`.

## Ordered modules

| Type | Content |
| --- | --- |
| `text` | `html` with Adobe styles/scripts removed, plus exact readable `text` |
| `image` | `images` array of one original asset |
| `gallery` | `images` array in original order |
| `video` | Local `src`, local `poster`, `title`, dimensions, and archival `original_url` |
| `form` | Original field names/types/placeholders and source text; the new contact page implements its own email composition behavior |

Image records contain local `/media/…` `src`, archival `original_url`, original
`alt`, and measured `width`, `height`, `bytes`, `format`, and `frames`.
Original alt text is blank where Adobe had none; the site renderer can supply
project-based accessible descriptions without altering the source snapshot.

The Social Media source page contained icon links only; these are retained in
`external_links` (LinkedIn and email). The source résumé was one image; the
separately supplied résumé PDF is an additional download, not a replacement for
that original image.

## Preservation

Raw HTML, source sitemap, and audit manifests are under `archive/adobe/`.
Original image bytes are under `public/media/`. Display derivatives are generated
separately; the originals must not be silently replaced by resized versions.
The FB-V12 video is preserved at its highest publicly offered 1080p resolution as
independent HLS segments under `archive/adobe/video/fb-v12/`, with a smaller MP4
for website playback. Its source Adobe player is no longer needed.

`scripts/archive_adobe.py` is a one-time migration utility, not a build step.
It needs network access and Python `beautifulsoup4`, `requests`, and `Pillow`.
The preserved-video mapping retains completed local video recovery if the image
and text import is rerun. Inspect changes before replacing this frozen snapshot.
