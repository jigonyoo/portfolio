#!/usr/bin/env python3
"""Offline checks of published files; baseline identity is (page, rule).

Infrastructure (tools/, checks/, dot paths, Makefile) is not published content.
No matched token values are included in diagnostics.
"""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

HOSTS = {'jigonyoo.com', 'www.jigonyoo.com', 'jigonyoo.vercel.app'}
LATEST = ('writing/check-then-act-paid-twice.html', 'writing/unique-not-null-3-of-17.html')
TOKEN = re.compile(r'github_pat_|ghp_|sk-ant-|AKIA[A-Z0-9]{16}|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----')
COUNTS = re.compile(r'\b(\d+)\s+public\s+repos(?:itories)?\b|\bAll\s+(\d+)\s+projects\s+are\s+public\b|공개\s*저장소\s*(\d+)\s*개|(\d+)\s*개(?:의)?\s*공개\s*저장소', re.I)


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.h1 = 0
        self.title = []
        self.in_title = False
        self.hidden = 0
        self.text = []
        self.description = False
        self.canonical = False
        self.links = []
        self.og_images = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1':
            self.h1 += 1
        if tag == 'title':
            self.in_title = True
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'meta' and attrs.get('name', '').lower() == 'description':
            self.description |= bool(attrs.get('content', '').strip())
        if tag == 'meta' and attrs.get('property', '').lower() == 'og:image':
            self.og_images.append(attrs.get('content', '').strip())
        if tag == 'link' and 'canonical' in attrs.get('rel', '').lower().split():
            self.canonical |= bool(attrs.get('href', '').strip())
        for attr in ('href', 'src', 'action', 'poster'):
            if attrs.get(attr):
                self.links.append(attrs[attr])

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.hidden:
            self.text.append(data)


def published(path):
    return not any(p.startswith('.') or p in ('tools', 'checks', '__pycache__', 'node_modules')
                   for p in path.parts) and path.name != 'Makefile'


def local_target(root, page, url):
    parts = urlsplit(url)
    if parts.scheme and parts.scheme not in ('http', 'https'):
        return None
    if parts.netloc and parts.hostname not in HOSTS:
        return None
    path = unquote(parts.path)
    target = root / path.lstrip('/') if path.startswith('/') or parts.netloc else root / page.parent / path
    if not path:
        target = root / page if not parts.netloc else root
    target = target.resolve()
    if target.is_relative_to(root.resolve()) and (target.is_dir() or path.endswith('/')):
        target /= 'index.html'
    return target


def inspect(root):
    root = Path(root).resolve()
    findings = {}

    def add(page, rule, detail):
        findings.setdefault((str(page), rule), set()).add(detail)

    files = sorted(p for p in root.rglob('*') if published(p.relative_to(root)) and p.is_file() and not p.is_symlink())
    pages = [p for p in files if p.suffix.lower() == '.html']
    try:
        facts = json.loads((root / 'data/facts.json').read_text())
        count = facts['public_repos']
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError('invalid count')
    except (OSError, ValueError, KeyError, TypeError):
        count = None
        add('@site', 'facts', 'Missing or invalid facts public_repos')
    for path in files:
        if TOKEN.search(path.read_bytes().decode('utf-8', errors='replace')):
            add(path.relative_to(root), 'secret-token', 'Token-shaped string detected (value redacted)')
    for path in pages:
        name = path.relative_to(root)
        page = Page(path.read_text(encoding='utf-8'))
        if page.h1 != 1:
            add(name, 'h1', f'Expected one H1; found {page.h1}')
        if not ''.join(page.title).strip():
            add(name, 'title', 'Missing nonempty title')
        if not page.description:
            add(name, 'description', 'Missing nonempty meta description')
        if not page.canonical:
            add(name, 'canonical', 'Missing canonical link')
        for image in page.og_images:
            try:
                target = local_target(root, name, image)
                valid = bool(image) and (target is None or (target.is_relative_to(root) and target.is_file()))
            except ValueError:
                valid = False
            if not valid:
                add(name, 'og-image', 'Open Graph image URL does not resolve to a file')
        for link in page.links:
            try:
                target = local_target(root, name, link)
                valid = target is None or (target.is_relative_to(root) and target.is_file())
            except ValueError:
                valid = False
            if not valid:
                add(name, 'internal-link', 'Internal URL does not resolve to a file')
        if count is not None:
            for match in COUNTS.finditer(' '.join(page.text)):
                actual = int(next(g for g in match.groups() if g is not None))
                if actual != count:
                    add(name, 'public-repos', f'Copy says {actual}; facts say {count}')
    for name in LATEST:
        if not (root / name).is_file():
            add(name, 'required-page', 'Required latest article missing')
    sitemap = root / 'sitemap.xml'
    if not sitemap.is_file():
        add('@site', 'sitemap', 'Missing sitemap.xml')
    else:
        try:
            tree = ET.fromstring(sitemap.read_text(encoding='utf-8'))
            targets = {local_target(root, Path('index.html'), node.text.strip())
                       for node in tree.iter() if node.tag.split('}')[-1] == 'loc' and node.text}
            for path in pages:
                if path.relative_to(root) != Path('404.html') and path not in targets:
                    add(path.relative_to(root), 'sitemap-coverage', 'Page absent from sitemap.xml')
        except (ET.ParseError, ValueError):
            add('@site', 'sitemap', 'Invalid sitemap.xml')
    return [{'page': page, 'rule': rule, 'details': sorted(details)}
            for (page, rule), details in sorted(findings.items())]


def compare(findings, baseline):
    current = {(f['page'], f['rule']) for f in findings}
    known = {(f['page'], f['rule']) for f in baseline}
    return sorted(current - known), sorted(known - current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        baseline = json.loads((args.root / 'checks/baseline.json').read_text())
        findings = inspect(args.root)
        new, fixed = compare(findings, baseline)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'CHECK ERROR: {type(exc).__name__}')
        return 2
    for label, items in [('NEW', new), ('고쳐짐', fixed)]:
        for page, rule in items:
            print(f'{label}: {page} [{rule}]')
    print(f'{len(findings)} current issue pairs; {len(new)} new; {len(fixed)} fixed')
    return int(bool(new))


if __name__ == '__main__':
    raise SystemExit(main())
