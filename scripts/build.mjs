import { readFile, writeFile, mkdir, readdir, stat, copyFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const output = path.join(root, 'dist');
const readJSON = async file => JSON.parse(await readFile(path.join(root, file), 'utf8'));
const source = await readJSON('content/site.json');
const profile = await readJSON('content/presentation.json');
const variants = existsSync(path.join(root, 'content/media-variants.json')) ? await readJSON('content/media-variants.json') : {};
const media = variants.images || variants;
const pages = new Map(source.pages.map(page => [page.slug, page]));
const projects = source.projects.map(project => ({ ...pages.get(project.slug), ...project, ...profile.projects[project.slug] }));
const maxAssetBytes = 25 * 1024 * 1024;
const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const cleanText = value => String(value ?? '').replace(/[\u200B-\u200D\uFEFF]/g, '').replace(/\s+/g, ' ').trim();
const route = slug => !slug || slug === 'index' ? '/' : `/${slug.replace(/^\/+|\/+$/g, '')}/`;
// Bypass image errors cached by the incomplete first deployment.
const mediaURL = href => href.replace(/^\/media\/([^?#]+)$/, '/media/$1?v=20261023');
const resume = profile.resume;
const absolute = href => new URL(href, profile.siteUrl).href;
const navigation = [['work', 'Work'], ['about', 'About'], ['resume', 'Résumé'], ['contact', 'Contact']];
const skippedAssets = [];
const pageInventory = [];

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
async function copyPublic(directory, relative = '') {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const name = path.join(relative, entry.name);
    const from = path.join(directory, entry.name);
    const to = path.join(output, name);
    if (entry.isDirectory()) { await mkdir(to, { recursive: true }); await copyPublic(from, name); }
    else if (entry.isFile()) {
      if ((await stat(from)).size > maxAssetBytes) { skippedAssets.push('/' + name.split(path.sep).join('/')); continue; }
      await copyFile(from, to);
    }
  }
}
await copyPublic(path.join(root, 'public'));

function normalizedLink(href) {
  if (!href) return '#';
  try {
    const url = new URL(href, source.source_url);
    if (url.origin === new URL(source.source_url).origin) {
      const slug = url.pathname.replace(/^\/+|\/+$/g, '');
      if (pages.has(slug || 'index')) return route(slug) + url.search + url.hash;
    }
  } catch { /* The migration checker reports malformed links. */ }
  return mediaURL(href);
}

function richText(html) {
  return String(html || '')
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/\s(on\w+|style|class|id)\s*=\s*("[^"]*"|'[^']*')/gi, '')
    .replace(/href=(['"])(.*?)\1/gi, (_, quote, href) => `href="${escape(normalizedLink(href.replace(/&amp;/g, '&')))}"`)
    .replace(/[\u200B-\u200D\uFEFF]/g, '');
}

function imageTag(image, options = {}) {
  if (!image?.src) return '';
  const { alt = '', thumbnail = false, eager = false, sizes = '(max-width: 760px) calc(100vw - 32px), 900px' } = options;
  const version = media[image.src] || {};
  const src = thumbnail ? (version.thumbnail || version.display || image.src) : (version.display || image.src);
  const width = version.width || image.width;
  const height = version.height || image.height;
  const srcset = !thumbnail && Array.isArray(version.srcset) && version.srcset.length && !/\.gif$/i.test(src)
    ? ` srcset="${version.srcset.map(item => `${escape(mediaURL(item.src))} ${item.width}w`).join(', ')}" sizes="${escape(sizes)}"` : '';
  return `<img src="${escape(mediaURL(src))}"${srcset} alt="${escape(alt || image.alt)}"${width && height ? ` width="${width}" height="${height}"` : ''} loading="${eager ? 'eager' : 'lazy'}" decoding="async"${eager ? ' fetchpriority="high"' : ''}>`;
}

function imageFigure(image, title, index, caption = '') {
  const version = media[image.src] || {};
  const alt = cleanText(image.alt) || (caption ? cleanText(caption) : `${title} — project image ${index}`);
  const full = version.full || image.src;
  if (version.video) {
    return `<figure class="project-figure animated-figure" data-source-media="${escape(image.src)}"><video controls data-animated muted loop playsinline preload="none"${version.poster ? ` poster="${escape(mediaURL(version.poster))}"` : ''} aria-label="${escape(alt)}"><source src="${escape(mediaURL(version.video))}" type="video/mp4"><a href="${escape(mediaURL(version.video))}">Open animation</a></video>${caption ? `<figcaption>${escape(caption)}</figcaption>` : ''}<p class="media-download"><a href="${escape(mediaURL(full))}">Open animation${/\.gif$/i.test(full) ? ' (original GIF)' : ''} ↗</a></p></figure>`;
  }
  return `<figure class="project-figure" data-source-media="${escape(image.src)}"><a class="media-link" href="${escape(mediaURL(full))}" data-lightbox data-caption="${escape(alt)}" aria-label="${escape(`Enlarge: ${alt}`)}">${imageTag(image, { alt })}<span class="enlarge-hint" aria-hidden="true">↗</span></a>${caption ? `<figcaption>${escape(caption)}</figcaption>` : ''}</figure>`;
}

function modulesHTML(page) {
  let figureIndex = 0;
  return (page.modules || []).map((module, index) => {
    const id = `module-${index + 1}`;
    if (module.type === 'text') return `<section id="${id}" class="module module-text prose rich-text">${richText(module.html || escape(module.text))}</section>`;
    if (['image', 'gallery'].includes(module.type)) {
      const images = module.images || [];
      return `<section id="${id}" class="module ${images.length > 1 ? 'module-images' : 'module-image'}" aria-label="${escape(page.title)} images">${images.map(image => imageFigure(image, page.title, ++figureIndex, images.length === 1 ? module.caption : '')).join('')}${module.caption && images.length > 1 ? `<p class="caption gallery-caption">${escape(module.caption)}</p>` : ''}</section>`;
    }
    if (module.type === 'video') {
      const src = module.src || module.video?.src;
      if (!src) throw new Error(`Video without local src on ${page.slug}`);
      return `<section id="${id}" class="module module-video"><video controls preload="none" playsinline${module.poster ? ` poster="${escape(mediaURL(module.poster))}"` : ''} aria-label="${escape(module.title || page.title + ' video')}"><source src="${escape(mediaURL(src))}" type="video/mp4"><a href="${escape(mediaURL(src))}">Download video</a></video><p class="caption">${escape(module.title || page.title + ' — project video')} · <a href="${escape(mediaURL(src))}">Open video ↗</a></p></section>`;
    }
    if (module.type === 'embed') return `<section id="${id}" class="module module-embed">${(module.embeds || []).map(embed => {
      if (/\.(mp4|webm)(\?|$)/i.test(embed.src)) return `<video controls preload="none" playsinline src="${escape(mediaURL(embed.src))}" aria-label="${escape(embed.title || page.title)}"></video>`;
      if (/adobe|myportfolio/i.test(embed.src)) throw new Error(`Adobe-dependent embed still needs migration: ${page.slug}`);
      return `<iframe src="${escape(mediaURL(embed.src))}" title="${escape(embed.title || page.title + ' video')}" loading="lazy" allow="fullscreen; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe><p class="caption"><a href="${escape(mediaURL(embed.src))}">Open embedded media ↗</a></p>`;
    }).join('')}</section>`;
    if (module.type === 'form') return ''; // Replaced by an explicit email composer on /contact/.
    if (module.type === 'divider') return '<hr class="module-divider">';
    if (module.html) return `<section id="${id}" class="module prose">${richText(module.html)}</section>`;
    throw new Error(`Unhandled module type ${module.type} on ${page.slug}`);
  }).join('\n');
}

function lightbox() {
  return `<dialog id="image-lightbox" class="lightbox" aria-label="Project image viewer"><div class="lightbox-toolbar"><span data-image-count></span><div><a href="#" data-original target="_blank" rel="noopener">Open full size ↗</a><button type="button" data-close aria-label="Close image viewer">Close ×</button></div></div><div class="lightbox-content"><img alt=""></div><div class="lightbox-bottom"><button type="button" data-previous aria-label="Previous image">← Previous</button><p class="lightbox-caption"></p><button type="button" data-next aria-label="Next image">Next →</button></div></dialog>`;
}

function layout({ title, slug, description, body, cover, active, noindex = false }) {
  const url = absolute(route(slug));
  const titleText = slug === 'index' ? `${profile.name} — Engineering & Design` : `${title} — ${profile.name}`;
  const socialImage = cover?.src ? (media[cover.src]?.display || cover.src) : projects[0]?.cover?.src;
  const jsonLd = { '@context': 'https://schema.org', '@type': 'Person', name: profile.fullName, url: profile.siteUrl, jobTitle: 'Multidisciplinary engineer', sameAs: [profile.linkedin, profile.github] };
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escape(titleText)}</title><meta name="description" content="${escape(description || profile.intro)}"><link rel="canonical" href="${escape(url)}"><meta name="theme-color" content="#ffffff">${noindex ? '<meta name="robots" content="noindex">' : ''}<meta property="og:type" content="website"><meta property="og:title" content="${escape(titleText)}"><meta property="og:description" content="${escape(description || profile.intro)}"><meta property="og:url" content="${escape(url)}"><meta property="og:site_name" content="${escape(profile.name)}">${socialImage ? `<meta property="og:image" content="${escape(absolute(mediaURL(socialImage)))}">` : ''}<meta name="twitter:card" content="summary_large_image"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/styles.css"><script src="/site.js" defer></script><script type="application/ld+json">${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script></head>
<body><a class="skip-link" href="#main">Skip to content</a><header class="site-header"><div class="shell"><a class="wordmark" href="/">JOHN SCHLAERTH<span class="wordmark-dot" aria-hidden="true">.</span></a><nav class="site-nav" aria-label="Main navigation">${navigation.map(([key, label]) => `<a href="${route(key)}"${(active || slug) === key || ((slug === 'index' || pages.get(slug)?.kind === 'project') && key === 'work') ? ' aria-current="page"' : ''}>${label}</a>`).join('')}</nav></div></header>
<main id="main" class="shell">${body}</main>
<footer class="site-footer"><div class="shell"><div class="footer-bottom"><span>© ${new Date(source.captured_at).getFullYear() || 2026} ${escape(profile.name)}</span><nav aria-label="Elsewhere"><a href="mailto:${profile.email}">Email ↗</a><a href="${profile.linkedin}">LinkedIn ↗</a><a href="${profile.github}">GitHub ↗</a><a href="/social-media/">Elsewhere ↗</a></nav><a href="#top" class="back-to-top">Back to top ↑</a></div></div></footer>${lightbox()}</body></html>`;
}

function projectCard(project, index) {
  return `<li class="project-card"><a href="${route(project.slug)}"><div class="card-image">${imageTag(project.cover, { alt: project.title, eager: index === 0, sizes: '(max-width: 600px) calc(100vw - 32px), (max-width: 1180px) calc((100vw - 80px) / 2), 534px' })}</div><div class="card-body"><h3>${escape(project.cardTitle || project.title)}</h3></div></a></li>`;
}

function projectIndex() {
  return `<section id="projects" aria-labelledby="projects-heading"><h2 id="projects-heading" class="sr-only">Projects</h2><ul class="project-grid">${projects.map(projectCard).join('')}</ul></section>`;
}

function home(slug) {
  return layout({ title: 'Portfolio', slug, active: 'work', cover: projects[0].cover, body: `<header class="portfolio-header"><h1>John Schlaerth</h1></header>${projectIndex()}` });
}

function projectPage(project, index) {
  const previous = projects[(index - 1 + projects.length) % projects.length];
  const next = projects[(index + 1) % projects.length];
  const body = `<nav class="breadcrumb" aria-label="Breadcrumb"><a href="/work/">← All projects</a></nav><header class="project-header"><h1 class="project-title">${escape(project.title)}</h1><p class="project-meta">${escape(project.category)} · ${escape(project.year)}</p></header><article class="project-body" aria-label="${escape(project.title)} documentation"><div class="project-modules">${modulesHTML(project)}</div></article><nav class="project-pagination" aria-label="Other projects"><a href="${route(previous.slug)}"><span>← Previous project</span><strong>${escape(previous.cardTitle || previous.title)}</strong></a><a href="${route(next.slug)}"><span>Next project →</span><strong>${escape(next.cardTitle || next.title)}</strong></a></nav>`;
  return layout({ title: project.title, slug: project.slug, description: project.summary, cover: project.cover, body });
}

function generalPage(page) {
  let heading = page.title;
  let intro = '';
  let body = '';
  if (page.slug === 'about') {
    heading = 'About';
    intro = 'John B. Schlaerth III, M.S.';
    body = `<div class="about-content project-modules">${modulesHTML(page)}</div><div class="hero-actions"><a class="button button-primary" href="/work/">Explore the portfolio →</a><a class="button button-secondary" href="${resume}">Download résumé ↗</a></div>`;
  } else if (page.slug === 'resume') {
    heading = 'Résumé';
    body = `<div class="resume-actions"><a class="button button-primary" href="${resume}" download>Download résumé (PDF) ↓</a><a class="button button-secondary" href="${resume}" target="_blank" rel="noopener">Open PDF ↗</a></div><p class="caption">PDF version: May 27, 2026.</p><div class="resume-viewer"><iframe src="${resume}#view=FitH" title="John Schlaerth résumé — May 27, 2026" loading="lazy"></iframe></div><section class="original-resume"><div class="section-heading"><h2>Portfolio résumé</h2><span>Full-size image</span></div><div class="project-modules">${modulesHTML(page)}</div></section>`;
  } else if (page.slug === 'social-media') {
    heading = 'Elsewhere';
    body = `<div class="link-directory"><a class="directory-item" href="${profile.linkedin}"><div><h2>LinkedIn</h2><p>Professional background and connections</p></div><span aria-hidden="true">↗</span></a><a class="directory-item" href="${profile.github}"><div><h2>GitHub</h2><p>Code and technical projects</p></div><span aria-hidden="true">↗</span></a><a class="directory-item" href="mailto:${profile.email}"><div><h2>Email</h2><p>${profile.email}</p></div><span aria-hidden="true">↗</span></a></div>${modulesHTML(page)}`;
  } else if (page.slug === 'contact') {
    heading = 'Contact';
    intro = 'For engineering opportunities, collaborations, or a question about my work.';
    body = `<div class="contact-panel"><div><p class="eyebrow">Direct contact</p><h2><a href="mailto:${profile.email}">${profile.email}</a></h2><p>Or connect on <a href="${profile.linkedin}">LinkedIn ↗</a>.</p></div><form id="contact-form" data-recipient="${profile.email}" hidden><h2>Compose an email</h2><p class="form-note">This opens a draft in your email app. You review and send it there.</p><label for="contact-name">Name <span aria-hidden="true">*</span></label><input id="contact-name" name="name" type="text" required autocomplete="name" maxlength="120" placeholder="Your Name..."><label for="contact-email">Email Address <span aria-hidden="true">*</span></label><input id="contact-email" name="email" type="email" required autocomplete="email" maxlength="254" placeholder="Your Email Address..."><label for="contact-subject">Subject</label><input id="contact-subject" name="subject" type="text" maxlength="180" value="Portfolio inquiry"><label for="contact-message">Message <span aria-hidden="true">*</span></label><textarea id="contact-message" name="message" required rows="6" maxlength="4000" placeholder="Your Message..."></textarea><button class="button button-primary" type="submit">Open email draft ↗</button><p id="contact-status" role="status"></p></form></div>`;
  } else body = modulesHTML(page);
  return layout({ title: page.title, slug: page.slug, description: intro || page.description, body: `<header class="page-header"><h1 class="page-title">${escape(heading)}</h1>${intro ? `<p class="page-intro">${escape(intro)}</p>` : ''}</header>${body}` });
}

async function savePage(slug, html) {
  const relative = slug === 'index' ? 'index.html' : `${slug}/index.html`;
  const target = path.join(output, relative);
  await mkdir(path.dirname(target), { recursive: true });
  // A real target for footer navigation, with no dependency on an id in migrated content.
  await writeFile(target, html.replace('<body>', '<body id="top">'));
  pageInventory.push({ slug, route: route(slug), file: relative });
}

await savePage('index', home('index'));
await savePage('work', home('work'));
for (const [index, project] of projects.entries()) await savePage(project.slug, projectPage(project, index));
for (const page of source.pages.filter(page => !['index', 'work'].includes(page.slug) && page.kind !== 'project')) await savePage(page.slug, generalPage(page));
await writeFile(path.join(output, '404.html'), layout({ title: 'Page not found', slug: '404', noindex: true, body: '<header class="page-header"><p class="eyebrow">404 / Page not found</p><h1 class="page-title">That page isn’t here.</h1><p class="page-intro">Browse the portfolio to find a project, or get in touch.</p><div class="hero-actions"><a class="button button-primary" href="/work/">View all projects →</a><a class="button button-secondary" href="/contact/">Contact</a></div></header>' }).replace('<body>', '<body id="top">'));
await writeFile(path.join(output, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${pageInventory.map(page => `<url><loc>${escape(absolute(page.route))}</loc></url>`).join('')}</urlset>\n`);
await writeFile(path.join(output, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${profile.siteUrl}/sitemap.xml\n`);
await mkdir(path.join(root, 'docs'), { recursive: true });
await writeFile(path.join(root, 'docs/build-inventory.json'), JSON.stringify({ pages: pageInventory, skippedOversizedOriginals: skippedAssets, note: 'Oversized originals remain in the repository; deployable derivatives are linked by content/media-variants.json.' }, null, 2) + '\n');
console.log(`Built ${pageInventory.length} pages plus 404. Local media copied. ${skippedAssets.length} oversized archived originals omitted from deployment.`);
