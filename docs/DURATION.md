# Duration Calculation Guide

This document explains how the duration endpoint computes durations for cleaned activities and what rules are applied per activity type.

## Endpoint

- Path: `POST /v1/duration`
- Body (optional): `{ "rules": { "Concrete": 4, "Piping": 6, ... } }`
- Reads: `data/clean_output_latest.json`
- Writes: `data/duration_output_latest.json` and `data/archive/duration_output_YYYYMMDD_HHMMSS.json`
- Response: `{ rows, result: [ ...enriched_records ], files }`

## Type Extraction

Type is derived from `Element Name` using these rules:

1) Install pattern
- If name matches `*_Install_<Type>*`, then `Type = <Type>` with underscores converted to spaces.
  - Example: `CWA_ASU-1A01_-_Install_Piping_Insulation` → `Type = "Piping Insulation"`

2) Set pattern
- If name matches `*_Set_<Anything>*`, then `Type = "Equipment"`.
  - Example: `CWA_ASU-1A02_-_Set_101-V135` → `Type = "Equipment"`

3) Fallback
- If neither pattern matches, `Type = ""` and default duration is used.

Implementation reference: `dataProc/services/duration_service.py` (`_extract_activity_type`).

## Duration Rules (Defaults)

The service merges optional overrides from the request body into these defaults (case-insensitive key match). Duration units are days.

- Equipment: 2.0
- Concrete: 3.0
- Grout: 1.0
- Piling: 2.0
- Piping: 5.0
- Piping Insulation: 3.0
- Cable Tray: 4.0
- Electrical: 5.0
- Instrumentation: 4.0
- UG Conduit: 2.0
- Transformer: 2.0
- Unknown/empty type: 1.0 (fallback)

Implementation reference: `dataProc/services/duration_service.py` (`_default_rules`).

## Equations Per Type

Let `T` be the derived `Type`. Let `R[T]` be the rules map after applying any overrides from the request body (positive numeric values only). Let `Default(T)` be the default value listed above, or `1.0` if `T` is unknown.

- General formula: `Duration = R[T]`, if provided and positive; otherwise `Duration = Default(T)`.
- Equipment: `Duration = R["Equipment"]  or  2.0`
- Concrete: `Duration = R["Concrete"]  or  3.0`
- Grout: `Duration = R["Grout"]  or  1.0`
- Piling: `Duration = R["Piling"]  or  2.0`
- Piping: `Duration = R["Piping"]  or  5.0`
- Piping Insulation: `Duration = R["Piping Insulation"]  or  3.0`
- Cable Tray: `Duration = R["Cable Tray"]  or  4.0`
- Electrical: `Duration = R["Electrical"]  or  5.0`
- Instrumentation: `Duration = R["Instrumentation"]  or  4.0`
- UG Conduit: `Duration = R["UG Conduit"]  or  2.0`
- Transformer: `Duration = R["Transformer"]  or  2.0`
- Unknown/empty type: `Duration = 1.0`

Notes:
- Overrides are coerced to positive floats; non‑positive or invalid values are ignored in favor of defaults.

## Output Record Shape

The endpoint keeps the original cleaned fields, removes raw coordinate fields, and appends the two fields below:

- Removed fields: `X Coordinate`, `Y Coordinate`, `Z Coordinate`, `Position X`, `Position Y`, `Position Z`.
- Added fields:
  - `Type`: derived as above
  - `Duration`: computed per rules

## Examples

1) Install example
- Input `Element Name`: `CWA_ASU-1A00_-_Install_Concrete`
- Type: `Concrete`
- Duration (default): `3.0`

2) Set example
- Input `Element Name`: `CWA_ASU-1A02_-_Set_101-V135`
- Type: `Equipment`
- Duration (default): `2.0`

3) Overrides
- Request body: `{ "rules": { "Concrete": 4, "Piping": 6 } }`
- Concrete activities get `Duration = 4.0`, Piping get `6.0`.

## Operational Notes

- Validation ensures every activity in the output has a non‑null `Duration`.
- The endpoint is idempotent with respect to the current `clean_output_latest.json`.
- To refresh durations after re‑running the clean step, call `/v1/duration` again.

