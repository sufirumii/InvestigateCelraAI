.PHONY: install run verify test gazetteer clean

install:
	pip install -r requirements-dev.txt

run:
	python run.py

verify:          ## prove every configured source is reachable and returning data
	PYTHONPATH=backend python scripts/verify_sources.py

test:
	PYTHONPATH=backend pytest -q

gazetteer:
	python scripts/build_gazetteer.py

clean:
	rm -rf var/*.db var/*.db-wal var/*.db-shm .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
