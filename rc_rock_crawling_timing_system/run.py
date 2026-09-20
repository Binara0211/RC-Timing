from app.config import AppConfig
import uvicorn

if __name__ == "__main__":
    cfg = AppConfig().get()
    # IMPORTANT: one worker only. The camera is an exclusive hardware resource.
    uvicorn.run("app.main:app", host=cfg.get("host", "127.0.0.1"), port=int(cfg.get("port", 8765)), workers=1, reload=False, access_log=False)
