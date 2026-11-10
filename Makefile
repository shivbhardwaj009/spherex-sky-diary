.PHONY: setup test mock processing detection matching spectra pipeline web help

PYTHON ?= python

help:
	@echo "SPHEREx Sky Diary"
	@echo "Available targets:"
	@echo "  setup      - Install Python dependencies"
	@echo "  mock       - Generate synthetic mock data (candidates.json & cutouts)"
	@echo "  test       - Run pytest test suite"
	@echo "  processing - Run Module 2 image processing"
	@echo "  detection  - Run Module 3 mover detection"
	@echo "  matching   - Run Module 4 catalog matching"
	@echo "  spectra    - Run Module 5 spectral extraction"
	@echo "  pipeline   - Run complete offline scientific pipeline"
	@echo "  web        - Start web application"

setup:
	$(PYTHON) -m pip install -r requirements.txt

mock:
	$(PYTHON) data/mock/generate_mock.py

test:
	$(PYTHON) -m pytest tests/

processing:
	$(PYTHON) -m detection.processing

detection:
	$(PYTHON) -m detection.movers

matching:
	$(PYTHON) -m matching --config config/settings.yaml --offline

spectra:
	$(PYTHON) -m spectra --config config/settings.yaml

pipeline:
	$(PYTHON) -m detection.processing
	$(PYTHON) -m detection.movers
	$(PYTHON) -m matching --config config/settings.yaml --offline
	$(PYTHON) -m spectra --config config/settings.yaml

web:
	npm run dev

