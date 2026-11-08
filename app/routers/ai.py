from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.ai_music_service import ai_music_service
from app.services.extractor import MediaExtractorService
from app.services.github_storage import GitHubStorageService
from app.services.lyrics_service import fetch_synced_lyrics
from app.services.search_service import build_search_keywords
from app.database import get_connection
from app.models import SongModel
from app.schemas import SongResponse

router = APIRouter(prefix="/api/ai", tags=["AI Music Assistant"])
extractor = MediaExtractorService()
storage = GitHubStorageService()

class SmartSearchRequest(BaseModel):
    prompt: str
    limit: Optional[int] = 8

class AutoImportRequest(BaseModel):
    url: str

class ClassifyRequest(BaseModel):
    title: str
    artist: Optional[str] = ""

@router.get("/trending")
def get_trending_songs(category: str = Query("all", description="all, chill, remix, tam_trang, hot_trend"), limit: int = 8):
    """
    AI tự động quét các bài hát hot nhất TikTok và YouTube theo thể loại chỉ định.
    """
    try:
        results = ai_music_service.discover_trending(category=category, limit=limit)
        return {
            "category": category,
            "total": len(results),
            "songs": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi quét nhạc trending: {str(e)}")

@router.post("/smart-search")
def smart_ai_search(payload: SmartSearchRequest):
    """
    Tìm kiếm thông minh bằng ngôn ngữ tự nhiên thông qua AI.
    Ví dụ: 'tìm bài nhạc bay bổng để quẩy', 'nhạc chill đêm khuya ru ngủ',...
    """
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập nội dung tìm kiếm!")
    try:
        return ai_music_service.smart_search(payload.prompt, limit=payload.limit or 8)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm AI: {str(e)}")

@router.post("/auto-import", response_model=Dict[str, Any])
def auto_import_song(payload: AutoImportRequest):
    """
    Tự động bóc tách link TikTok/YouTube, lưu lên CDN và dùng AI phân loại danh mục thích hợp.
    """
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp đường dẫn bài hát!")

    try:
        # 1. Trích xuất âm thanh và metadata
        extracted_items = extractor.extract_and_download(payload.url.strip())
        if not extracted_items:
            raise HTTPException(status_code=400, detail="Không thể bóc tách âm thanh từ link này.")

        imported_songs = []
        with get_connection() as conn:
            for item in extracted_items:
                audio_file = item["audio_file"]
                cover_file = item["cover_file"]
                song_id = item["id"]

                # 2. Upload lên GitHub Storage (kèm logic chọn CDN tối ưu jsDelivr / Fastly)
                audio_url, cover_url = storage.upload_song_assets(
                    audio_file=audio_file,
                    cover_file=cover_file,
                    song_id=song_id
                )

                # 3. Tìm kiếm lời bài hát tự động
                lyrics = fetch_synced_lyrics(
                    track_name=item["title"],
                    artist_name=item["artist"]
                )

                # 4. AI Phân loại thể loại / Danh mục
                classification = ai_music_service.classify_genre_and_mood(item["title"], item["artist"])

                # 5. Tạo từ khóa tìm kiếm tiếng Việt không dấu
                keywords = build_search_keywords(item["title"], item["artist"])

                # 6. Lưu vào SQLite Database
                conn.execute('''
                    INSERT OR REPLACE INTO songs 
                    (id, title, artist, duration, audio_url, cover_url, source_type, original_url, search_keywords, lyrics)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    song_id,
                    item["title"],
                    item["artist"],
                    item["duration"],
                    audio_url,
                    cover_url,
                    item["source_type"],
                    item["original_url"],
                    keywords,
                    lyrics
                ))
                conn.commit()

                imported_songs.append({
                    "id": song_id,
                    "title": item["title"],
                    "artist": item["artist"],
                    "duration": item["duration"],
                    "audio_url": audio_url,
                    "cover_url": cover_url,
                    "source_type": item["source_type"],
                    "original_url": item["original_url"],
                    "lyrics": lyrics,
                    "ai_category": classification["category"],
                    "ai_emoji": classification["emoji"],
                    "ai_tag": classification["tag"],
                })

        return {
            "success": True,
            "message": f"Đã bóc tách và phân loại thành công {len(imported_songs)} bài hát!",
            "songs": imported_songs
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi nhập bài hát tự động: {str(e)}")

@router.post("/classify-library")
def classify_library():
    """
    Duyệt toàn bộ thư viện bài hát hiện có và dùng AI phân loại vào các Danh mục:
    - ☕ Nhạc Chill / Thư Giãn
    - 🎧 Nhạc Remix / Vinahouse
    - 💔 Nhạc Tâm Trạng / Buồn
    - 🔥 TikTok Hot Trend
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, artist, duration, audio_url, cover_url, original_url FROM songs")
        rows = cursor.fetchall()

    categories_map = {
        "chill": {"name": "Nhạc Chill", "songs": []},
        "remix": {"name": "Nhạc Remix", "songs": []},
        "tam_trang": {"name": "Nhạc Tâm Trạng", "songs": []},
        "hot_trend": {"name": "TikTok Hot Trend", "songs": []},
        "pop": {"name": "Nhạc Trẻ", "songs": []},
    }

    for row in rows:
        song_dict = {
            "id": row["id"],
            "title": row["title"],
            "artist": row["artist"],
            "duration": row["duration"],
            "audio_url": row["audio_url"],
            "cover_url": row["cover_url"],
            "original_url": row["original_url"],
        }
        res = ai_music_service.classify_genre_and_mood(row["title"], row["artist"])
        tag = res.get("tag", "pop")
        if tag not in categories_map:
            tag = "pop"
        categories_map[tag]["songs"].append(song_dict)

    # Loại bỏ các danh mục trống và định dạng trả về
    final_result = {v["name"]: v["songs"] for k, v in categories_map.items() if v["songs"]}
    return {
        "total_songs": len(rows),
        "categorized_playlists": final_result
    }
