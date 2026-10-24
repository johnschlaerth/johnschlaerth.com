import { readFile, readdir, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { runInNewContext } from 'node:vm';

const root = path.resolve(import.meta.dirname, '..');
const dist = path.join(root, 'dist');
const site = JSON.parse(await readFile(path.join(root, 'content/site.json'), 'utf8'));
const profile = JSON.parse(await readFile(path.join(root, 'content/presentation.json'), 'utf8'));
const cloudflare = JSON.parse(await readFile(path.join(root, 'wrangler.json'), 'utf8'));
assert.equal(cloudflare.assets.directory, './dist', 'Cloudflare must deploy only the generated public site.');
assert.equal(cloudflare.assets.not_found_handling, '404-page', 'Missing routes must return the portfolio 404 page.');
const errors = [];
const report = { routes: 0, textBlocks: 0, contentImages: 0, localReferences: 0, outputFiles: 0, largestAssetBytes: 0, adobeDependencies: 0 };
const decode = value => value.replace(/&#x([\da-f]+);/gi, (_, code) => String.fromCodePoint(parseInt(code, 16))).replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code))).replace(/&(amp|lt|gt|quot|apos|nbsp|ndash|mdash|lsquo|rsquo|ldquo|rdquo|hellip);/g, (_, name) => ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—', lsquo: '‘', rsquo: '’', ldquo: '“', rdquo: '”', hellip: '…' }[name]));
const normalize = value => decode(String(value)).replace(/[\u200B-\u200D\uFEFF]/g, '').replace(/\s+/g, ' ').trim();
const plain = html => normalize(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '').replace(/<[^>]*>/g, ' '));
const built = new Map();

for (const page of site.pages) {
  const file = path.join(dist, page.slug === 'index' ? 'index.html' : `${page.slug}/index.html`);
  if (!existsSync(file)) { errors.push(`Missing original route: ${page.slug}`); continue; }
  const html = await readFile(file, 'utf8');
  built.set(file, html);
  report.routes++;
  if ((html.match(/<h1(?:\s|>)/g) || []).length !== 1) errors.push(`Expected one h1: ${page.slug}`);
  const renderedText = plain(html);
  // The supplied October résumé replaces the archived Adobe résumé.
  const modules = page.slug === 'resume' ? [] : page.modules || [];
  for (const module of modules) {
    if (module.type === 'text') {
      report.textBlocks++;
      if (!renderedText.includes(normalize(module.text))) errors.push(`Missing source text on ${page.slug}: ${normalize(module.text).slice(0, 90)}`);
    }
  }
  const expected = modules.flatMap(module => module.images || []).map(image => image.src);
  const actual = [...html.matchAll(/data-source-media="([^"]+)"/g)].map(match => decode(match[1]));
  report.contentImages += expected.length;
  if (JSON.stringify(expected) !== JSON.stringify(actual)) errors.push(`Image count or order changed on ${page.slug}: source=${expected.length}, output=${actual.length}`);
  if (page.slug === 'social-media') {
    for (const link of page.external_links || []) {
      const normalizedTarget = link.url.replace(/^http:/, 'https:');
      if (!html.includes(link.url) && !html.includes(normalizedTarget)) errors.push(`Missing social link: ${link.url}`);
    }
  }
  const videoSources = (page.modules || []).filter(module => module.type === 'video').map(module => module.src);
  for (const src of videoSources) if (!html.includes(`src="${src}?v=20261023"`)) errors.push(`Missing recovered video: ${page.slug}`);
}

const originalProjectOrder = site.projects.map(project => project.slug);
for (const slug of ['index', 'work']) {
  const file = path.join(dist, slug === 'index' ? 'index.html' : `${slug}/index.html`);
  const html = built.get(file) || '';
  const actual = [...html.matchAll(/<li class="project-card"[^>]*><a href="\/([^/]+)\/"/g)].map(match => match[1]);
  if (JSON.stringify(actual) !== JSON.stringify(originalProjectOrder)) errors.push(`Project order/count changed on ${slug}`);
}

async function filesIn(directory) {
  const result = [];
  for (const item of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, item.name);
    if (item.isDirectory()) result.push(...await filesIn(file));
    else result.push(file);
  }
  return result;
}

