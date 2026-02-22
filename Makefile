.PHONY: format lint test

format:
	cd apps/api && ruff format .

lint:
	cd apps/api && ruff check .

test:
	cd apps/api && pytest -q
