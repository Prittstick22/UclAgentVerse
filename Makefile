.PHONY: setup synth test dev-api dev-web fixtures build board data-status
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
data-status:
	@$(PY) -c "import json,hashlib,pathlib;d=pathlib.Path('backend/data/snapshot');m=json.loads((d/'manifest.json').read_text()) if (d/'manifest.json').exists() else {};print('snapshot label:',m.get('label','MISSING'),'| created:',m.get('created_at','?'));f=d/'prices_daily.parquet';print('prices sha256:',hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else 'MISSING');r=pathlib.Path('backend/runs/year.sqlite');print('recorded year:', 'present' if r.exists() else 'not yet')"
