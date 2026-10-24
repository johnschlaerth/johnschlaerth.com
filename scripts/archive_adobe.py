#!/usr/bin/env python3
"""Archive the complete public Adobe Portfolio and produce portable content.

Run once during migration (network required): python3 scripts/archive_adobe.py
Dependencies: beautifulsoup4, requests, Pillow. Original media remain unmodified;
transient playback access values are redacted from saved HTML and metadata.
"""
from __future__ import annotations
import concurrent.futures as futures
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse, urldefrag, unquote, urlunparse
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://johnschlaerth.myportfolio.com'
HOST = urlparse(BASE).netloc
ARCHIVE = ROOT / 'archive' / 'adobe'
MEDIA = ROOT / 'public' / 'media'
CONTENT = ROOT / 'content'
for directory in [ARCHIVE / 'pages', ARCHIVE / 'metadata', MEDIA, CONTENT]:
    directory.mkdir(parents=True, exist_ok=True)

CAPTURED = datetime.now(timezone.utc).isoformat()
failures = []
asset_sources = {}
capture_hashes = {}
previous_pages_file = ARCHIVE / 'metadata' / 'pages.json'
previous_pages = {p['slug']: p for p in json.loads(previous_pages_file.read_text())} if previous_pages_file.exists() else {}

ACCESS_FIELDS = frozenset({
    'hdnts', 'apikey', 'accesstoken', 'authtoken', 'token', 'nonce',
    'playerkey', 'mediatoken', 'authorization', 'clientsecret',
    'signature', 'keypairid',
})

def access_field(name):
    compact = re.sub(r'[-_]', '', unquote(str(name))).lower()
    return compact in ACCESS_FIELDS or compact.startswith(('xamz', 'xgoog'))

def redact_url(url):
    """Remove access parameters while preserving ordinary media transform URLs."""
    decoded = html.unescape(url)
    parsed = urlparse(decoded)
    if not parsed.scheme or not parsed.query:
        return url
    parameters = parsed.query.split('&')
    retained = [pair for pair in parameters if not access_field(pair.split('=', 1)[0])]
    if len(retained) == len(parameters):
        return url
    result = urlunparse(parsed._replace(query='&'.join(retained)))
    return html.escape(result, quote=False) if '&amp;' in url else result

def redact_text(value):
    """Sanitize serialized HTML, URLs, config fields, and error messages."""
    value = re.sub(r'https?://[^\s\"\'<>]+', lambda match: redact_url(match.group()), value)
    # Non-content player configuration may expose access values outside a URL.
    field = r'(?:hdnts|api[_-]?key|access[_-]?token|auth[_-]?token|token|nonce|playerkey|mediatoken|authorization|client[_-]?secret|signature|key[_-]?pair[_-]?id)'
    value = re.sub(
        rf'([\"\']{field}[\"\']\s*:\s*)([\"](?:\\.|[^\"\\])*[\"]|[\'](?:\\.|[^\'\\])*[\']|[^,}}\r\n]+)',
        lambda match: match.group(1) + 'null', value, flags=re.I,
    )
    value = re.sub(
        rf'\s+(?:data-)?{field}\s*=\s*([\"](?:\\.|[^\"\\])*[\"]|[\'](?:\\.|[^\'\\])*[\'])',
        '', value, flags=re.I,
    )
    return value

def redact_data(value):
    if isinstance(value, dict):
        return {key: redact_data(item) for key, item in value.items() if not access_field(key)}
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value

def same_video_resource(left, right):
    a, b = urlparse(html.unescape(left or '')), urlparse(html.unescape(right or ''))
    return bool(a.hostname and a.hostname == b.hostname and a.path == b.path)

def get(url):
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=(15, 90), verify='/etc/ssl/certs/ca-certificates.crt', headers={'User-Agent': 'Mozilla/5.0 (compatible; OwnerPortfolioMigration/1.0)'})
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)

def slug_of(url):
    return urlparse(url).path.strip('/') or 'index'

