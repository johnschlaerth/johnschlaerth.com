# Deploy on Cloudflare

The portfolio is a static site. `npm run build` creates and verifies `dist/`.
Every image and video comes from this repository. Adobe is not required after deployment.

## Fix the Wrangler configuration error

The previous source had no Wrangler configuration. Cloudflare's **Clone a public repository via Git URL** flow expects one.
The root `wrangler.json` now names the Worker and its static asset directory. It also configures real 404 responses.

Use the latest `main` branch. If the wizard still shows the old error, return to repository selection and select the repository again.
Use **Import a repository** for an existing GitHub repository. The **Clone a public repository** option creates a copy under the connected GitHub account.

## Workers with GitHub integration

Connect `johnschlaerth/johnschlaerth.com` from **Workers & Pages → Create application → Import a repository**.
The Cloudflare GitHub connection must have access to that repository.

| Setting | Value |
| --- | --- |
| Worker name | `johnschlaerth-com` (must match `wrangler.json`) |
| Production branch | `main` |
| Root directory | Repository root |
| Build command | `npm run build` |
| Deploy command | `npx --yes wrangler@4.152.0 deploy` |
| Node version | `22` or newer; set `NODE_VERSION=22` if needed |

The build stops if a local image, video, link, or original description is missing.
Wrangler uploads only `dist/`. Original snapshots and source video segments stay outside the deployed site.
Test the `workers.dev` address before you connect the domain.

For a terminal deployment, authenticate Wrangler in your Cloudflare account, then run:

```sh
npm ci
npm run deploy
```

For a deployment check without publication:

```sh
npm run build
npx --yes wrangler@4.152.0 deploy --dry-run
```

## Cloudflare Pages alternative

An existing Pages project can still serve this site. Use its Pages build settings:

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | Repository root |
| Node version | `22` or newer |

Leave the Worker deploy command out of Pages settings. Pages uses its dashboard build settings; `wrangler.json` configures the Worker option.

## Verify the deployment

- Open the homepage and each project. Refresh a project URL directly.
- Open images at full size and play the FB-V12 video with sound.
- Download the résumé and test the email link.
- Check a narrow screen and keyboard navigation.
- Open an unknown URL and confirm a 404 response.

## Connect johnschlaerth.com

Domain registration can remain with its current registrar. A registration transfer is optional.

1. Add `johnschlaerth.com` to the intended Cloudflare account.
2. Compare its DNS records with the current provider. Preserve email and service-verification records.
3. Follow Cloudflare's DNSSEC instructions before you replace the nameservers.
4. Set the nameservers at the registrar to those Cloudflare assigns. Wait until the zone is active.
5. For a Worker, open **Settings → Domains & Routes → Add → Custom domain**. Add `johnschlaerth.com`.
6. For Pages, use **Custom domains → Set up a domain** instead.
7. Add `www.johnschlaerth.com` if needed. Wait for HTTPS certificates, then test both addresses.

Attach the hostname through the application settings before you rely on a DNS record alone.
Keep the Adobe site until the replacement and preserved content pass verification.

## Updates

Push source changes to the connected production branch. Cloudflare rebuilds and deploys them.
Keep `archive/` and `public/media/` in the repository for recovery.
Each deployed file must remain below Cloudflare's 25 MiB asset limit. The build uses smaller derivatives for oversized original GIFs.

## Official references

- [Worker static assets and configuration](https://developers.cloudflare.com/workers/static-assets/binding/)
- [Workers build configuration](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/)
- [Worker custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)
- [Pages Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)
- [Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
