from pathlib import Path

from dotenv import load_dotenv

from rag_app.api import create_app

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

app = create_app()
