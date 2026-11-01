.PHONY: check
check:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/tests -v
	PYTHONDONTWRITEBYTECODE=1 python3 tools/check_site.py
