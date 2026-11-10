.PHONY: setup test mock pipeline web help

PYTHON ?= python

help:
	@echo "SPHEREx Sky Diary"
	@echo "Available targets:"
	@echo "  setup    - Install Python dependencies"
	@echo "  mock     - Generate synthetic mock data (candidates.json & cutouts)"
	@echo "  test     - Run pytest test suite"
	@echo "  pipeline - Run offline processing pipeline"
	@echo "  web      - Start web application"

setup:
	$(PYTHON) -m pip install -r requirements.txt

mock:
	$(PYTHON) data/mock/generate_mock.py

test:
	$(PYTHON) -m pytest tests/

pipeline:
	$(PYTHON) data/mock/generate_mock.py

web:
	npm run dev
