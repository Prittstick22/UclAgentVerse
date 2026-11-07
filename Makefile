.PHONY: setup synth test dev-api dev-web fixtures build board
PY ?= python3
setup:
	cd backend && $(PY) -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install
synth:
	cd backend && $(PY) scripts/make_synthetic_snapshot.py
test:
	cd backend && $(PY) -m pytest -q
dev-api:
	cd backend && uvicorn app.main:app --reload --port 8000
dev-web:
	cd frontend && npm run dev
fixtures:
	cd backend && $(PY) scripts/make_fixtures.py
build:
	docker compose build
board:
	$(PY) scripts/board.py list --open
