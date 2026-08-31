# Exposure Atlas — bootstrap Makefile (BOOT-050).
# PLT-001 later extends this with the full command set from SPEC 8.3/PLT-001.
PY := .venv/bin/python

.PHONY: bootstrap plan-validate plan-next task-verify gate-verify build-status test

bootstrap:
	uv venv .venv --python 3.11
	uv pip install --python .venv/bin/python jsonschema==4.23.0 pyyaml==6.0.2 pytest==8.3.3

plan-validate:
	$(PY) tools/atlas_plan.py validate

plan-next:
	$(PY) tools/atlas_plan.py next

task-verify:
	$(PY) tools/atlas_plan.py task-verify $(TASK)

gate-verify:
	$(PY) tools/atlas_plan.py gate-verify $(GATE)

build-status:
	$(PY) tools/atlas_plan.py build-status

test:
	$(PY) -m pytest tests/ -q

.PHONY: lint schemas-check release-determinism e2e
lint:
	$(PY) -m ruff check packages tools tests

schemas-check:
	$(PY) -m pytest tests/test_schemas.py -q

release-determinism:
	$(PY) -m pytest tests/test_release.py -q -k determinism

e2e:
	$(PY) -m pytest tests/test_end_to_end.py -q
