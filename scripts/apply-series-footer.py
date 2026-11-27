#!/usr/bin/env python3
"""Apply the shared series banner without changing project documentation or signatures."""
import argparse
from pathlib import Path
import re

START = '<!-- series-footer:start -->'
END = '<!-- series-footer:end -->'


def apply(content, banner):
    if START in content or END in content:
        if content.count(START) != 1 or content.count(END) != 1:
            raise ValueError('Malformed or duplicate series footer markers')
        return re.sub(re.escape(START) + r'[\s\S]*?' + re.escape(END), lambda _: banner, content)
    for paragraph in re.finditer(r'<p\b[^>]*>[\s\S]*?</p>', content):
        if 'brand/series/' not in paragraph.group() and '/assets/series/' not in paragraph.group():
            continue
        end = paragraph.end()
        caption = re.match(r'\s*<p\b[^>]*>\s*<sub>[\s\S]*?</sub>\s*</p>', content[end:])
        if caption:
            end += caption.end()
        return content[:paragraph.start()] + banner + content[end:]
    # A new project gets the same banner, before its existing handwritten signature.
    signature = re.search(r'<p align="right">[\s\S]*?</p>\s*$', content)
    if signature:
        return content[:signature.start()].rstrip() + '\n\n' + banner + '\n\n' + content[signature.start():]
    return content.rstrip() + '\n\n---\n\n' + banner + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--series', required=True, choices=['frank', 'franklin', 'frankie'])
    parser.add_argument('--templates-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--repo-root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    banner = (args.templates_root / 'assets/footers' / (args.series + '.html')).read_text().strip()
    for name in ['README.md', 'README.zh-CN.md', 'README_zh.md']:
        path = args.repo_root / name
        if path.exists():
            before = path.read_text()
            after = apply(before, banner)
            if after != before:
                path.write_text(after)
                print('Updated ' + name)


if __name__ == '__main__':
    main()
