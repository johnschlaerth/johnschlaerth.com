# Deploy to Cloudflare Pages

This repository builds a static website with Node.js. The deployment target is **Cloudflare Pages with GitHub integration**. Account authorization and the domain cutover happen in your Cloudflare account.

## 1. Connect the repository

1. Sign in to Cloudflare and open **Workers & Pages**.
2. Select **Create application**, then the **Pages** tab. Choose **Connect to Git** or **Import an existing Git repository**. Use the Pages path, not the Worker creation wizard.
3. Connect the GitHub account **`johnschlaerth`** and grant Cloudflare access to **`johnschlaerth.com`**. If the repository is absent, update the Cloudflare GitHub app's repository permissions.
4. Select **`johnschlaerth/johnschlaerth.com`** and begin setup.
5. Enter the following settings:

| Setting | Value |
| --- | --- |
| Project name | `johnschlaerth` or another available name |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | Leave empty to use the repository root |
| Environment variable, if needed | `NODE_VERSION` = `22` |

The build requires Node.js 22 or newer. No API keys or application secrets are required. Deploy **only `dist/`**; it contains the public site, while original source snapshots remain in `archive/`.

6. Select **Save and Deploy**. Wait for a successful build and open the exact `https://<project-name>.pages.dev` address Cloudflare provides.

After connection, pushes to `main` automatically rebuild the production site. Other branches can generate preview deployments according to the project's branch settings.

## 2. Verify before changing DNS

On the `pages.dev` deployment:

- Open the homepage and every project from the project index. Refresh a project page directly to check its route.
- Check descriptions, captions, image galleries, and any video embeds against the archived originals.
- Open the résumé download and test the contact email link. The contact action composes an email; it does not submit through Adobe.
- Check mobile navigation and image sizing on a narrow screen.
- Open a nonexistent path and confirm that the site's not-found page appears.

Keep a copy of this repository, including `archive/` and `public/media/`. The archive is for recovery and comparison; it is not part of the live website.

## 3. Connect johnschlaerth.com

**You do not need to transfer domain registration to Cloudflare.** For the apex address `johnschlaerth.com`, Cloudflare Pages requires a Cloudflare DNS zone in the same account as the Pages project. You can change nameservers at your existing registrar and transfer registration separately if desired.

1. In Cloudflare, add/onboard **`johnschlaerth.com`** as a domain.
2. Compare the imported DNS records with those at your current DNS provider. Cloudflare's automatic scan may miss records. Preserve existing email **MX**, **SPF**, **DKIM**, and **DMARC** records and service-verification records, if any.
3. If DNSSEC is enabled at the current registrar, follow Cloudflare's instructions to disable it before replacing nameservers; re-enable it through Cloudflare after the zone is active.
4. At the registrar, replace the nameservers with the two assigned by Cloudflare. Wait until Cloudflare reports the zone as active.
5. Open **Workers & Pages → your Pages project → Custom domains → Set up a domain**. Add **`johnschlaerth.com`** and follow the DNS prompts.
6. Add **`www.johnschlaerth.com`** through the same Pages custom-domain flow so both addresses work. If you prefer one canonical hostname, configure Cloudflare's documented `www` → apex redirect after the custom domain is working; preserve paths and query strings.
7. Wait for each custom domain and its HTTPS certificate to become active. Verify the homepage, a project URL, media, and the résumé on the custom domain.

Associate the hostname with the Pages project **before** relying on a manually created CNAME. A DNS record alone does not attach a hostname to Pages. Retire the Adobe-hosted site only after content has been preserved and the replacement has been verified.

## Routine updates and recovery

```sh
npm ci
npm run build
npm run check
```

Commit the intended source changes and push to `main`. Watch the build in the Pages dashboard and inspect the resulting deployment. If a release causes a problem, use Pages' deployment history to roll back to a previously successful production deployment, then correct the source in GitHub.

## Common setup problems

| Symptom | Check |
| --- | --- |
| Build fails or uses an older Node version | Set `NODE_VERSION=22` and rerun the deployment. Check that the production branch contains `package.json` and `scripts/build.mjs`. |
| Homepage returns 404 | Confirm output is `dist` and the successful build produced `dist/index.html`. |
| Missing routes show the homepage | Confirm the deployed output includes the top-level `404.html`; Pages otherwise assumes a single-page application. |
| Custom hostname fails while `pages.dev` works | Check Pages **Custom domains**, DNS-zone activation, hostname records, and certificate status. |
| An image or video fails | Check the file or embed URL. Any third-party video embed still depends on its original provider. |
| An added file blocks deployment | Pages limits each asset to **25 MiB**. Keep oversized originals archived and use a deployable derivative or suitable separate media hosting. |

## Official references

- [Cloudflare Pages Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)
- [Deploying static HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)
- [Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
- [Onboarding a domain and preserving DNS records](https://developers.cloudflare.com/fundamentals/manage-domains/add-site/)
- [Redirecting www to the apex domain](https://developers.cloudflare.com/pages/how-to/www-redirect/)
- [Serving Pages and not-found behavior](https://developers.cloudflare.com/pages/configuration/serving-pages/)
- [Pages limits](https://developers.cloudflare.com/pages/platform/limits/)