async function resolveLocal(reference, pageFile) {
  const value = decode(reference);
  if (!value || /^(https?:|mailto:|tel:|data:|blob:)/i.test(value)) return;
  if (/^javascript:/i.test(value)) { errors.push(`Unsafe link in ${pageFile}`); return; }
  const pageURL = 'https://local.invalid/' + path.relative(dist, pageFile).split(path.sep).join('/');
  let url;
  try { url = new URL(value, pageURL); } catch { errors.push(`Malformed reference ${value}`); return; }
  if (url.host !== 'local.invalid') return;
  report.localReferences++;
  if (url.pathname.startsWith('/media/') && url.searchParams.get('v') !== '20261023') errors.push(`Media URL can reuse a cached migration error: ${value}`);
  const relative = decodeURIComponent(url.pathname).replace(/^\//, '');
  let target = path.resolve(dist, relative);
  if (target !== dist && !target.startsWith(dist + path.sep)) { errors.push(`Out-of-root reference ${value}`); return; }
  if (existsSync(target) && (await stat(target)).isDirectory()) target = path.join(target, 'index.html');
  if (!existsSync(target) && existsSync(target + '.html')) target += '.html';
  if (!existsSync(target)) { errors.push(`Broken local reference ${value} in ${path.relative(dist, pageFile)}`); return; }
  if (url.hash && path.extname(target) === '.html') {
    const fragment = decodeURIComponent(url.hash.slice(1));
    if (fragment) {
      const contents = built.get(target) || await readFile(target, 'utf8');
      if (!contents.includes(`id="${fragment}"`)) errors.push(`Missing fragment ${value} in ${path.relative(dist, pageFile)}`);
    }
  }
}

for (const file of await filesIn(dist)) {
  report.outputFiles++;
  const size = (await stat(file)).size;
  report.largestAssetBytes = Math.max(report.largestAssetBytes, size);
  if (size > 25 * 1024 * 1024) errors.push(`Exceeds Cloudflare 25 MiB asset limit: ${path.relative(dist, file)}`);
  if (path.extname(file) !== '.html') continue;
  const html = built.get(file) || await readFile(file, 'utf8');
  if (/(?:https?:)?\/\/[^"'<>\s]*(?:myportfolio\.com|adobe\.io|typekit\.net)/i.test(html)) {
    report.adobeDependencies++;
    errors.push(`Deployed HTML still references Adobe: ${path.relative(dist, file)}`);
  }
  for (const match of html.matchAll(/\s(?:src|href|poster)="([^"]*)"/g)) await resolveLocal(match[1], file);
  for (const match of html.matchAll(/\ssrcset="([^"]*)"/g)) {
    for (const entry of match[1].split(',')) await resolveLocal(entry.trim().split(/\s+/)[0], file);
  }
  for (const match of html.matchAll(/<img\b([^>]+)>/g)) {
    if (/\ssrc=/.test(match[1]) && !/\salt="[^"]+"/.test(match[1])) errors.push(`Image missing alt text in ${path.relative(dist, file)}`);
  }
}
assert(existsSync(path.join(dist, '404.html')), 'A top-level 404.html is required for real 404 handling on Cloudflare Pages.');
assert(report.outputFiles < 20000, 'The site exceeds the Cloudflare Workers Free asset count.');
const pdf = await readFile(path.join(dist, profile.resume));
if (!pdf.subarray(0, 5).equals(Buffer.from('%PDF-'))) errors.push('Résumé download is not a valid PDF.');
// Exercise the email composer without opening a mail app or sending a message.
const contactHandlers = {};
const contactFields = { name: 'Visitor & colleague', email: 'visitor@example.com', message: 'Hello John — robotics & design?\nA second line.' };
let contactValid = false;
const contactStatus = { textContent: '' };
const contactForm = { dataset: { recipient: profile.email }, removeAttribute() {}, addEventListener(event, handler) { contactHandlers[event] = handler; }, reportValidity: () => contactValid };
const contactWindow = { matchMedia: () => ({ matches: true }), location: { href: '' } };
runInNewContext(await readFile(path.join(root, 'public/site.js'), 'utf8'), {
  document: { querySelectorAll: () => [], querySelector: selector => selector === '#contact-form' ? contactForm : selector === '#contact-status' ? contactStatus : null },
  window: contactWindow,
  FormData: class { get(name) { return contactFields[name]; } }
});
contactHandlers.submit({ preventDefault() {} });
assert.equal(contactWindow.location.href, '', 'An invalid contact form must not open an email draft.');
contactValid = true;
contactHandlers.submit({ preventDefault() {} });
const draft = new URL(contactWindow.location.href);
assert.equal(draft.protocol, 'mailto:');
assert.equal(draft.pathname, profile.email);
assert.equal(draft.searchParams.get('subject'), 'Portfolio inquiry');
assert.equal(draft.searchParams.get('body'), `${contactFields.message}\n\nFrom: ${contactFields.name}\nReply to: ${contactFields.email}`, 'The draft must preserve punctuation, Unicode, line breaks, and reply details.');

console.log(JSON.stringify(report, null, 2));
if (errors.length) {
  console.error(`\n${errors.length} migration verification failure(s):\n${errors.map(error => `- ${error}`).join('\n')}`);
  process.exit(1);
}
console.log('PASS: original routes, project order, complete text, image order, media, links, résumé, and Cloudflare asset limits.');
