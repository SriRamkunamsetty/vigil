.PHONY: install lint type test e2e eval serve docker check

PY ?= python

install:
	uv venv --python 3.13 .venv && . .venv/bin/activate && uv pip install -e ".[dev]"

lint:
	ruff check src tests scripts
	ruff format --check src tests scripts

type:
	mypy

test:
	pytest -m "not e2e" --cov --cov-report=term-missing:skip-covered

e2e:
	pytest -m e2e

eval:
	$(PY) -m vigil.eval.run --out artifacts/eval --ui src/vigil/web/results.json
	$(PY) scripts/gen_eval_doc.py

serve:
	uvicorn vigil.api.main:app --reload --port 8080

docker:
	docker build -t vigil:dev .

check: lint type test eval
