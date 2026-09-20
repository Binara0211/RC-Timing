# Changelog

## 2.0.0 — Premium RC Arena UI + hardening

- Rebuilt TV dashboard around the real RC rock-crawling course photographs supplied for the installation.
- New dark rock / neon green / amber visual language inspired by the physical course.
- TV layout includes live drivers, rotating today/week/month leaderboards, fastest-lap record hero, live clock and record-break animation.
- Removed track-length, today-driver-count and today-session-count widgets from the TV design.
- Rebuilt Operator Console in the same visual system without changing timing/business logic.
- Rebuilt Camera Calibration UI in the same visual system.
- Added HTML escaping for dynamic customer/car text rendered into dashboards.
- Added restrictive HTTP security headers (CSP, clickjacking protection, MIME sniff protection, no-referrer policy, permissions policy).
- Added API bounds/enum validation for leaderboard parameters and manual gate events.
- Added `tzdata` to Windows dependencies to prevent the `Asia/Colombo` startup error seen on Microsoft Store Python.
- Added seven-player, 25-lap-each endurance test.
- Added safe V1→V2 upgrade scripts that preserve the existing config, camera ROIs and database.
- Version bumped to 2.0.0.
