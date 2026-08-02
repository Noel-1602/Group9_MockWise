import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        PROJECT_NAME: str = "MockWise - AI Mock Interview Platform"
        VERSION: str = "1.0.0"
        API_PREFIX: str = "/api"
        
        BASE_DIR: Path = Path(__file__).resolve().parent.parent
        STORAGE_DIR: Path = BASE_DIR / "storage"
        UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
        AUDIO_DIR: Path = STORAGE_DIR / "audio"
        REPORTS_DIR: Path = STORAGE_DIR / "reports"
        
        DATABASE_URL: str = f"sqlite+aiosqlite:///{STORAGE_DIR}/mockwise.db"
        SYNC_DATABASE_URL: str = f"sqlite:///{STORAGE_DIR}/mockwise.db"
        
        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
        
        STT_PROVIDER: str = os.getenv("STT_PROVIDER", "mock")
        WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
        
        TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "synth")
        DEFAULT_VOICE: str = os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural")

        class Config:
            env_file = ".env"
            extra = "ignore"

except ImportError:
    class Settings:
        PROJECT_NAME: str = "MockWise - AI Mock Interview Platform"
        VERSION: str = "1.0.0"
        API_PREFIX: str = "/api"
        
        BASE_DIR: Path = Path(__file__).resolve().parent.parent
        STORAGE_DIR: Path = BASE_DIR / "storage"
        UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
        AUDIO_DIR: Path = STORAGE_DIR / "audio"
        REPORTS_DIR: Path = STORAGE_DIR / "reports"
        
        DATABASE_URL: str = f"sqlite+aiosqlite:///{STORAGE_DIR}/mockwise.db"
        SYNC_DATABASE_URL: str = f"sqlite:///{STORAGE_DIR}/mockwise.db"
        
        LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
        
        STT_PROVIDER: str = os.getenv("STT_PROVIDER", "mock")
        WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
        
        TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "synth")
        DEFAULT_VOICE: str = os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural")

# Ensure storage directories exist
settings = Settings()
for folder in [settings.STORAGE_DIR, settings.UPLOADS_DIR, settings.AUDIO_DIR, settings.REPORTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)
