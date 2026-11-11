import os
from dotenv import load_dotenv

load_dotenv()

PLUGGY_CLIENT_ID = os.getenv("PLUGGY_CLIENT_ID", "")
PLUGGY_CLIENT_SECRET = os.getenv("PLUGGY_CLIENT_SECRET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/database.db")