def internal(url):
    p = urlparse(url)
    return p.netloc == HOST and not p.path.startswith(('/site/', '/dist/')) and not p.query

def dump(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(redact_data(data), ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)

def page_file(slug):
    return ARCHIVE / 'pages' / (slug.replace('/', '__') + '.html')

def save_page(url, body):
    slug = slug_of(url)
    captured_sha = hashlib.sha256(body.encode()).hexdigest()
    previous = previous_pages.get(slug, {})
    capture_hashes[slug] = (previous.get('original_capture_sha256', captured_sha)
                            if captured_sha == previous.get('sha256') else captured_sha)
    page_file(slug).write_text(redact_text(body))

pages_html = {}
home = ROOT.parent / 'adobe-home.html'
pages_html[BASE + '/'] = home.read_text() if home.exists() else get(BASE + '/').text
for name in ['sitemap.xml', 'robots.txt']:
    try:
        result = get(BASE + '/' + name)
        (ARCHIVE / name).write_text(redact_text(result.text))
    except Exception as exc:
        failures.append({'url': BASE + '/' + name, 'stage': 'discovery', 'error': str(exc)})

todo = {BASE + '/' + p for p in ['work', 'about', 'resume', 'social-media', 'contact']}
sitemap = ARCHIVE / 'sitemap.xml'
if sitemap.exists():
    todo.update(re.findall(r'<loc>(.*?)</loc>', sitemap.read_text()))

def fetch_page(url):
    path = page_file(slug_of(url))
    if path.exists():
        return url, path.read_text()
    return url, get(url).text

while True:
    for url, body in list(pages_html.items()):
        soup = BeautifulSoup(body, 'html.parser')
        for a in soup.select('a[href]'):
            link = urldefrag(urljoin(url, a['href']))[0]
            if internal(link):
                todo.add(link.rstrip('/') or BASE + '/')
    current = sorted(todo - set(pages_html))
    if not current:
        break
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(fetch_page, url): url for url in current}
        for future in futures.as_completed(jobs):
            url = jobs[future]
            try:
                _, body = future.result()
                pages_html[url] = body
                save_page(url, body)
                print('PAGE', slug_of(url), len(body), flush=True)
            except Exception as exc:
                failures.append({'url': url, 'stage': 'page', 'error': str(exc)})
                pages_html[url] = ''
for url, body in pages_html.items():
    if body:
        save_page(url, body)

# Canonicalize the same homepage body if a root URL with no slash is linked.
pages_html.pop(BASE, None)
home_soup = BeautifulSoup(pages_html[BASE + '/'], 'html.parser')
project_index = {}
for a in home_soup.select('a.project-cover'):
    slug = a['href'].strip('/')
    project_index[slug] = {
        'slug': slug,
        'title': a.select_one('.title').get_text(' ', strip=True),
        'year': a.select_one('.date').get_text(' ', strip=True) if a.select_one('.date') else '',
        'cover_tag': a.select_one('img'),
    }
navigation = []
for a in home_soup.select('a[href]'):
    href = a['href']
    if href in ['/work', '/about', '/resume', '/social-media', '/contact'] and not any(n['href'] == href for n in navigation):
        navigation.append({'label': a.get_text(' ', strip=True), 'href': href})

def register_asset(url, page, role='image'):
    if not url or url.startswith('data:'):
        return None
    url = html.unescape(urljoin(BASE, url))
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        return None
    extension = Path(parsed.path).suffix.lower() or '.bin'
    basename = Path(parsed.path).name
    # Preserve Adobe's readable asset identifier; hash distinguishes crop variants.
    filename = re.sub(r'[^A-Za-z0-9._-]', '-', Path(basename).stem)[:100] + '-' + hashlib.sha256(redact_url(url).encode()).hexdigest()[:10] + extension
    item = asset_sources.setdefault(url, {'url': url, 'local_path': '/media/' + filename, 'pages': [], 'roles': []})
    if page not in item['pages']:
        item['pages'].append(page)
    if role not in item['roles']:
        item['roles'].append(role)
    return item['local_path']

