from pathlib import Path
import customtkinter as ctk
import database

# ============================================================
# ASCEND PRESENTATION MODE
# ============================================================
# Every launch creates a fresh database in THIS folder.
# Your code/assets are preserved; only the local presentation
# database is reset.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ascend.db"

database.DB_NAME = str(DB_PATH)

for path in (
    DB_PATH,
    Path(str(DB_PATH) + "-wal"),
    Path(str(DB_PATH) + "-shm"),
):
    try:
        if path.exists():
            path.unlink()
    except PermissionError:
        print("Close ASCEND before launching presentation mode.")
        raise

database.init_db()
database.seed_quests()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

from ui import App

if __name__ == "__main__":
    App().mainloop()
