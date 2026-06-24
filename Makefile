# Convenience targets. Run `make setup` once, then `make backend` and
# `make frontend` in two terminals (or `make seed` to populate demo data).

.PHONY: setup backend frontend seed test clean

setup:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

seed:
	cd backend && . .venv/bin/activate && python -m scripts.run_pipeline

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && . .venv/bin/activate && python -m pytest -q

clean:
	rm -f backend/cosailor.db
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