def image_url(tag):
    # The lightbox URL is the original source, even when the displayed preview is scaled.
    lightbox = tag.find_parent(class_='js-lightbox')
    if lightbox and lightbox.get('data-src'):
        return lightbox['data-src']
    # Media collection images sometimes put the original on their immediate wrapper.
    ancestor = tag.parent
    while ancestor and ancestor.name not in ('body', 'main'):
        if ancestor.get('data-src') and 'cdn.myportfolio.com' in ancestor['data-src'] and ancestor.name != 'img':
            return ancestor['data-src']
        if 'project-module' in ancestor.get('class', []):
            break
        ancestor = ancestor.parent
    srcset = tag.get('data-srcset') or tag.get('srcset') or ''
    choices = []
    for part in srcset.split(','):
        bits = part.strip().split()
        if bits:
            choices.append((int(re.sub(r'\D','', bits[1])) if len(bits)>1 else 0, bits[0]))
    if choices:
        return max(choices)[1]
    return tag.get('data-src') or tag.get('src')

def image_record(tag, slug, role='image'):
    original = image_url(tag)
    src = register_asset(original, slug, role)
    return {'src': src, 'original_url': original, 'alt': tag.get('alt','').strip()}

def sanitize_text(fragment, slug):
    soup = BeautifulSoup(str(fragment), 'html.parser')
    for bad in soup.select('script,style'):
        bad.decompose()
    for tag in soup.find_all(True):
        attrs = {}
        if tag.name == 'a' and tag.get('href'):
            target = urljoin(BASE, tag['href'])
            if urlparse(target).netloc == HOST:
                target = urlparse(target).path
            if re.search(r'\.(pdf|zip|docx?|pptx?|mp4|mov|stl|step|py|cpp)(?:\?|$)', target, re.I):
                target = register_asset(target, slug, 'download')
            attrs['href'] = target
            if tag.get('target') == '_blank':
                attrs.update(target='_blank', rel='noopener noreferrer')
        elif tag.name == 'img':
            rec = image_record(tag, slug)
            attrs = {'src':rec['src'], 'alt':rec['alt']}
        elif tag.name in ['td','th']:
            attrs = {k:v for k,v in tag.attrs.items() if k in ['colspan','rowspan']}
        tag.attrs = attrs
    return str(soup)

global_images = {}
for key, node, attribute in [
    ('social_image', home_soup.select_one('meta[property="og:image"]'), 'content'),
    ('favicon', home_soup.select_one('link[rel="icon"], link[rel="shortcut icon"]'), 'href'),
]:
    if node and node.get(attribute):
        original = urljoin(BASE, node[attribute])
        global_images[key] = {'src': register_asset(original, 'global', key), 'original_url': original, 'alt': ''}

