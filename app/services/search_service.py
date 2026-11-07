import re
import unicodedata
from typing import List, Dict, Any
import yt_dlp
from app.config import settings

def remove_vietnamese_accents(text: str) -> str:
    """
    Chuẩn hóa chuỗi tiếng Việt thành không dấu, viết thường.
    Hỗ trợ xử lý ký tự 'đ', 'Đ' và các tổ hợp unicode.
    Ví dụ: 'Cắt Đôi Nỗi Sầu' -> 'cat doi noi sau'
    """
    if not text:
        return ""
    text = text.replace('đ', 'd').replace('Đ', 'D')
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text

def build_search_keywords(title: str, artist: str = "") -> str:
    """Tạo chuỗi từ khóa tìm kiếm tổng hợp từ tiêu đề và ca sĩ."""
    clean_title = remove_vietnamese_accents(title)
    clean_artist = remove_vietnamese_accents(artist)
    return f"{clean_title} {clean_artist}".strip()

def search_youtube_fallback(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Tìm kiếm dự phòng từ YouTube (ytsearch5) khi cơ sở dữ liệu chưa có kết quả.
    Trả về danh sách 5 video để người dùng có thể nghe thử hoặc bấm bóc tách vào hệ thống.
    """
    results = []
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'default_search': f'ytsearch{max_results}',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_data = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if 'entries' in search_data:
                for entry in search_data['entries']:
                    if not entry:
                        continue
                    video_id = entry.get('id', '')
                    title = entry.get('title', 'Unknown Title')
                    uploader = entry.get('uploader') or entry.get('channel', 'Unknown Artist')
                    duration = int(entry.get('duration') or 0)
                    thumbnails = entry.get('thumbnails') or []
                    cover_url = thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    original_url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
                    
                    results.append({
                        "id": video_id,
                        "title": title,
                        "artist": uploader,
                        "duration": duration,
                        "cover_url": cover_url,
                        "original_url": original_url,
                        "source_type": "youtube"
                    })
    except Exception as e:
        print(f"[FallbackSearch] Lỗi tìm kiếm YouTube: {e}")
        
    return results

