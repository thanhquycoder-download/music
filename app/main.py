from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db
from app.routers import admin, songs, ai

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo DB khi ứng dụng khởi động
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Hệ thống bóc tách nhạc từ TikTok/YouTube, lưu trữ GitHub + jsDelivr CDN và tìm kiếm tiếng Việt thông minh.",
    lifespan=lifespan
)

# Kích hoạt CORS cho ứng dụng Flutter và Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn router
app.include_router(admin.router)
app.include_router(songs.router)
app.include_router(ai.router)

ADMIN_HTML_PATH = Path(__file__).resolve().parent / "templates" / "admin.html"

@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    """Giao diện Web Admin Panel bóc tách nhạc và quản lý bài hát."""
    if ADMIN_HTML_PATH.exists():
        return HTMLResponse(content=ADMIN_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h3>Admin template not found</h3>")

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "commit": "fast-tikwm-direct-v3",
        "docs": "/docs"
    }

@app.get("/api/test-tikwm")
def test_tikwm(url: str):
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/"
    }
    try:
        r_get = requests.get("https://www.tikwm.com/api/", params={"url": url}, headers=headers, timeout=10)
        get_json = r_get.json() if r_get.status_code == 200 else r_get.text
    except Exception as e:
        get_json = f"GET Error: {e}"

    try:
        r_post = requests.post("https://www.tikwm.com/api/", data={"url": url}, headers=headers, timeout=10)
        post_json = r_post.json() if r_post.status_code == 200 else r_post.text
    except Exception as e:
        post_json = f"POST Error: {e}"

    return {
        "get_result": get_json,
        "post_result": post_json
    }

# Phục vụ file media trực tiếp (âm thanh và ảnh bìa) với tốc độ cao, hỗ trợ Range Streaming
app.mount("/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")




@app.get("/api/app/version")
def check_app_version():
    """
    API kiểm tra phiên bản mới nhất của ứng dụng Thành Quý Music (Windows & Android).
    Cho phép app tự động thông báo và cập nhật khi có bản mới.
    """
    owner = settings.GITHUB_OWNER or "phanthanhquy917"
    repo = settings.GITHUB_REPO or "music"
    return {
        "latest_version": settings.VERSION,
        "version_code": 1,
        "force_update": False,
        "title": "Bản cập nhật Thành Quý Music",
        "changelog": "• Giao diện và logo Thành Quý Music hoàn toàn mới\n• Tối ưu tốc độ tải và lưu nhạc nhanh gấp 4 lần\n• Tự động quét và phân loại nhạc Hot TikTok, Chill, Remix\n• Hỗ trợ cập nhật mượt mà không gián đoạn",
        "download_url_windows": f"https://github.com/{owner}/{repo}/releases/latest/download/Thanh.Quy.Music.Setup.exe",
        "download_url_android": f"https://github.com/{owner}/{repo}/releases/latest/download/Thanh.Quy.Music.apk",
        "published_at": "2026-11-07"
    }

# Phục vụ ứng dụng Thành Quý Music Web/PWA trực tiếp tại trang chủ
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