pages = []
for url, body in pages_html.items():
    if not body:
        continue
    slug = slug_of(url)
    soup = BeautifulSoup(body, 'html.parser')
    title_node = soup.select_one('.page-header .title, h1')
    title = title_node.get_text(' ',strip=True) if title_node else ('Portfolio Projects' if slug in ['index','work'] else soup.title.get_text(' ',strip=True))
    description_node = soup.select_one('.page-header .description')
    description = description_node.get_text(' ',strip=True) if description_node else ''
    record = {'slug':slug, 'source_url':url, 'title': title, 'kind':'project' if slug in project_index else ('index' if slug in ['index','work'] else 'page'), 'description':description, 'year':project_index.get(slug,{}).get('year',''), 'modules':[]}
    if slug in project_index:
        record['cover'] = image_record(project_index[slug]['cover_tag'],slug,'cover')
    canvas = soup.select_one('#project-modules') or soup.select_one('.page-content') or soup.select_one('main')
    if record['kind'] != 'index' and canvas:
        modules = canvas.select('.project-module')
        if not modules:
            modules = [canvas]
        for module in modules:
            classes = module.get('class',[])
            text_node = module.select_one('.rich-text')
            images = []
            seen = set()
            for img in module.select('img'):
                item = image_record(img,slug)
                if item['src'] and item['src'] not in seen:
                    images.append(item)
                    seen.add(item['src'])
            embeds = []
            for embed in module.select('iframe,video,audio,object,embed'):
                source = embed.get('src') or embed.get('data-src') or embed.get('data')
                sources = [source] if source else []
                sources += [s.get('src') for s in embed.select('source[src]')]
                for source in sources:
                    source = urljoin(BASE,source)
                    local = register_asset(source,slug,'video' if embed.name == 'video' else 'embedded-file') if urlparse(source).netloc.endswith('myportfolio.com') or re.search(r'\.(pdf|mp4|mov|webm|mp3)(?:\?|$)',source,re.I) else None
                    embeds.append({'tag':embed.name,'src':local or source,'original_url':source,'title':embed.get('title','')})
            caption_node = module.select_one('.caption,figcaption,.project-caption')
            caption = caption_node.get_text(' ',strip=True) if caption_node else ''
            if text_node:
                record['modules'].append({'type':'text','html':sanitize_text(text_node,slug),'text':text_node.get_text(' ',strip=True)})
            elif 'text' in classes:
                record['modules'].append({'type':'text','html':sanitize_text(module,slug),'text':module.get_text(' ',strip=True)})
            elif images:
                record['modules'].append({'type':'gallery' if len(images)>1 else 'image','images':images,'caption':caption})
            if embeds:
                record['modules'].append({'type':'embed','embeds':embeds,'html':str(module)})
            if module.find('form'):
                record['modules'].append({'type':'form','text':module.get_text(' ',strip=True),'fields':[{'name':x.get('name'),'type':x.get('type'), 'placeholder':x.get('placeholder')} for x in module.select('input,textarea')], 'html':str(module)})
            if not any([text_node, images, embeds, module.find('form')]) and module.get_text(' ',strip=True):
                record['modules'].append({'type':'text','html':sanitize_text(module,slug),'text':module.get_text(' ',strip=True)})
        record['text'] = canvas.get_text(' ',strip=True)
    else:
        record['text'] = ''
    record['external_links'] = []
    for a in (canvas or soup).select('a[href]'):
        target = urljoin(BASE,a['href'])
        if urlparse(target).netloc != HOST and not target.startswith('javascript:'):
            entry = {'url':target,'text':a.get_text(' ',strip=True)}
            if entry not in record['external_links']:
                record['external_links'].append(entry)
    # Capture Adobe-hosted CSS/background/download references outside ordinary images.
    for match in re.finditer(r'https?://cdn\.myportfolio\.com/[^\s\"\'<>]+', body):
        source = html.unescape(match.group())
        # Image variants are archived through their original. Non-image files must be explicit.
        if re.search(r'\.(pdf|mp4|mov|webm|zip|mp3|wav)(?:\?|$)',source,re.I):
            register_asset(source,slug,'linked-media')
    record['raw_html'] = str(page_file(slug).relative_to(ROOT))
    record['sha256'] = hashlib.sha256(page_file(slug).read_bytes()).hexdigest()
    if capture_hashes.get(slug) != record['sha256']:
        record['original_capture_sha256'] = capture_hashes[slug]
        record['archive_redaction'] = 'Transient playback access parameters removed; portfolio content and media preserved.'
    pages.append(record)

