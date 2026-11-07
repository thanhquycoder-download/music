import sys
from pathlib import Path

# Add current dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import get_connection
from app.services.search_service import build_search_keywords

SAMPLE_SONGS = [
    {
        "id": "song-demo-1",
        "title": "Cắt Đôi Nỗi Sầu",
        "artist": "Tăng Duy Tân",
        "duration": 182,
        "audio_url": "https://cdn.jsdelivr.net/gh/anars/blank-audio/250-milliseconds-of-silence.mp3",
        "cover_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&q=80",
        "source_type": "tiktok",
        "original_url": "https://www.tiktok.com/@tangduytan/video/demo1",
    },
    {
        "id": "song-demo-2",
        "title": "Đừng Làm Trái Tim Anh Đau",
        "artist": "Sơn Tùng M-TP",
        "duration": 224,
        "audio_url": "https://cdn.jsdelivr.net/gh/anars/blank-audio/250-milliseconds-of-silence.mp3",
        "cover_url": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500&q=80",
        "source_type": "youtube",
        "original_url": "https://www.youtube.com/watch?v=demo2",
    },
    {
        "id": "song-demo-3",
        "title": "Bật Tình Yêu Lên",
        "artist": "Tăng Duy Tân x Hòa Minzy",
        "duration": 210,
        "audio_url": "https://cdn.jsdelivr.net/gh/anars/blank-audio/250-milliseconds-of-silence.mp3",
        "cover_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=500&q=80",
        "source_type": "tiktok",
        "original_url": "https://www.tiktok.com/@hoaminzy/video/demo3",
    },
    {
        "id": "song-demo-4",
        "title": "Ngày Mai Người Ta Lấy Chồng",
        "artist": "Thành Đạt",
        "duration": 255,
        "audio_url": "https://cdn.jsdelivr.net/gh/anars/blank-audio/250-milliseconds-of-silence.mp3",
        "cover_url": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=500&q=80",
        "source_type": "youtube",
        "original_url": "https://www.youtube.com/watch?v=demo4",
    }
]

def seed():
    conn = get_connection()
    cursor = conn.cursor()
    print("Đang nạp dữ liệu mẫu vào cơ sở dữ liệu...")

    for s in SAMPLE_SONGS:
        keywords = build_search_keywords(s["title"], s["artist"])
        cursor.execute("""
            INSERT OR REPLACE INTO songs (id, title, artist, duration, audio_url, cover_url, source_type, original_url, search_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["id"],
            s["title"],
            s["artist"],
            s["duration"],
            s["audio_url"],
            s["cover_url"],
            s["source_type"],
            s["original_url"],
            keywords
        ))
        print(f" -> Đã thêm: {s['title']} ({s['artist']})")

    conn.commit()
    conn.close()
    print("Hoàn tất nạp dữ liệu mẫu!")

if __name__ == "__main__":
    seed()

