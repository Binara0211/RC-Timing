# Deployment Guide — RC Rock Crawling Timing System v2.0

## Recommended path for the current working installation

Because the existing V1 timing/backend is already working and calibrated, use the **upgrade path** rather than a destructive fresh install.

1. Close the current RC server with `Ctrl+C` in its black Command Prompt window.
2. Extract the V2 ZIP to a temporary directory, e.g. `C:\RC-Timing-V2`.
3. Double-click `scripts\UPGRADE_EXISTING_V1.bat` inside the extracted V2 folder.
4. The script targets `C:\RC-Timing\rc_rock_crawling_timing_system` by default.
5. It backs up the replaced application/UI files to an `upgrade_backup_YYYYMMDD_HHMMSS` folder.
6. It preserves the current working `config`, camera START/FINISH polygons, `data/rc_timing.db`, backups, exports, logs and markers.
7. It updates Python dependencies, including `tzdata`.
8. Start with `scripts\LAUNCH_OPERATOR.bat`.

## Daily launch

1. Connect the external USB webcam.
2. Close Windows Camera / Zoom / Teams / OBS if they are using the webcam.
3. Double-click `scripts\LAUNCH_OPERATOR.bat`.
4. Staff page: `http://127.0.0.1:8765/operator`.
5. Camera page: `http://127.0.0.1:8765/settings`.
6. TV page: `http://127.0.0.1:8765/tv`.
7. Put the TV browser on the second display and press F11.

## Fresh install only

The included fresh `config/config.json` is pre-set to:

```json
"source": 1,
"finish_source": null,
"width": 1280,
"height": 720,
"fps": 30
```

This matches the current 720p/30 FPS external USB webcam setup where the built-in laptop webcam is camera 0 and the USB webcam is camera 1. On another mini PC the USB camera may enumerate as 0; change only `camera.source` and restart.

## Visual assets

The supplied venue photographs are packaged under `app/static/images/`:

- `track_bg.jpg` — full course background.
- `crawler_hero.jpg` — camera/settings hero.
- `crawler_bridge.jpg` — crawler bridge hero.
- `track_action.jpg` — course action image.
- `track_action_2.jpg` — footer/action image.

They are local files and require no internet connection.

## TV behavior

The TV automatically rotates its leaderboard period every 20 seconds:

- Today
- This Week
- This Month

The live driver table always stays current. The track-record hero uses the first entry from the current fastest-lap leaderboard period. A changed record triggers a short visual highlight.

## Backup / data safety

The persistent database is `data/rc_timing.db`.

The application performs startup, hourly and shutdown backups and supports a secondary backup directory. Do not manually replace the live database while the server is running.

When upgrading from V1, the included upgrade script intentionally does not replace the persistent data/config directories.

## Commercial commissioning after V2 upgrade

UI changes do not change the physical marker/camera calibration, but before reopening to customers:

1. Confirm `/operator`, `/tv` and `/settings` all load.
2. Confirm the external USB camera is still selected.
3. Confirm saved START/FINISH zones are present.
4. Test IDs 1–7 under the camera.
5. Prepare seven test sessions.
6. Complete at least one START→FINISH lap per car.
7. Confirm live TV values match Operator values.
8. Confirm Fastest Lap and Most Laps populate.
9. Leave the system running for at least 30 minutes after upgrade before customer launch; existing full commercial commissioning requirements still apply to new camera/track changes.
