# Offline site gate

Run `make check` from the repository root. It runs standard-library unittest
tests first, then `tools/check_site.py`; no dependencies or network are needed.
Bytecode caches are disabled. Tests create and clean temporary sites under
`tools/tests/` using the committed fixture in `tools/tests/fixtures/`.

HTML parsing uses `html.parser`. Published HTML pages anywhere in the repository
are checked for exactly one H1, a nonempty title, description and canonical link.
Local href/src/action/poster URLs resolve relative to their page or site root;
directory URLs resolve to index.html. Queries and fragments do not change file
existence checks (fragment IDs are not checked). Absolute URLs on jigonyoo.com,
www.jigonyoo.com and jigonyoo.vercel.app are internal. External URLs are not fetched.
Sitemap URL entries are parsed with standard-library ElementTree. Missing or
malformed sitemap.xml is a site-level issue; missing pages are page-level issues.

Published files are scanned for token shapes without printing matched values.
Infrastructure under tools/, checks/, dot paths and Makefile is excluded, so test
fixtures and scanner patterns are not mistaken for published secrets. The scanner
is a heuristic, not a substitute for a dedicated secret audit.

Public repository claims in visible text (English public repos/repositories,
“All N projects are public”, and Korean 공개 저장소 counts) are compared with
data/facts.json. Script/style text is excluded. The two required recent articles
are also checked even if no page links to them.

baseline.json records existing findings by `(page, rule)` with descriptive details.
`@site` denotes a site-wide finding. New pairs fail with exit code 1; existing
pairs pass. Removed pairs are printed as `고쳐짐` and do not fail. Configuration or
read errors fail with exit code 2. Detail changes within the same pair do not
constitute a new issue. Baselines are never rewritten automatically by the gate;
review any manual baseline change before accepting it.

The initial baseline preserves existing content issues, including the stale 79
repository claim, absent sitemap, missing metadata and one token-shape finding.
No site content or token values were copied into these notes.
