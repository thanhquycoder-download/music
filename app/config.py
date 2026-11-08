import os
from pathlib import Path
from dotenv import load_dotenv

# Tự động load biến môi trường từ file .env nếu có
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "Thành Quý Music API"
    VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")

    # GitHub Storage Settings
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")
    GITHUB_BRANCH: str = os.getenv("GITHUB_BRANCH", "main")

    # Database Path (Luôn chuẩn hóa thành đường dẫn tuyệt đối)
    _raw_db: str = os.getenv("DATABASE_PATH", "music.db")
    DATABASE_PATH: str = str((BASE_DIR / _raw_db).resolve() if not Path(_raw_db).is_absolute() else Path(_raw_db).resolve())

    # FFmpeg binary path (tự động nhận diện trên cả Windows và Linux Docker)
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "")

    @property
    def ffmpeg_binary(self) -> str:
        import shutil
        if self.FFMPEG_PATH and os.path.exists(self.FFMPEG_PATH):
            return self.FFMPEG_PATH
        return shutil.which("ffmpeg") or "ffmpeg"

    # Temporary directory for audio processing (sẽ được dọn sạch sau khi upload)
    TEMP_DIR: Path = BASE_DIR / "temp"

    # Thư mục lưu trữ media cục bộ trên server (phục vụ fallback tức thì khi GitHub CDN token lỗi/hết hạn)
    MEDIA_DIR: Path = BASE_DIR / "media"

    # Server Base URL để phát nhạc trực tiếp
    SERVER_BASE_URL: str = os.getenv("SERVER_BASE_URL", "https://music-dk2c.onrender.com").rstrip("/")

settings = Settings()
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)


