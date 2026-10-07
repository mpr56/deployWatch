.PHONY: setup db-up db-down db-migrate db-shell seed api web reset

PY := .venv/bin/python
PIP := .venv/bin/pip

setup:                ## one-time: venv, deps, database, schema, fixtures
	python3 -m venv .venv
	$(PIP) install -q -r api/requirements.txt
	cd web && npm install
	cp -n api/.env.example api/.env || true
	$(MAKE) db-up db-migrate seed

db-up:
	docker compose up -d db

db-down:
	docker compose down

db-migrate:
	docker exec -i deploywatch-db psql -U deploywatch -d deploywatch -v ON_ERROR_STOP=1 \
		< api/migrations/001_init.sql

db-shell:
	docker exec -it deploywatch-db psql -U deploywatch -d deploywatch

seed:                 ## wipe and reload fixture monitors + 24h of checks
	cd api && ../$(PY) -m scripts.seed

api:                  ## http://localhost:8000  (docs at /docs)
	cd api && ../$(PY) -m uvicorn app.main:app --reload --port 8000

web:                  ## http://localhost:5173
	cd web && npm run dev

reset: db-down db-up
	sleep 3 && $(MAKE) db-migrate seed
