CONFIG ?= ~/.ronspot/config.toml
RUN := uv run --locked

.PHONY: install lint format format-check types test check tick dry-run status report

install:
	uv sync --locked

lint:
	$(RUN) ruff check .

format:
	$(RUN) ruff check --fix .
	$(RUN) ruff format .

format-check:
	$(RUN) ruff format --check .

types:
	$(RUN) mypy

test:
	$(RUN) pytest -q

check: lint format-check types test

tick:
	$(RUN) ronspot-sniper --config $(CONFIG)

dry-run:
	$(RUN) ronspot-sniper --config $(CONFIG) --dry-run

status:
	$(RUN) ronspot-sniper --config $(CONFIG) --status

report:
	$(RUN) ronspot-sniper --config $(CONFIG) --report
