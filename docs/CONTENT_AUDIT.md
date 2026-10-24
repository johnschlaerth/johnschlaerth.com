# Adobe Portfolio content audit

This audit compares the archived Adobe HTML with `content/site.json`. It checks source-content completeness independently of the new site's layout or generated output. Snapshot timestamps and source hashes are recorded in `content/site.json` and `archive/adobe/metadata/`.

## Result

The captured source contains all **21 URLs** in the original sitemap, including the two project indexes, **15 project pages**, About, Resume, Social Media, and Contact. No missing project descriptions, body images, galleries, or project-index entries were found in the normalized content.

| Check | Result |
| --- | --- |
| Sitemap routes | All 21 represented by archived HTML and normalized page records. |
| Archived HTML integrity | All 21 page SHA-256 values match their recorded source hashes. |
| Project indexes | Both `/` and `/work` match all 15 project titles, years, and their original order. |
| Rich text | All 17 blocks, containing 12,290 characters of extracted text, match in content and order after whitespace normalization. |
| Body images | All 344 image instances match their original media URLs and order. |
| Image structure | 223 individual-image modules and 9 galleries containing 121 images are preserved. |
| Gallery lightboxes | Full-slide URLs were independently read from Adobe's `script[type="text/html"]` templates and matched to the normalized gallery images. |
| Module order | The text, image, gallery, video, and form sequence is preserved on each page. |
| Captions and text hyperlinks | No separate source captions or rich-text hyperlinks were present to omit. |
| Background graphics | No inline image backgrounds were found. The 13 archived custom stylesheets contain no nonempty `url(...)` graphic references. |

The 344 body images and 15 project-cover image records account for the initial 359-image inventory. Additional preserved files include the original global sharing image, favicon, and the video poster. Generated display derivatives and the supplied résumé PDF are additions to that source inventory.

## Special cases

**Social Media.** The original module contains two SVG icon links with no text: LinkedIn and email. Its normalized `modules` array is empty because those destinations are preserved in `external_links`. The replacement must render that list; an empty module list does not mean the original page had no content. This accounts for the difference between 252 original modules and 251 normalized modules.

**Contact.** The original name, email, and message fields, their placeholders, and form HTML are archived. The replacement deliberately uses an explicit email-composition action. Adobe's submission service and its success message must not be presented as a working local submission handler.

**Resume.** At John’s request, the live page now uses `John_Schlaerth_Resume_10.23.2026.pdf`, transcribed into responsive HTML with one PDF link. It replaces the old résumé image on the live page. The original image and prior PDF remain in the repository for recovery; they are excluded from the live-page preservation comparison.

**Walking-robot video.** The original FB-V12 page has one Adobe-hosted video iframe. Its original URL is captured. Video preservation and the deployable local playback copy are tracked separately under `archive/adobe/video/` and the corresponding migration metadata; this source-content audit does not substitute for playback verification.

**Global graphics.** The initial extraction omitted the original `og:image` and favicon because they occur in the document head. The audit identified both; their source URLs, local files, sizes, and hashes are now present in `archive/adobe/metadata/assets.json`:

- Sharing image: Adobe asset `e9fd2516-84e5-481c-86e1-828eb53ff661`.
- Favicon: Adobe asset `a1627771-dabf-48d3-b125-ee59cbc835d6`.

## Evidence and remaining release checks

Source evidence lives in `archive/adobe/sitemap.xml`, `archive/adobe/pages/`, `archive/adobe/styles/`, and `archive/adobe/metadata/assets.json`. Normalized content lives in `content/site.json`.

This audit covers the captured original and normalized data. Run the build and output checker, inspect the rendered pages, verify local video playback, and test the Cloudflare deployment separately before treating the migration as launched. No new network requests were used for this audit.
