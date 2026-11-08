from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List
from app.schemas import ExtractRequest, SongResponse
from app.services.extractor import extractor_service
from app.services.github_storage import github_storage
from app.services.search_service import build_search_keywords
from app.services.lyrics_service import fetch_synced_lyrics
from app.database import get_connection

router = APIRouter(prefix="/api/admin", tags=["Admin Extraction"])

@router.post("/extract", response_model=List[SongResponse])
def extract_media(request: ExtractRequest):
    """
    Endpoint bóc tách nhạc từ TikTok (Video) hoặc YouTube (Video, Shorts, Playlist).
    1. Tải và bóc tách MP3 128kbps + Cover Art bằng yt-dlp và FFmpeg.
    2. Tự động làm sạch tiêu đề.
    3. Upload file lên GitHub Repo qua REST API.
    4. Tự động dọn sạch file tạm trên ổ cứng server.
    5. Tìm kiếm lời bài hát đồng bộ (Synced Lyrics .lrc).
    6. Lưu siêu dữ liệu bài hát và jsDelivr CDN URLs vào Database.
    """
    try:
        # Nếu client đã bóc tách direct MP3 URL từ TikWM (vượt qua Cloudflare bằng residential IP):
        if request.direct_audio_url and request.direct_audio_url.startswith("http"):
            import uuid
            song_id = str(uuid.uuid4())
            audio_file = extractor_service.temp_dir / f"{song_id}.mp3"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            with requests.get(request.direct_audio_url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(audio_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

            cover_file = None
            if request.direct_cover_url and request.direct_cover_url.startswith("http"):
                cover_file = extractor_service.temp_dir / f"{song_id}.jpg"
                try:
                    with requests.get(request.direct_cover_url, headers=headers, timeout=10) as cr:
                        if cr.status_code == 200:
                            with open(cover_file, "wb") as cf:
                                cf.write(cr.content)
                        else:
                            cover_file = None
                except Exception:
                    cover_file = None

            title = request.custom_title or "TikTok Sound"
            artist = request.custom_artist or "TikTok Creator"
            from app.services.extractor import clean_media_title
            cleaned_title = clean_media_title(title)

            extracted_items = [{
                "id": song_id,
                "title": cleaned_title,
                "artist": artist,
                "duration": request.duration or 0,
                "source_type": "tiktok",
                "original_url": request.url,
                "audio_file": audio_file,
                "cover_file": cover_file,
            }]
        else:
            extracted_items = extractor_service.extract_and_download(request.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi trích xuất đa phương tiện: {str(e)}")


    if not extracted_items:
        raise HTTPException(status_code=400, detail="Không thể bóc tách nội dung từ đường dẫn này.")

    conn = get_connection()
    cursor = conn.cursor()
    saved_songs: List[SongResponse] = []

    try:
        for item in extracted_items:
            song_id = item["id"]
            title = request.custom_title if (request.custom_title and len(extracted_items) == 1) else item["title"]
            artist = request.custom_artist if (request.custom_artist and len(extracted_items) == 1) else item["artist"]
            
            # Upload lên GitHub và nhận jsDelivr CDN URL (file tạm được xóa tự động sau khi xong)
            audio_cdn_url, cover_cdn_url = github_storage.upload_song_assets(
                audio_file=item["audio_file"],
                cover_file=item["cover_file"],
                song_id=song_id
            )

            # Tự động tìm lời bài hát đồng bộ
            lyrics = fetch_synced_lyrics(title, artist)

            # Tạo từ khóa tìm kiếm tiếng Việt không dấu
            keywords = build_search_keywords(title, artist)

            # Lưu vào Database
            cursor.execute("""
            INSERT INTO songs (id, title, artist, duration, audio_url, cover_url, source_type, original_url, search_keywords, lyrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                song_id,
                title,
                artist,
                item["duration"],
                audio_cdn_url,
                cover_cdn_url,
                item["source_type"],
                item["original_url"],
                keywords,
                lyrics
            ))

            saved_songs.append(SongResponse(
                id=song_id,
                title=title,
                artist=artist,
                duration=item["duration"],
                audio_url=audio_cdn_url,
                cover_url=cover_cdn_url,
                source_type=item["source_type"],
                original_url=item["original_url"],
                lyrics=lyrics
            ))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi lưu trữ bài hát vào cơ sở dữ liệu: {str(e)}")
    finally:
        conn.close()

    return saved_songs

