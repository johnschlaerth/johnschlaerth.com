#!/usr/bin/env python3
"""Restore the frozen, checksum-verified portfolio media on a fresh checkout.

Uses Python's standard library and system certificate store. FFmpeg/ffprobe are
required only to reconstruct/check the website playback video. This is a one-time
preservation tool, not a normal website build step. Run before Adobe URLs expire.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = frozenset({'cdn.myportfolio.com', 'cdn-prod-ccv.adobe.com'})
PUBLIC_VIDEO_HOSTS = ALLOWED_HOSTS | {'johnschlaerth.myportfolio.com', 'www-ccv.adobe.io'}
MAX_PLAYBACK_BYTES = 25 * 1024 * 1024


def destination(relative: str) -> Path:
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or '\\' in relative:
        raise ValueError(f'Unsafe repository path: {relative}')
    result = (ROOT / relative).resolve()
    if not result.is_relative_to(ROOT):
        raise ValueError(f'Path leaves repository: {relative}')
    return result


def public_path(local_path: str) -> Path:
    if not local_path.startswith('/media/'):
        raise ValueError(f'Unexpected public media path: {local_path}')
    return destination('public' + local_path)


def approved_url(url: str, hosts=ALLOWED_HOSTS) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname not in hosts
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('Media source is outside the approved Adobe CDN hosts')
    return url


class ApprovedRedirects(HTTPRedirectHandler):
    def __init__(self, hosts=ALLOWED_HOSTS):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, approved_url(newurl, self.hosts))


def public_text(url):
    """Read public playback data in memory; never persist or log access parameters."""
    approved_url(url, PUBLIC_VIDEO_HOSTS)
    opener = build_opener(ApprovedRedirects(PUBLIC_VIDEO_HOSTS))
    request = Request(url, headers={'User-Agent': 'OwnerPortfolioMigration/1.0'})
    for attempt in range(3):
        try:
            with opener.open(request, timeout=60) as response:
                approved_url(response.geturl(), PUBLIC_VIDEO_HOSTS)
                return response.read().decode('utf-8')
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


class PublicVideoFrame(HTMLParser):
    def __init__(self, video_id):
        super().__init__()
        self.video_id = video_id
        self.player_url = None

    def handle_starttag(self, tag, attrs):
        if tag != 'iframe':
            return
        source = dict(attrs).get('src', '')
        parsed = urlparse(source)
        if (parsed.hostname == 'www-ccv.adobe.io'
                and parsed.path == f'/v1/player/ccv/{self.video_id}/embed'):
            self.player_url = approved_url(source, PUBLIC_VIDEO_HOSTS)


def current_video_locations(source):
    """Discover fresh public CDN access in memory from the owner's live page.

    Stored metadata contains only stable identifiers and unsigned resource URLs.
    The public player response is intentionally never written to disk or output.
    """
    parser = PublicVideoFrame(source['video_id'])
    parser.feed(public_text(source['source_page']))
    if not parser.player_url:
        raise RuntimeError('The public source page no longer exposes its video player')
    player = public_text(parser.player_url)
    match = re.search(r'window\.ccv\$serverData\s*=\s*(\{.*?\});', player, re.S)
    if not match:
        raise RuntimeError('Could not read the public video playback configuration')
    metadata = json.loads(match.group(1))
    master = approved_url(metadata['m3u8URL'])
    lines = public_text(master).splitlines()
    rendition = None
    for index, line in enumerate(lines[:-1]):
        if 'RESOLUTION=' + source['resolution'] in line:
            rendition = lines[index + 1].strip()
            break
    if not rendition or rendition.startswith('#'):
        raise RuntimeError('The original video resolution is no longer publicly offered')
    playlist = urlparse(urljoin(master, rendition))
    playlist = approved_url(urlunparse(playlist._replace(query=urlparse(master).query)))
    if urlparse(playlist).path != urlparse(source['unsigned_playlist_url']).path:
        raise RuntimeError('Public playback identifies a different original video rendition')
    poster = approved_url(metadata['posterframe'])
    return {'playlist': playlist, 'poster': poster}


def read_json(relative):
    return json.loads(destination(relative).read_text())


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def correct(path, expected_bytes, expected_sha):
    return (path.is_file() and path.stat().st_size == expected_bytes
            and digest(path) == expected_sha)


def restore(job, verify_only):
    path, url, expected_bytes, expected_sha = job
    if correct(path, expected_bytes, expected_sha):
        return 'verified'
    if verify_only:
        raise RuntimeError(f'Missing or corrupt media: {path.relative_to(ROOT)}')
    approved_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.download')
    for attempt in range(3):
        try:
            opener = build_opener(ApprovedRedirects())
            request = Request(url, headers={'User-Agent': 'OwnerPortfolioMigration/1.0',
                                           'Accept-Encoding': 'identity'})
            sha, count = hashlib.sha256(), 0
            with opener.open(request, timeout=90) as response, temporary.open('wb') as output:
                approved_url(response.geturl())
                if response.status != 200:
                    raise ValueError(f'Unexpected HTTP status {response.status}')
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > expected_bytes:
                        raise ValueError('Downloaded media exceeds recorded byte count')
                    sha.update(chunk)
                    output.write(chunk)
            if count != expected_bytes or sha.hexdigest() != expected_sha:
                raise ValueError('Downloaded media does not match archived size/SHA-256')
            temporary.replace(path)
            return 'downloaded'
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def playback_info(path):
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
        '-show_entries', 'stream=codec_name,width,height', '-of', 'json', str(path)
    ], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    video = next(s for s in data['streams'] if s.get('codec_name') == 'h264')
    if not any(s.get('codec_name') == 'aac' for s in data['streams']):
        raise ValueError('Playback video is missing its AAC audio stream')
    duration = float(data['format']['duration'])
    if not 408.0 <= duration <= 409.0:
        raise ValueError(f'Playback video duration is incomplete: {duration}')
    if (video.get('width'), video.get('height')) != (1024, 576):
        raise ValueError('Unexpected playback video dimensions')
    if not 0 < path.stat().st_size <= MAX_PLAYBACK_BYTES:
        raise ValueError('Playback video exceeds the Cloudflare Pages file limit')
    return {'duration': duration, 'bytes': path.stat().st_size, 'width': 1024, 'height': 576}


def restore_playback(verify_only):
    mapping_path = destination('archive/adobe/metadata/preserved-videos.json')
    mappings = json.loads(mapping_path.read_text())
    changed = False
    for entry in mappings:
        module = entry['module']
        path = public_path(module['src'])
        if correct(path, module['bytes'], entry['sha256']):
            playback_info(path)
            print('Playback video: verified existing file', flush=True)
            continue
        if verify_only:
            raise RuntimeError('Playback video is missing or does not match its recorded hash')
        playlist = destination(entry['original_archive'])
        for line in playlist.read_text().splitlines():
            if line and not line.startswith('#') and not re.fullmatch(r'index-\d+\.ts', line):
                raise ValueError('Offline video playlist contains an unexpected source')
            if line.startswith(('#EXT-X-KEY', '#EXT-X-MAP')):
                raise ValueError('Offline video playlist must not reference remote resources')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.stem + '.restore.mp4')
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-threads', '2',
            '-filter_threads', '1', '-i', str(playlist), '-vf', 'scale=-2:576',
            '-c:v', 'libx264', '-preset', 'veryfast', '-b:v', '390k',
            '-maxrate', '500k', '-bufsize', '780k', '-threads', '2',
            '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', str(temporary)
        ], check=True)
        measured = playback_info(temporary)
        new_hash = digest(temporary)
        temporary.replace(path)
        module.update(measured)
        entry['sha256'] = new_hash
        changed = True
        print(f'Playback video: rebuilt and verified ({measured["bytes"]:,} bytes)', flush=True)
    if changed:
        # Encoded bytes can vary across FFmpeg versions; original media checksums
        # never change. Only the derived MP4's measured metadata is refreshed.
        write_json(mapping_path, mappings)
        site_path = destination('content/site.json')
        site = json.loads(site_path.read_text())
        for entry in mappings:
            for page in site['pages']:
                if page['slug'] == entry['page']:
                    for index, module in enumerate(page['modules']):
                        if module.get('type') == 'video' and module.get('src') == entry['module']['src']:
                            page['modules'][index] = entry['module']
        write_json(site_path, site)
        report_path = destination('archive/adobe/metadata/report.json')
        report = json.loads(report_path.read_text())
        report['preserved_videos'] = mappings
        write_json(report_path, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Verify existing files without downloading or writing')
    args = parser.parse_args()
    assets = read_json('archive/adobe/metadata/assets.json')
    jobs = [(public_path(a['local_path']), approved_url(a['url']), int(a['bytes']), a['sha256']) for a in assets]
    folder = 'archive/adobe/video/fb-v12/'
    source = read_json(folder + 'source.json')
    base = approved_url(source['unsigned_playlist_url'])
    source_query = urlparse(base).query
    segments = read_json(folder + 'segments.json')
    names = [line.strip() for line in destination(folder + 'source-index.m3u8').read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    if set(names) != {s['file'] for s in segments} or len(names) != len(segments):
        raise ValueError('Original playlist and segment checksum manifest do not agree')
    for segment in segments:
        name = segment['file']
        if not re.fullmatch(r'index-\d+\.ts', name):
            raise ValueError('Unexpected video segment filename')
        parsed = urlparse(urljoin(base, name))
        url = approved_url(urlunparse(parsed._replace(query=source_query)))
        jobs.append((destination(folder + name), url, int(segment['bytes']), segment['sha256']))
    if len({job[0] for job in jobs}) != len(jobs):
        raise ValueError('Duplicate output paths in preservation manifests')
    if any(size <= 0 or not re.fullmatch(r'[0-9a-f]{64}', sha) for _, _, size, sha in jobs):
        raise ValueError('Invalid byte count or checksum in preservation manifest')
    if not args.verify_only and any(
        urlparse(url).hostname == 'cdn-prod-ccv.adobe.com' and not correct(path, size, sha)
        for path, url, size, sha in jobs
    ):
        # Resolve access only when a CDN-hosted original is actually missing.
        # These URLs live in this process's memory and are never serialized.
        current = current_video_locations(source)
        current_playlist = urlparse(current['playlist'])
        refreshed = []
        for path, url, size, sha in jobs:
            parsed = urlparse(url)
            if parsed.hostname == 'cdn-prod-ccv.adobe.com':
                if parsed.path == urlparse(current['poster']).path:
                    url = current['poster']
                elif path.suffix == '.ts':
                    segment = urlparse(urljoin(current['playlist'], path.name))
                    url = approved_url(urlunparse(segment._replace(query=current_playlist.query)))
                else:
                    raise ValueError('Unrecognized original video resource')
            refreshed.append((path, url, size, sha))
        jobs = refreshed
    counts = {'verified': 0, 'downloaded': 0}
    failures = []
    print(f'Checking {len(assets)} original images and {len(segments)} original video segments', flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(restore, job, args.verify_only): job[0] for job in jobs}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                counts[future.result()] += 1
            except Exception as exc:
                failures.append(f'{futures[future].relative_to(ROOT)}: {exc}')
            if index % 25 == 0 or index == len(jobs):
                print(f'Original media {index}/{len(jobs)}; {len(failures)} failures', flush=True)
    if failures:
        raise RuntimeError('Restoration failed; no checksum failures are ignored:\n' + '\n'.join(failures))
    restore_playback(args.verify_only)
    print(f'SUCCESS: {counts["verified"]} verified, {counts["downloaded"]} restored; '
          f'{len(jobs)} exact original media files; playback video verified.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
