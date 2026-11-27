"""Shared HTML footer rendering and live Pages verification (stdlib only)."""
import argparse
import concurrent.futures
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urljoin

START = '<!-- series-page-footer:start -->'
END = '<!-- series-page-footer:end -->'
NAV = re.compile(r'<nav\b(?=[^>]*(?:id=["\']series-footer["\']|aria-label=["\'](?:Frankie|Frank|Franklin) projects["\']))[^>]*>[\s\S]*?</nav>', re.I)

class Icons(HTMLParser):
    def __init__(self, base_url=''):
        super().__init__()
        self.base_url = base_url
        self.href = ''
        self.items = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.href = urljoin(self.base_url, attrs.get('href', ''))
        if tag == 'img':
            self.items.append((attrs.get('alt', ''), self.href,
                               urljoin(self.base_url, attrs.get('src', '')),
                               attrs.get('width'), attrs.get('height')))
    def handle_endtag(self, tag):
        if tag == 'a':
            self.href = ''

def icons(content, base_url='', template=False):
    if not template:
        match = NAV.search(content)
        content = match.group() if match else ''
    parser = Icons(base_url)
    parser.feed(content)
    return parser.items

STYLE = """<style>
#series-footer{display:block!important;position:static!important;box-sizing:border-box;width:100%;max-width:100%;margin:0 auto;padding:24px 20px;border-top:1px solid #8883;font:12px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;text-align:center;background:transparent;color:inherit}
#series-footer p{display:block;max-width:960px;margin:0 auto 12px;text-align:center}
#series-footer p:first-of-type{font-size:16px;line-height:44px}
#series-footer p:last-of-type{margin-bottom:0}
#series-footer a{display:inline-block;vertical-align:middle;padding:0;margin:0;border:0;border-radius:0;background:none;box-shadow:none;color:inherit}
#series-footer p:first-of-type a{line-height:0}
#series-footer a::before,#series-footer a::after{content:none!important}
#series-footer img{display:inline-block!important;width:32px!important;height:32px!important;max-width:none!important;object-fit:contain;vertical-align:middle;border:0!important;border-radius:0;box-shadow:none;background:transparent}
#series-footer sub{font:12px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;vertical-align:baseline}
</style>"""

def render(content, template, series):
    label = {'frank': 'Frank', 'franklin': 'Franklin', 'frankie': 'Frankie'}[series]
    revision = hashlib.sha256((STYLE + template).encode()).hexdigest()[:12]
    banner = (START + '\n' + STYLE + '\n<nav id="series-footer" data-series="' + series
              + '" data-template-hash="' + revision + '" aria-label="' + label + ' projects">\n' + template.strip()
              + '\n</nav>\n' + END)
    if START in content or END in content:
        if content.count(START) != 1 or content.count(END) != 1:
            raise ValueError('Malformed shared Pages footer markers')
        result = re.sub(re.escape(START) + r'[\s\S]*?' + re.escape(END), lambda _: banner, content)
    else:
        matches = list(NAV.finditer(content))
        if not matches:
            return content
        if len(matches) != 1:
            raise ValueError('Multiple legacy series banners found')
        match = matches[0]
        result = content[:match.start()] + banner + content[match.end():]
    if icons(result) != icons(template, template=True):
        raise ValueError('Rendered footer does not match the shared template')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--series', required=True, choices=['frank', 'franklin', 'frankie'])
    parser.add_argument('--site-root', type=Path)
    parser.add_argument('--templates-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--audit-url', action='append', default=[])
    args = parser.parse_args()
    template = (args.templates_root / 'assets/footers' / (args.series + '.html')).read_text()
    if args.audit_url:
        expected = icons(template, template=True)
        def audit(url):
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read().decode()
            actual = icons(content, url)
            revision = hashlib.sha256((STYLE + template).encode()).hexdigest()[:12]
            current = f'data-template-hash="{revision}"' in content
            return {'url': url, 'match': actual == expected and current, 'expected': len(expected), 'actual': len(actual), 'current_template': current}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(audit, args.audit_url))
        print(json.dumps(results, ensure_ascii=False, indent=2))
        if not all(row['match'] for row in results):
            raise SystemExit(1)
        return
    if args.site_root is None:
        parser.error('--site-root or --audit-url is required')
    if not args.site_root.is_dir():
        raise ValueError('Site output directory is missing')
    pages = []
    for path in sorted(args.site_root.rglob('*.html')):
        before = path.read_text()
        after = render(before, template, args.series)
        if START in after:
            pages.append(path)
        if after != before:
            path.write_text(after)
    if not pages:
        raise ValueError('No series banners found in the built site; refusing an unverified deployment')
    print(f'Verified {len(pages)} Pages banners against the shared {args.series} template.')


if __name__ == '__main__':
    main()
