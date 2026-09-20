# QA Report — RC Rock Crawling Timing System v2.0

Tested in the build environment after the V2 UI/security integration.

## Result summary

**PASS — release candidate approved for deployment, subject to final physical camera check on the real Windows PC.**

## Automated backend tests

`python -m pytest -q`

**14 tests passed.**

Coverage includes:

1. FINISH before first START is rejected.
2. First START begins a prepared commercial session.
3. Too-short / physically impossible lap is rejected.
4. Valid START→FINISH creates exactly one lap.
5. Duplicate FINISH cannot increment the lap count.
6. Second START→FINISH creates lap 2 correctly.
7. Best-lap aggregation selects the fastest completed lap.
8. Expired sessions reject later results.
9. SQLite integrity check returns `ok`.
10. Online SQLite backup opens successfully and passes integrity check.
11. Fastest leaderboard sorting is correct.
12. All seven generated ArUco markers remain detectable under synthetic rotation and seven concurrent sessions avoid DB-lock errors.
13. Gate debounce preserves the first confirmed entry timestamp.
14. **V2 endurance test:** seven simultaneous players × 25 valid laps each = **175 completed laps** with correct lap counts, 2.000 s test best laps and database integrity `ok`.

## Maximum-player repeat test

The V2 seven-player / 25-lap-each endurance test was run **five additional consecutive times**.

Result: **5/5 PASS**.

That represents another 875 simulated valid lap completions across repeated max-capacity runs without a database-lock or timing-state failure.

## Front-end syntax validation

Inline JavaScript extracted from:

- `operator.html`
- `tv.html`
- `settings.html`

was checked using Node.js `node --check`.

Result: **3/3 PASS**.

## Real server smoke test

The actual Uvicorn/FastAPI application was launched. The following returned HTTP 200:

- `/operator`
- `/tv`
- `/settings`
- `/api/cars`
- `/api/live`
- `/api/leaderboard?period=today&limit=8`
- `/api/health`
- `/static/images/track_bg.jpg`

The build environment has no USB camera, so OpenCV correctly reports camera-unavailable while the rest of the service stays online. Physical camera recognition is therefore the one item that must be rechecked on the real installation PC after upgrade.

## Security hardening QA

Verified on live HTTP responses:

- `Content-Security-Policy` present.
- `X-Content-Type-Options: nosniff` present.
- `X-Frame-Options: DENY` present.
- `Cache-Control: no-store` present on dynamic pages/APIs.
- Customer/car dynamic strings pass through HTML escaping before `innerHTML` rendering.
- Invalid leaderboard limit (`100000`) → HTTP 422.
- Invalid leaderboard period → HTTP 422.
- Unknown marker ID for manual event → HTTP 400.
- Invalid manual gate value → HTTP 422.
- Application remains bound to `127.0.0.1` by default.
- Interactive API docs remain disabled.

## Windows startup bug fixed

The previous Windows error:

`ZoneInfoNotFoundError: No time zone found with key Asia/Colombo`

is addressed by including `tzdata` in `requirements.txt`. The Windows installer therefore installs the timezone database automatically on a fresh V2 install/update.

## UI QA

- Real venue photos are local static assets; no web/CDN dependency exists.
- TV dashboard contains no track-length widget.
- TV dashboard contains no today's-driver-count widget.
- TV dashboard contains no today's-session-count widget.
- 7 live car rows are allocated explicitly.
- Fastest Lap and Most Laps support Top 8.
- Today / week / month cycle retained.
- Operator and settings pages retain all existing operational controls and endpoints.
- User-supplied text is escaped in Operator/TV rendering.

## Physical final acceptance required after installation

Before customer launch on the real track:

1. Confirm the USB camera source is correct and remains stable.
2. Confirm saved START/FINISH polygons survived the upgrade.
3. Confirm IDs 1–7 are detected at both gates.
4. Complete several real laps with all seven physical vehicles.
5. Compare TV and Operator lap/time values.
6. Run the real camera continuously for at least four hours before treating a new hardware installation as fully commissioned.

The V2 upgrade script preserves the existing calibrated config/database specifically to reduce deployment risk.
