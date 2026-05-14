# AGENTS Guide

This file defines repository-specific instructions for coding agents working on this project.

## Project Summary

- Project type: Home Assistant custom integration.
- Domain: `lg_tv_serial`.
- Purpose: control compatible LG TVs over serial (local serial port or serial-over-network endpoints supported by serialx).
- Main package: `custom_components/lg_tv_serial`.

## Repo Layout

- `custom_components/lg_tv_serial/__init__.py`: integration setup, teardown, and service registration (`send_raw`).
- `custom_components/lg_tv_serial/config_flow.py`: config flow and connectivity validation.
- `custom_components/lg_tv_serial/coordinator.py`: `DataUpdateCoordinator` and shared integration state.
- `custom_components/lg_tv_serial/lgtv_api.py`: low-level serial protocol implementation and enums.
- `custom_components/lg_tv_serial/media_player.py`: media player entity.
- `custom_components/lg_tv_serial/remote.py`: remote entity.
- `custom_components/lg_tv_serial/select.py`: select entities.
- `custom_components/lg_tv_serial/switch.py`: switch entities.
- `custom_components/lg_tv_serial/helpers.py`: helper decorators/utilities.
- `custom_components/lg_tv_serial/translations/en.json`: user-facing strings and errors.
- `tests/`: test suite.
- `coverage.sh`: local coverage + mypy helper script.

## Setup And Verification

Use these commands from repo root:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements_dev.txt
pytest
./coverage.sh
```

Notes:

- `requirements_dev.txt` pulls runtime requirements and dev tooling.
- `./coverage.sh` runs pytest coverage and mypy (`custom_components --check-untyped-defs`).

## Coding Rules For This Repo

- Keep Home Assistant code async-first.
- Avoid blocking I/O in entity methods or coordinator updates.
- Keep protocol-level logic in `lgtv_api.py`; keep HA entity/platform files thin.
- Use coordinator state (`CoordinatorData`) as the single source of truth for entity state.
- If entity methods optimistically update state, keep updates minimal and consistent with existing patterns.
- Raise translated HA errors where user-facing validation fails (for example config flow and services).
- Preserve compatibility with Home Assistant typing patterns already used in this codebase.

## Error Handling Expectations

- Connection failures should surface as `ConnectionError` at API layer and be converted to HA-specific errors higher up.
- Keep disconnect behavior robust: reconnect/reload behavior is handled in setup callbacks.
- Do not swallow exceptions silently; use targeted exception handling and logging.

## Tests To Add With Changes

When changing behavior, add or update tests in `tests/` for at least one of:

- Config flow validation and error mapping.
- Coordinator update behavior for on/off and unavailable states.
- API command building/parsing and failure handling.
- Entity behavior when TV is off, buffering, or reconnecting.
- Service schema and validation (`send_raw`).

## Files To Avoid Editing Unless Required

- Release helper behavior in `release.py` unless the task is explicitly about releases.

## Versioning And Release Notes

- Integration version lives in `custom_components/lg_tv_serial/manifest.json`.
- `release.py` contains repository release automation and version bump logic.
- Do not bump versions unless the task explicitly asks for release/version changes.

## Change Checklist

Before finishing a task:

- Keep changes scoped to the requested behavior.
- Run relevant tests and type checks when possible.
- Ensure user-visible text has translation coverage where applicable.
- Ensure new logic matches existing HA integration lifecycle patterns.
