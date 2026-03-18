# DESIGN.md

This repository was generated from the written requirements included in the prompt.

The original governing document was provided as `deejay_sets_api_design_v2.docx`, but the current environment can't directly extract `.docx` contents. If you want the exact wording from that file mirrored here, paste the text or provide a PDF export.

## Section 5: API Endpoints

All endpoints return the standard success envelope:

`{ "data": ..., "meta": { "count": <n>, "version": "<API_VERSION>" } }`

Errors return:

`{ "error": { "code": "...", "message": "..." } }`

### Sets

* `GET /v1/sets` — list sets (`year`, `venue`, `date_from`, `date_to`, `limit=50`, `offset=0`)
* `GET /v1/sets/{id}` — single set with full track list
* `GET /v1/sets/{id}/tracks` — ordered track list for a set

### Tracks

* `GET /v1/tracks` — query tracks (`artist`, `title`, `genre`, `bpm_min`, `bpm_max`, `year`, `data_quality`, `limit=50`, `offset=0`)
* `GET /v1/tracks/{id}` — single track play with set context

### Catalog

* `GET /v1/catalog` — list catalog entries (`artist`, `title`, `confidence`, `min_play_count`, `limit`, `offset`)
* `GET /v1/catalog/{id}` — catalog entry with play history
* `PATCH /v1/catalog/{id}` — update `genre`, `bpm`, `release_year` (source becomes `manual`); protected

### Evaluations

* `GET /v1/evaluations` — list findings (`repo`, `dimension`, `severity`, `limit`, `offset`)
* `GET /v1/evaluations/summary` — aggregate by severity and dimension
* `POST /v1/evaluations` — write findings; protected

### Stats

* `GET /v1/stats/overview`
* `GET /v1/stats/by-year`
* `GET /v1/stats/top-artists`
* `GET /v1/stats/top-tracks`

### Ingest

* `POST /v1/ingest` — accept a set with track list, run reconciliation, return set id + catalog stats; protected

## Reconciliation + Normalization

Normalization and reconciliation rules are implemented in:
* `src/deejay_sets_api/services/normalization.py`
* `src/deejay_sets_api/services/reconciliation.py`

