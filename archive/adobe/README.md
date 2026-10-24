# Original Adobe Portfolio preservation

Source: `https://johnschlaerth.myportfolio.com/`.

This directory preserves the public portfolio independently of the Adobe account.
It is an archival source directory and is not copied into the production website.

## Contents

- `pages/`: all 21 published HTML URLs from the source sitemap, including both
  the root portfolio grid and `/work`.
- `styles/`: all 13 distinct original theme stylesheets; inspected for additional
  graphics, with no CSS `url(...)` backgrounds found.
- `metadata/pages.json`: page identities, source URLs, paths, and SHA-256 hashes.
- `metadata/assets.json`: every original image's source URL, local path, byte
  count, SHA-256 hash, measured dimensions, and GIF frame count.
- `metadata/content-verification.json`: page-by-page source/import comparison.
- `metadata/report.json`: capture totals, failures, and media limits.
- `metadata/preserved-videos.json`: original-video archive and local playback map.
- `video/fb-v12/`: every segment of the highest publicly offered 1080p FB-V12 video.

Original image binaries live in `public/media/`; the new website uses smaller
display derivatives where needed. Four source GIFs exceed the Cloudflare Pages
per-file limit and remain preserved in Git while smaller versions serve visitors.

## Video recovery

The Adobe player offered three streaming resolutions. The complete 1920×1080
stream was downloaded as 69 independent MPEG-TS files, totaling 271,330,436 bytes.
Each file has a SHA-256 hash in `video/fb-v12/segments.json`.

`source-index.m3u8` is the exact original playlist. Its segment durations were
rounded/inaccurate, so `index.m3u8` uses durations measured with ffprobe without
changing any segment bytes. The corrected playlist totals approximately 408.48
seconds. Both its video and audio streams are retained.

To reconstruct a full-resolution MP4 locally, install FFmpeg and run from the
repository root:

```sh
ffmpeg -i archive/adobe/video/fb-v12/index.m3u8 -c copy \
  -bsf:a aac_adtstoasc -movflags +faststart fb-v12-original-1080p.mp4
```

That reconstructed file is larger than GitHub's single-file upload limit; the
segmented archive avoids that limit. The smaller website playback MP4 preserves
the full duration and audio while meeting Cloudflare Pages' file-size limit.

Only stable video identifiers and unsigned resource locations are archived.
Temporary playback access parameters and player response snapshots were removed
before publication. A fresh restoration discovers current public playback access
in memory from the portfolio page; it never writes those values into the repo.
No live Adobe URLs are needed to view the preserved video or rebuilt portfolio.

## Completeness checks

The original 15 project covers and all 344 project/about/résumé image occurrences
were imported in order. All 17 original rich-text blocks match the extracted
content after whitespace normalization. The original social sharing photograph,
favicon, and video poster are also saved. Every page's current SHA-256 hash
matches its archived HTML. The FB-V12 page's original player access query was
redacted; its initial capture checksum is retained as `original_capture_sha256`,
while `sha256` verifies the sanitized file. The descriptions and media are intact.
See `metadata/redaction-report.json` for the complete publication redaction log.

The original contact form depended on Adobe's service. Its fields and source
markup remain in the archive; the rebuilt site's contact action uses email
composition instead of pretending to submit to a removed Adobe backend.
