#!/usr/bin/env python3
"""Refresh profile tiles from declared public project artwork (stdlib only).

logo-sources.json is the public artwork contract. Update the listed project brand
file when changing a logo. Entries marked public-series-mirror follow a published
copy, not a private repository. Private changes need that public copy refreshed.

The hourly workflow and manual dispatch use no cross-repository credentials.
A source failure stops publication; the last valid icons stay in the README.
"""
import base64
import struct
import concurrent.futures
import copy
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)

def svg(tag, attrs):
    return ET.Element(f'{{{NS}}}{tag}', attrs)

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'SonghaiFan-profile-logo-sync'})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('SVG exceeds 2 MB')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        width, height = struct.unpack('>II', data[16:24])
        root = svg('svg', {'viewBox': f'0 0 {width} {height}'})
        root.append(svg('image', {'width': str(width), 'height': str(height),
                                 'href': 'data:image/png;base64,' + base64.b64encode(data).decode()}))
    else:
        root = ET.fromstring(data)
    if root.tag != f'{{{NS}}}svg':
        raise ValueError('Expected an SVG document')
    return data, root

def tile(source, mode):
    if mode == 'board':
        # The whiteboard surface is the app tile, with no second frame around it.
        board = copy.deepcopy(next(el for el in source if el.tag == f'{{{NS}}}svg'))
        board.attrib.update(viewBox='48 48 416 418', width='256', height='256')
        board.attrib.pop('x', None)
        board.attrib.pop('y', None)
        return board
    if mode == 'series':
        return source
    source = copy.deepcopy(source)
    if mode == 'mirrored-icon':
        source = next(el for el in source if el.tag == f'{{{NS}}}svg')
    fill = 'none'
    # Retain the original full-size background, moving it onto the outer tile.
    background = next((el for el in source if el.tag == f'{{{NS}}}rect'
                       and el.get('width') == '256' and el.get('height') == '256'), None)
    if background is not None:
        fill = background.get('fill', 'none')
        source.remove(background)
    paths = list(source.iter(f'{{{NS}}}path'))
    # Legacy Poker artwork includes a white export canvas and a green app tile.
    if mode == 'poker' and len(paths) > 1 and paths[0].get('d', '').startswith('M2.042,7.5'):
        fill = re.search(r'fill:([^;]+)', paths[1].get('style', '')).group(1)
        for old in paths[:2]:
            next(parent for parent in source.iter() if old in list(parent)).remove(old)
    # The original Life List uses holes in its blue panel for the white glyphs.
    if mode == 'list' and paths and paths[0].get('d', '').startswith('M63.792 35'):
        mark = paths[0]
        fill = mark.get('fill')
        mark.set('d', mark.get('d').split('Z', 1)[1])
        mark.set('fill', '#ffffff')
    root = svg('svg', {'viewBox': '0 0 256 256', 'width': '256', 'height': '256'})
    frame = {'x': '0', 'y': '0', 'width': '256', 'height': '256', 'rx': '56', 'fill': fill}
    if fill == 'none':
        frame.update(x='2', y='2', width='252', height='252', stroke='#888888',
                     **{'stroke-opacity': '0.32', 'stroke-width': '4'})
    root.append(svg('rect', frame))
    source.attrib.update(x='24', y='24', width='208', height='208')
    root.append(source)
    return root

def refresh(item, source):
    root = copy.deepcopy(tile(source, item['mode']))
    if item.get('badge'):
        badge = item['badge']
        if badge not in {'iOS', 'API'}:
            raise ValueError(f'Unsupported badge: {badge}')
        root.append(svg('rect', {'x': '126', 'y': '180', 'width': '126', 'height': '72',
                                'rx': '20', 'fill': '#242424', 'stroke': '#ffffff',
                                'stroke-width': '5'}))
        label = svg('text', {'x': '189', 'y': '228', 'text-anchor': 'middle',
                             'font-family': 'Arial, Helvetica, sans-serif',
                             'font-size': '42', 'font-weight': '700', 'fill': '#ffffff'})
        label.text = badge
        root.append(label)
    content = '\n'.join(line.rstrip() for line in ET.tostring(root, encoding='unicode').splitlines()) + '\n'
    digest = hashlib.sha256(content.encode()).hexdigest()[:8]
    path = f"assets/apps/{item['id']}-{digest}.svg"
    return item, path, content

def main():
    entries = json.loads((ROOT / 'scripts/logo-sources.json').read_text())
    by_id = {item['id']: item for item in entries}
    entries = [{**by_id[item['logo_of']], **item} if item.get('logo_of') else item
               for item in entries]
    # Fetch each shared source once, so base and variant use identical artwork.
    urls = list(dict.fromkeys(item['url'] for item in entries))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        sources = dict(zip(urls, pool.map(fetch, urls)))
    # Resolve every source before writing, so a missing source cannot publish a partial update.
    results = [refresh(item, sources[item['url']][1]) for item in entries]
    readme = (ROOT / 'README.md').read_text()
    for item, path, content in results:
        pattern = r'src="[^"]+"(?= width="32" height="32" alt="' + re.escape(item['alt']) + r'")'
        readme, count = re.subn(pattern, f'src="{path}"', readme)
        if count != 1:
            raise ValueError(f"Expected one README image for {item['id']}, found {count}")
    assets = ROOT / 'assets/apps'
    assets.mkdir(parents=True, exist_ok=True)
    for _, path, content in results:
        (ROOT / path).write_text(content)
    (ROOT / 'README.md').write_text(readme)
    referenced = {path for _, path, _ in results}
    for old in assets.glob('*.svg'):
        if old.relative_to(ROOT).as_posix() not in referenced:
            old.unlink()
    # Stable aliases let every repository follow central artwork without copying SVGs.
    aliases = ROOT / 'assets/series'
    aliases.mkdir(parents=True, exist_ok=True)
    for item, path, content in results:
        alias = aliases / (item['id'] + '.svg')
        alias.write_text(content)
    # Footer templates are maintained in assets/footers independently of the
    # profile README, whose selection can exclude forks or other projects.
    print(f'Refreshed {len(results)} logos; shared footer templates stay independent.')

if __name__ == '__main__':
    main()
