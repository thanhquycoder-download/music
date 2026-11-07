from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from app.schemas import SongResponse, SearchResultResponse, SearchFallbackItem
from app.services.search_service import remove_vietnamese_accents, search_youtube_fallback
from app.database import get_connection

router = APIRouter(prefix="/api/songs", tags=["Songs & Search"])

@router.get("", response_model=List[SongResponse])
def get_all_songs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Lấy danh sách các bài hát mới nhất trong hệ thống."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, artist, duration, audio_url, cover_url, source_type, original_url, created_at
        FROM songs
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    conn.close()

    return [
        SongResponse(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            duration=row["duration"],
            audio_url=row["audio_url"],
            cover_url=row["cover_url"],
            source_type=row["source_type"],
            original_url=row["original_url"],
            created_at=row["created_at"]
        )
        for row in rows
    ]

@router.get("/search", response_model=SearchResultResponse)
def search_songs(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm (có dấu hoặc không dấu)"),
    fallback: bool = Query(True, description="Kích hoạt tìm kiếm YouTube fallback nếu DB chưa có kết quả")
):
    """
    Tìm kiếm thông minh:
    1. Chuẩn hóa tiếng Việt không dấu (vd: 'cat doi noi sau' -> tìm ra 'Cắt Đôi Nỗi Sầu').
    2. Fuzzy/Sub-string matching trên tiêu đề, nghệ sĩ và search_keywords.
    3. Live Fallback Search: Nếu DB không có, tự động query nhanh 5 bài gợi ý từ YouTube qua yt-dlp.
    """
    normalized_q = remove_vietnamese_accents(q)
    like_pattern = f"%{normalized_q}%"
    raw_like_pattern = f"%{q.strip().lower()}%"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, artist, duration, audio_url, cover_url, source_type, original_url, created_at
        FROM songs
        WHERE search_keywords LIKE ? 
           OR LOWER(title) LIKE ? 
           OR LOWER(artist) LIKE ?
        ORDER BY created_at DESC
        LIMIT 30
    """, (like_pattern, raw_like_pattern, raw_like_pattern))
    rows = cursor.fetchall()
    conn.close()

    results = [
        SongResponse(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            duration=row["duration"],
            audio_url=row["audio_url"],
            cover_url=row["cover_url"],
            source_type=row["source_type"],
            original_url=row["original_url"],
            created_at=row["created_at"]
        )
        for row in rows
    ]

    fallback_results: List[SearchFallbackItem] = []
    # Nếu không tìm thấy bài nào trong hệ thống và fallback=True
    if not results and fallback:
        raw_fallback = search_youtube_fallback(q, max_results=5)
        fallback_results = [
            SearchFallbackItem(**item) for item in raw_fallback
        ]

    return SearchResultResponse(
        query=q,
        total=len(results),
        results=results,
        fallback_results=fallback_results
    )

@router.get("/{song_id}", response_model=SongResponse)
def get_song_by_id(song_id: str):
    """Chi tiết một bài hát theo ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, artist, duration, audio_url, cover_url, source_type, original_url, created_at
        FROM songs
        WHERE id = ?
    """, (song_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài hát.")

    return SongResponse(
        id=row["id"],
        title=row["title"],
        artist=row["artist"],
        duration=row["duration"],
        audio_url=row["audio_url"],
        cover_url=row["cover_url"],
        source_type=row["source_type"],
        original_url=row["original_url"],
        created_at=row["created_at"]
    )

@router.delete("/{song_id}")
def delete_song_by_id(song_id: str):
    """Xóa bài hát khỏi cơ sở dữ liệu hệ sinh thái."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM songs WHERE id = ?", (song_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy bài hát để xóa.")
    
    cursor.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Đã xóa bài hát {song_id} thành công"}

