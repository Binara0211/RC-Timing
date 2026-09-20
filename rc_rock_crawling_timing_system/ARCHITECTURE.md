# System Architecture — v2.0

## Timing/data flow

`USB Camera(s) → OpenCV Frame Capture → ArUco ID Detection → Gate Debouncer → Timing State Machine → SQLite → Local API → Operator UI / TV UI`

All runtime components remain on the same PC. Normal operation does not require cloud services or internet access.

## V2 UI architecture

The presentation layer is intentionally separated from the timing engine:

- `app/templates/operator.html` — staff session/control interface.
- `app/templates/tv.html` — public live scoreboard.
- `app/templates/settings.html` — camera ROI setup/diagnostics.
- `app/static/app.css` — shared premium RC Arena visual system.
- `app/static/images/` — local venue photography.

The UI reads existing local APIs (`/api/live`, `/api/leaderboard`, `/api/health`, etc.). No timing calculations were moved into the browser.

## Timing state machine

Prepared:

- START → Running + Lap Open
- FINISH → Ignored

Running / no lap open:

- START → Lap Open
- FINISH → Ignored

Running / lap open:

- FINISH → minimum-lap validation → record lap → Lap Closed
- START → ignored to prevent double-start

Expired:

- session closes at paid end timestamp and new laps are blocked by default.

## Reliability

- SQLite WAL journaling.
- `synchronous=FULL`.
- short `BEGIN IMMEDIATE` writes protected by an application write lock.
- single Uvicorn worker.
- one camera reader thread per configured USB camera.
- timestamp-derived countdowns rather than decrementing browser timers.
- hourly online database snapshots.
- manual timing fallback remains audit logged.

## V2 security boundary

The application remains local-only by default (`127.0.0.1`). V2 also adds response hardening headers, input bounds/enums for exposed control parameters, and HTML escaping for user-provided text rendered by the dashboard. The public TV page is display-only; session creation and manual timing actions remain on the operator endpoints/UI.
