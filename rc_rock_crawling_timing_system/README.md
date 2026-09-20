# RC Rock Crawling Timing System v2.0

Offline commercial timing, session management and leaderboard software for a seven-car RC rock-crawling attraction.

## V2 visual system

The backend timing/database/camera workflow remains the same, while all public and staff pages were redesigned around the actual course photographs supplied for the venue. The theme uses dark rock textures, amber construction-zone highlights, neon green live-status accents, blue RC-headlight accents and large high-contrast typography suitable for mall TV viewing.

Main pages:

- `http://127.0.0.1:8765/operator` — premium staff/operator console.
- `http://127.0.0.1:8765/tv` — premium full-screen public scoreboard.
- `http://127.0.0.1:8765/settings` — camera/START/FINISH calibration.

## Core timing behavior

1. Staff enters the customer name and assigns RC-1…RC-7.
2. Session is prepared but paid time does not start yet.
3. The assigned ArUco marker entering START begins the paid timer and opens lap 1.
4. A valid FINISH closes the lap and records the lap time.
5. Another FINISH cannot count until that car returns to START.
6. At 00:00 the session is closed and new results are blocked by default.
7. Daily, weekly and monthly rankings are generated from the local SQLite database.

## TV dashboard

The V2 TV page includes:

- Play Planet / RC Arena brand lockup.
- Real course photographs integrated into the dashboard.
- Live clock and date.
- Live 7-car table with status, time left, laps and best lap.
- Fastest Lap Top 8.
- Most Laps Top 8.
- Today / This Week / This Month automatic rotation.
- Track Record hero panel.
- Record-change highlight animation.
- “Can You Beat The Record?” footer.

It intentionally does **not** show track length, today's driver count or today's session count.

## Marker mapping

- RC-1 → ArUco 1
- RC-2 → ArUco 2
- RC-3 → ArUco 3
- RC-4 → ArUco 4
- RC-5 → ArUco 5
- RC-6 → ArUco 6
- RC-7 → ArUco 7

Marker dictionary: `DICT_4X4_50`.

## Existing V1 installation

If your current system is already calibrated and working, do **not** overwrite its database/config manually. Extract V2 somewhere temporary and run:

`scripts\UPGRADE_EXISTING_V1.bat`

The upgrade keeps the existing `config`, camera ROIs, `data/rc_timing.db`, backups, exports, logs and markers.

## Fresh installation

1. Install 64-bit Python 3.12.
2. Copy the full project to `C:\RC-Timing\rc_rock_crawling_timing_system`.
3. Run `scripts\INSTALL_WINDOWS.bat` once while internet is available.
4. Run `scripts\LAUNCH_OPERATOR.bat`.
5. Open `/settings`, confirm the USB camera and calibrate START/FINISH.
6. Open `/tv` on the public display and press F11.

The fresh package is set to 1280×720 / 30 FPS and camera source index 1, matching the current laptop + external USB camera setup. Change `camera.source` to 0 or 2 if Windows enumerates the USB camera differently.

## Reliability / security changes in V2

- Local-only bind (`127.0.0.1`) remains the default.
- SQLite WAL + FULL synchronous durability retained.
- Customer/car names are escaped before dynamic UI insertion.
- Security headers added: CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, Referrer Policy and browser Permissions Policy.
- API parameter bounds added for leaderboard limits and gate/manual-event values.
- `tzdata` added to requirements for reliable `Asia/Colombo` support on Windows Python.
- Seven-car 25-lap-each endurance test added.

See `QA_REPORT.md` for final validation results.
