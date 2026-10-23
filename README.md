# John Schlaerth — Personal Portfolio

A self-hosted replacement for [John's Adobe Portfolio](https://johnschlaerth.myportfolio.com), built for [johnschlaerth.com](https://johnschlaerth.com). It preserves the original project descriptions and media in a personal portfolio with the clean typography, structured layout, and restrained color of Goosnav Labs.

The site uses a dependency-free Node.js static builder. Project content, presentation, and media live in this repository; Cloudflare Pages serves the generated HTML, CSS, JavaScript, and files. No Adobe subscription or application server is required to serve the migrated site.

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

The contact action opens an email draft in the visitor's mail application; it does not claim to submit an Adobe contact form. External links and any retained third-party video embeds still depend on their respective providers.

## Publish on Cloudflare

Connect **`johnschlaerth/johnschlaerth.com`** to a **Cloudflare Pages** project using:

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | Repository root; leave the field empty |
| Node.js version | `22` or newer; set `NODE_VERSION=22` if needed |

See [the deployment guide](docs/DEPLOYMENT.md) for account connection, domain setup, and verification. Test the generated `pages.dev` site before switching the domain. Domain registration can remain with its current registrar.

## Before accepting a change

Run `npm run build` followed by `npm run check`. Review the affected pages on desktop and mobile, follow project links, open their media, test the résumé download, and verify the email action. Compare substantive content changes against the originals in `archive/`.
