from pathlib import Path
from datetime import datetime
from app.config import AppConfig, ROOT
from app.db import Database

cfg = AppConfig().get()
db = Database(ROOT / "data" / "rc_timing.db", cfg.get("timezone", "Asia/Colombo"))
out = ROOT / "backups" / f"manual_{datetime.now():%Y%m%d_%H%M%S}.db"
db.backup_to(out)
print(out)
