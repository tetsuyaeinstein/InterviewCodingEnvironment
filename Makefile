# OPTIONAL convenience aliases for macOS/Linux. The canonical interface is `python -m lab ...`
# (works everywhere, including Windows without make).
PY ?= .venv/bin/python
ID ?= SQL-021

.PHONY: venv install up down status migrate seed seed-medium seed-large reset show run check check-all verify selftest session progress banks lint

venv:
	python3 -m venv .venv
install: venv
	$(PY) -m pip install -e '.[dev]'
up:
	docker compose up -d
down:
	docker compose down
status:
	$(PY) -m lab db status
migrate:
	$(PY) -m lab db migrate
seed:
	$(PY) -m lab db seed --size small
seed-medium:
	$(PY) -m lab db seed --size medium
seed-large:
	$(PY) -m lab db seed --size large --yes
reset:
	$(PY) -m lab db reset --confirm
show:
	$(PY) -m lab show $(ID)
run:
	$(PY) -m lab run $(ID)
check:
	$(PY) -m lab check $(ID)
check-all:
	$(PY) -m lab check-all
verify:
	$(PY) -m lab verify
selftest:
	$(PY) -m pytest -q
session:
	$(PY) -m lab session --minutes 45 --mix sql,python
progress:
	$(PY) -m lab progress
banks:
	$(PY) -m lab dev build-banks
lint:
	$(PY) -m lab dev lint
