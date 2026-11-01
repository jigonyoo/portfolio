import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.check_site import Page, compare, inspect, main


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = (Path(__file__).parent / 'fixtures/valid.html').read_text()
        self.write('index.html', self.source)
        self.write('data/facts.json', json.dumps({'public_repos': 94}))
        for name in ('check-then-act-paid-twice', 'unique-not-null-3-of-17'):
            self.write(f'writing/{name}.html', self.source)
        self.sitemap()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def sitemap(self):
        urls = ['https://jigonyoo.com/' + str(p.relative_to(self.root)) for p in self.root.rglob('*.html')]
        self.write('sitemap.xml', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{u}</loc></url>' for u in urls) + '</urlset>')

    def keys(self):
        return {(f['page'], f['rule']) for f in inspect(self.root)}

    def test_valid_offline_site(self):
        self.assertEqual(self.keys(), set())

    def test_metadata_and_h1(self):
        self.write('index.html', '<h1>A</h1><h1>B</h1><title> </title><meta name="description" content="">')
        self.assertEqual(self.keys(), {('index.html', r) for r in ('title', 'h1', 'description', 'canonical')})

    def test_links(self):
        self.write('index.html', self.source + '<a href="writing/check-then-act-paid-twice.html?x=1#x">ok</a><img src="/missing.png"><a href="https://jigonyoo.com/no.html">bad</a>')
        self.assertEqual(self.keys(), {('index.html', 'internal-link')})

    def test_relative_encoded_directory_and_escape(self):
        self.write('nested/index.html', self.source + '<a href="../writing/%63heck-then-act-paid-twice.html">ok</a><a href="/nested/">ok</a>')
        self.sitemap()
        self.assertEqual(self.keys(), set())
        self.write('index.html', self.source + '<a href="/../../escape.html">bad</a>')
        self.assertIn(('index.html', 'internal-link'), self.keys())

    def test_sitemap_missing_malformed_and_coverage(self):
        (self.root / 'sitemap.xml').unlink()
        self.assertIn(('@site', 'sitemap'), self.keys())
        self.write('sitemap.xml', '<broken')
        self.assertIn(('@site', 'sitemap'), self.keys())
        self.write('sitemap.xml', '<urlset/>')
        self.assertEqual(sum(rule == 'sitemap-coverage' for _, rule in self.keys()), 3)

    def test_required_article(self):
        (self.root / 'writing/check-then-act-paid-twice.html').unlink()
        self.assertIn(('writing/check-then-act-paid-twice.html', 'required-page'), self.keys())

    def test_counts_across_markup(self):
        self.write('index.html', self.source + '<p>All <b>79</b> projects are public</p>')
        self.assertIn(('index.html', 'public-repos'), self.keys())

    def test_token_shapes_redacted(self):
        tokens = ['github_' + 'pat_example', 'gh' + 'p_example', 'sk-' + 'ant-example', 'AK' + 'IA' + 'A' * 16, '-----BEGIN RSA ' + 'PRIVATE KEY-----']
        for token in tokens:
            with self.subTest(token=token[:4]):
                self.write('sample.txt', token)
                findings = inspect(self.root)
                self.assertIn(('sample.txt', 'secret-token'), self.keys())
                self.assertNotIn(token, json.dumps(findings))

    def test_baseline_new_fixed_and_detail_changes(self):
        known = [{'page': 'a', 'rule': 'h1', 'details': ['old']}, {'page': 'b', 'rule': 'title'}]
        current = [{'page': 'a', 'rule': 'h1', 'details': ['changed']}, {'page': 'c', 'rule': 'h1'}]
        self.assertEqual(compare(current, known), ([('c', 'h1')], [('b', 'title')]))

    def test_infrastructure_excluded(self):
        self.write('tools/tests/fixtures/bad.html', 'gh' + 'p_example')
        self.assertEqual(self.keys(), set())

    def test_empty_metadata(self):
        page = Page('<title></title><link rel="canonical" href=" "><meta name="description" content=" ">')
        self.assertFalse(page.canonical)
        self.assertFalse(page.description)

    def test_cli_new_known_and_fixed(self):
        self.write('index.html', self.source + '<a href="missing.html">Broken</a>')
        self.write('checks/baseline.json', '[]')
        with patch('sys.argv', ['check_site.py', '--root', str(self.root)]):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 1)
            self.assertIn('NEW: index.html [internal-link]', output.getvalue())
            self.write('checks/baseline.json', json.dumps(inspect(self.root)))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            self.write('index.html', self.source)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 0)
            self.assertIn('고쳐짐: index.html [internal-link]', output.getvalue())

    def test_missing_facts_and_zero_h1(self):
        (self.root / 'data/facts.json').unlink()
        self.write('index.html', self.source.replace('<h1>Test</h1>', ''))
        self.assertIn(('@site', 'facts'), self.keys())
        self.assertIn(('index.html', 'h1'), self.keys())


if __name__ == '__main__':
    unittest.main()