ordered_slugs = ['index','work','about','resume','social-media','contact']+list(project_index)
pages.sort(key=lambda p: ordered_slugs.index(p['slug']) if p['slug'] in ordered_slugs else len(ordered_slugs))
site = {'source_url':BASE, 'captured_at':CAPTURED, 'navigation':navigation,'global_images':global_images,'projects':[{k:v for k,v in project_index[p['slug']].items() if k!='cover_tag'} | {'cover':p['cover']} for p in pages if p['kind']=='project'], 'pages':pages}
dump(CONTENT / 'site.json',site)
dump(ARCHIVE / 'metadata' / 'assets.json',list(asset_sources.values()))
print('INVENTORY',len(pages),'pages',len(project_index),'projects',len(asset_sources),'media files',flush=True)

def download_asset(item):
    path = ROOT / 'public' / item['local_path'].lstrip('/')
    if path.exists() and path.stat().st_size:
        content = path.read_bytes()
        content_type = ''
    else:
        response = get(item['url'])
        content = response.content
        content_type = response.headers.get('content-type','')
        if 'text/html' in content_type:
            raise ValueError('Expected media; received HTML')
        path.write_bytes(content)
    item.update(bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),content_type=content_type,cloudflare_oversize=len(content)>25*1024*1024)
    try:
        with Image.open(path) as image:
            item.update(width=image.width,height=image.height,format=image.format,frames=getattr(image,'n_frames',1))
    except Exception:
        pass
    return item

with futures.ThreadPoolExecutor(max_workers=6) as pool:
    jobs={pool.submit(download_asset,item):item for item in asset_sources.values()}
    for i,future in enumerate(futures.as_completed(jobs),1):
        item=jobs[future]
        try:
            future.result()
        except Exception as exc:
            item['error']=str(exc)
            failures.append({'url':item['url'],'stage':'asset','error':str(exc)})
        if i%10==0 or i==len(jobs):
            print('MEDIA',i,'/',len(jobs),flush=True)
        dump(ARCHIVE/'metadata'/'assets.json',list(asset_sources.values()))

def enrich(value):
    if isinstance(value,dict):
        if value.get('original_url') in asset_sources:
            asset=asset_sources[value['original_url']]
            for key in ['width','height','frames','format','bytes']:
                if key in asset:
                    value[key]=asset[key]
        for v in value.values():
            enrich(v)
    elif isinstance(value,list):
        for v in value:
            enrich(v)
enrich(site)
# A public Adobe-hosted video may require separate HLS preservation/transcoding.
# The checked-in map describes the completed original-video archive and its local
# playback derivative. Retain that completed work when refreshing HTML/images.
video_map_path = ARCHIVE / 'metadata' / 'preserved-videos.json'
preserved_videos = json.loads(video_map_path.read_text()) if video_map_path.exists() else []
for video in preserved_videos:
    if not (ROOT / 'public' / video['module']['src'].lstrip('/')).is_file():
        continue
    for page in site['pages']:
        if page['slug'] != video['page']:
            continue
        for index, module in enumerate(page['modules']):
            if any(same_video_resource(embed.get('original_url'), video['module']['original_url']) for embed in module.get('embeds',[])):
                page['modules'][index] = video['module']
dump(CONTENT/'site.json',site)
report={'source_url':BASE,'captured_at':CAPTURED,'pages':len(pages),'projects':len(project_index),'assets':len(asset_sources),'downloaded_assets':sum('sha256' in a for a in asset_sources.values()),'downloaded_bytes':sum(a.get('bytes',0) for a in asset_sources.values()),'oversize_assets':[a['local_path'] for a in asset_sources.values() if a.get('cloudflare_oversize')],'failures':failures,'external_embeds':[{'page':p['slug'],**e} for p in pages for m in p['modules'] for e in m.get('embeds',[]) if not e['src'].startswith('/media/')],'preserved_videos':preserved_videos,'module_counts':{p['slug']:len(p['modules']) for p in pages}}
dump(ARCHIVE/'metadata'/'report.json',report)
dump(ARCHIVE/'metadata'/'pages.json',[{k:p[k] for k in ['slug','source_url','title','kind','raw_html','sha256','original_capture_sha256','archive_redaction'] if k in p} for p in pages])
print(json.dumps(redact_data(report),indent=2),flush=True)
