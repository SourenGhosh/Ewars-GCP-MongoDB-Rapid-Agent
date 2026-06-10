# config.py
import os
from dotenv import load_dotenv
load_dotenv()

def get_secret(secret_id: str) -> str:
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        name = f"projects/{project}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception:
        return os.environ.get(secret_id, "")

class Config:
    PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    REGION: str = os.getenv("GCP_REGION", "us-central1")
    MONGODB_URI: str = os.getenv("MONGODB_URI") or get_secret("MONGODB_URI")
    DB_NAME: str = "ewars_db"
    FLASH_MODEL: str = "gemini-2.0-flash-001"
    PRO_MODEL: str = "gemini-2.0-pro-001"
    OWM_API_KEY: str = os.getenv("OPENWEATHERMAP_API_KEY") or get_secret("OPENWEATHERMAP_API_KEY")
    TIMEOUT_SECONDS: int = 120

config = Config()
