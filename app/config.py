from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'app.db'}"
SECRET_KEY = "dev-secret-change-in-production"
