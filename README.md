# John Schlaerth — Personal Portfolio

A self-hosted replacement for [John's Adobe Portfolio](https://johnschlaerth.myportfolio.com), built for [johnschlaerth.com](https://johnschlaerth.com). It preserves the original project descriptions and media in a personal portfolio with the clean typography, structured layout, and restrained color of Goosnav Labs.

The site uses a dependency-free Node.js static builder. Project content, presentation, and media live in this repository; Cloudflare serves the generated HTML, CSS, JavaScript, and files. No Adobe subscription or application server is required to serve the migrated site.

## Run locally

Use **Node.js 22 or newer**.

```sh
npm ci
npm run build
npm run check
npm run dev
```

Open the address printed by the development server. `npm run dev` serves `dist/`; rerun the build after editing source files. There are no third-party npm dependencies.

## Edit the portfolio

| Location | Purpose |
| --- | --- |
| `content/site.json` | Captured pages, descriptions, media references, and source information. |
| `content/presentation.json` | Presentation annotations and organization for the replacement site. |
| `public/media/` | Preserved media and any optimized display versions. |
| `public/documents/John_Schlaerth_Resume_05.27.26.pdf` | Downloadable résumé supplied for this migration. |
| `scripts/build.mjs` | Static page generation. |
| `archive/` | Original HTML and migration records, retained for checking and recovery. |
| `dist/` | Generated public website; rebuild this from source. |

Keep original project wording and media intact when making presentation changes. Add new public assets to `public/`, update their content references, then build and check. Archive files stay outside the deployed output.

The contact action opens an email draft in the visitor's mail application; it does not claim to submit an Adobe contact form. The original Adobe-hosted video is preserved locally with audio; its complete 1080p source is archived as well. The live portfolio has no Adobe-hosted content dependencies.

## Publish on Cloudflare

The root `wrangler.json` configures a static Cloudflare Worker. Connect **`johnschlaerth/johnschlaerth.com`** with these settings:

| Setting | Value |
| --- | --- |
| Worker name | `johnschlaerth-com` |
| Production branch | `main` |
| Build command | `npm run build` |
| Deploy command | `npx --yes wrangler@4.152.0 deploy` |
| Root directory | Repository root |
| Node.js version | `22` or newer |

The build checks all local media and original content before deployment. Only `dist/` is public.
An existing Cloudflare Pages project can also use build command `npm run build` and output directory `dist`.

See [the deployment guide](docs/DEPLOYMENT.md) for both setup paths, the Wrangler error, and domain connection.
Domain registration can remain with its current registrar.

## Before accepting a change

Run `npm run build`; it also runs the migration checks. Review the affected pages on desktop and mobile, follow project links, open their media, test the résumé download, and verify the email action. Compare substantive content changes against the originals in `archive/`.

## Preservation record

The migration preserves 21 original URLs, 15 projects, all 17 text blocks, 344 content-image placements, 362 original image files (including covers and site graphics), and the complete FB-V12 video. See [the content audit](docs/CONTENT_AUDIT.md) and [archive documentation](archive/adobe/README.md). Original oversized GIFs remain in Git; display versions meet Cloudflare’s 25 MiB per-file limit.

The manually runnable **Preserve portfolio media** workflow verifies existing originals against the frozen hashes. During the initial migration it restored the media from the recorded public URLs and committed them here. Normal builds use the checked-in files and do not contact Adobe.
