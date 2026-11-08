import os
import re
import uuid
import subprocess
import requests
from urllib.parse import urljoin
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import yt_dlp
from app.config import settings

def clean_media_title(raw_title: str) -> str:
    """
    Tự động làm sạch tiêu đề: loại bỏ toàn bộ hashtags (#remix, #fyp,...),
    mentions (@username), các emoji biểu tượng và hậu tố MV/video rác,
    chỉ giữ lại tên bài hát và nghệ sĩ thuần túy.
    """
    cleaned = raw_title
    
    # 1. Loại bỏ các emoji và biểu tượng âm nhạc/dingbats
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2b55\u3030\u200d\ufe0f♪♫♬♩🎧🎤🔊🔥✨]")
    cleaned = emoji_pattern.sub("", cleaned)
    
    # 2. Loại bỏ các tag mention @username (thường ở cuối video TikTok)
    cleaned = re.sub(r"@[^#\n]+", "", cleaned)
    
    # 3. Loại bỏ toàn bộ hashtags (#remix, #fyp, #hottrend,...)
    cleaned = re.sub(r"#\S+", "", cleaned)
    
    # 4. Loại bỏ các hậu tố video/MV rác thường gặp
    patterns = [
        r"\[\s*(official\s*(music\s*)?mv|official\s*(music\s*)?video|lyrics|lyric\s*video|audio|mv|4k|hd|remix)\s*\]",
        r"\(\s*(official\s*(music\s*)?mv|official\s*(music\s*)?video|lyrics|lyric\s*video|audio|mv|4k|hd|remix)\s*\)",
        r"\|\s*(official\s*(music\s*)?video|official\s*mv|lyrics\s*video|audio|mv)\b.*",
        r"/\s*(official\s*mv|official\s*audio)\b.*",
        r"【.*?】",
        r"\[.*?\]",
        # Loại bỏ các tiền tố BXH / Top / Tuyển tập rác nếu có dấu hai chấm / gạch ngang
        r"^(BXH|Top\s*\d+|Tuyển\s*tập|Tổng\s*hợp)[^:-]*[:\-]\s*",
        # Loại bỏ các đuôi giật tít như "- BXH Nhạc Chill...", "- Nhạc Lofi...", "- Top 20..."
        r"\s*[-|]\s*(BXH|Nhạc\s*(?:Lofi|Chill|Trẻ|Remix)|Triệu\s*View|Hay\s*Nhất|Top\s*\d+)[^|]*$",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    # 5. Dọn dẹp khoảng trắng và ký tự phân cách thừa ở đầu và cuối
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^[-:|/_.,\s]+|[-:|/_.,\s]+$", "", cleaned).strip()
    return cleaned if cleaned else raw_title

def detect_source_type(url: str) -> str:
    """Xác định nguồn link là tiktok hay youtube."""
    url_lower = url.lower()
    if 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    return 'unknown'

class MediaExtractorService:
    def __init__(self):
        self.temp_dir = settings.TEMP_DIR

    def _extract_tiktok_direct(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Trích xuất trực tiếp link TikTok qua TikWM API để vượt qua challenge bot của TikTok,
        lấy thẳng link audio MP3 và ảnh cover trong tích tắc (chuẩn theo demo.py).
        """
        try:
            api_endpoint = "https://www.tikwm.com/api/"
            params = {"url": url}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.tiktok.com/"
            }
            res = requests.get(api_endpoint, params=params, headers=headers, timeout=12)
            if res.status_code == 200:
                body = res.json()
                if body.get("code") == 0 and "data" in body:
                    data = body["data"]
                    raw_title = data.get("title") or "TikTok Sound"
                    cleaned_title = clean_media_title(raw_title)
                    author_info = data.get("author") or {}
                    music_info = data.get("music_info") or {}
                    artist = author_info.get("nickname") or music_info.get("author") or "TikTok Creator"
                    duration = int(data.get("duration") or music_info.get("duration") or 0)
                    song_id = str(uuid.uuid4())

                    # Lấy link MP3 trực tiếp
                    audio_stream_url = data.get("music") or music_info.get("play")
                    if not audio_stream_url:
                        audio_stream_url = data.get("play")
                    if not audio_stream_url:
                        return None

                    if audio_stream_url.startswith("/"):
                        audio_stream_url = urljoin("https://www.tikwm.com", audio_stream_url)

                    audio_file = self.temp_dir / f"{song_id}.mp3"
                    with requests.get(audio_stream_url, headers=headers, stream=True, timeout=60) as audio_res:
                        audio_res.raise_for_status()
                        with open(audio_file, "wb") as f:
                            for chunk in audio_res.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)

                    # Tối ưu kích thước: Nếu file lớn hơn 15MB (Nonstop dài), nén nhanh để tải lên GitHub trong 3s
                    if audio_file.exists() and audio_file.stat().st_size > 15 * 1024 * 1024:
                        compressed_file = self.temp_dir / f"{song_id}_opt.mp3"
                        try:
                            opt_kbps = 96
                            if duration > 0:
                                opt_kbps = max(48, min(96, int((13.5 * 1024 * 8) / duration)))
                            subprocess.run([
                                settings.ffmpeg_binary, "-y", "-i", str(audio_file),
                                "-vn", "-threads", "0", "-b:a", f"{opt_kbps}k", str(compressed_file)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                            if compressed_file.exists() and compressed_file.stat().st_size > 0:
                                audio_file.unlink()
                                compressed_file.rename(audio_file)
                        except Exception:
                            pass

                    # Tải ảnh thumbnail
                    cover_file = None
                    cover_url = data.get("cover") or data.get("origin_cover")
                    if cover_url:
                        if cover_url.startswith("/"):
                            cover_url = urljoin("https://www.tikwm.com", cover_url)
                        cover_file = self.temp_dir / f"{song_id}.jpg"
                        try:
                            with requests.get(cover_url, headers=headers, timeout=10) as cover_res:
                                with open(cover_file, "wb") as f:
                                    f.write(cover_res.content)
                        except Exception:
                            cover_file = None

                    return [{
                        "id": song_id,
                        "title": cleaned_title,
                        "artist": artist,
                        "duration": duration,
                        "source_type": "tiktok",
                        "original_url": url,
                        "audio_file": audio_file,
                        "cover_file": cover_file,
                    }]
        except Exception as e:
            print(f"[TikTokExtractor] TikWM error: {e}")
        return None

    def extract_and_download(self, url: str) -> List[Dict[str, Any]]:
        """
        Trích xuất thông tin, tải file âm thanh .mp3 (128kbps) và ảnh thumbnail về thư mục tạm.
        Hỗ trợ cả link đơn lẻ và link playlist.
        """
        source_type = detect_source_type(url)
        
        # Ưu tiên trích xuất TikTok qua API chuyên biệt để không bị chặn bot
        if source_type == 'tiktok':
            tiktok_result = self._extract_tiktok_direct(url)
            if tiktok_result:
                return tiktok_result
        
        ydl_opts = {
            'format': 'ba[ext=m4a]/ba[ext=mp3]/ba/251/140/b[height<=360]/best',
            'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
            'extract_flat': False,
            'geo_bypass': True,
            'socket_timeout': 15,
            'retries': 2,
            'fragment_retries': 2,
            'buffersize': 1024 * 1024,
            'match_filter': yt_dlp.utils.match_filter_func('!is_live'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            },
        }

        # Tự động phát hiện JavaScript runtime (Node.js) để giải mã chữ ký YouTube
        import shutil
        node_bin = shutil.which("node")
        if not node_bin:
            for candidate in ["/usr/bin/node", "/usr/local/bin/node", r"C:\node-v24.19.0-win-x64\node.exe"]:
                if os.path.exists(candidate):
                    node_bin = candidate
                    break
        if node_bin:
            ydl_opts['js_runtimes'] = {'node': {'path': node_bin}}

        results = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Xử lý trường hợp playlist
            entries = info.get('entries') if 'entries' in info and info['entries'] else [info]

            for entry in entries:
                if not entry:
                    continue
                
                raw_title = entry.get('title', 'Unknown Title')
                cleaned_title = clean_media_title(raw_title)
                artist = entry.get('artist') or entry.get('uploader') or entry.get('channel') or 'Unknown Artist'
                duration = int(entry.get('duration') or 0)
                video_id = entry.get('id') or str(uuid.uuid4())[:8]
                song_id = str(uuid.uuid4())

                # Tìm file âm thanh/video thô vừa tải về
                raw_files = [f for f in self.temp_dir.glob(f"{video_id}.*") if f.suffix.lower() not in ('.jpg', '.png', '.webp')]
                if not raw_files:
                    raise FileNotFoundError(f"Không tìm thấy file audio sau khi tải cho: {video_id}")
                raw_file = raw_files[0]

                final_mp3 = self.temp_dir / f"{song_id}.mp3"
                ffmpeg_bin = settings.ffmpeg_binary

                # Tính bitrate chuẩn xác 1 bước:
                # Nếu bài hát dài > 25 phút (>1500s), tự tính bitrate để file luôn < 19MB (tương thích GitHub API & CDN)
                # Các bài hát thông thường (3-5 phút) dùng bitrate 128k chất lượng cao
                if duration > 1500:
                    target_bitrate = max(32, min(96, int((18.5 * 1024 * 8) / duration)))
                else:
                    target_bitrate = 128

                # Chuyển đổi siêu tốc 1 bước duy nhất bằng FFmpeg đa luồng (-threads 0)
                cmd = [
                    ffmpeg_bin, "-i", str(raw_file),
                    "-vn",
                    "-threads", "0",
                    "-b:a", f"{target_bitrate}k",
                    "-ac", "2",
                    str(final_mp3),
                    "-y"
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Xóa file thô ngay lập tức
                if raw_file.exists():
                    try:
                        raw_file.unlink()
                    except Exception:
                        pass

                # Tải ảnh thumbnail / cover art
                cover_file = None
                thumbnail_url = entry.get('thumbnail')
                if not thumbnail_url and 'thumbnails' in entry and entry['thumbnails']:
                    thumbnail_url = entry['thumbnails'][-1].get('url')

                if thumbnail_url:
                    cover_file = self.temp_dir / f"{song_id}.jpg"
                    try:
                        res = requests.get(thumbnail_url, timeout=15)
                        if res.status_code == 200:
                            with open(cover_file, 'wb') as f:
                                f.write(res.content)
                        else:
                            cover_file = None
                    except Exception as e:
                        print(f"[CoverDownload] Lỗi tải ảnh bìa: {e}")
                        cover_file = None

                results.append({
                    "id": song_id,
                    "title": cleaned_title,
                    "artist": artist,
                    "duration": duration,
                    "source_type": source_type,
                    "original_url": entry.get('webpage_url') or url,
                    "audio_file": final_mp3,
                    "cover_file": cover_file,
                })

        return results

extractor_service = MediaExtractorService()

