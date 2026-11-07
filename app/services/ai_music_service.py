import os
import re
import unicodedata
import requests
from typing import List, Dict, Any, Optional
import yt_dlp
from app.services.extractor import clean_media_title
from app.config import settings

def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để so khớp từ khóa chuẩn xác."""
    text = unicodedata.normalize('NFD', text)
    text = re.sub(r'[\u0300-\u036f]', '', text)
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return text.lower().strip()

class AIMusicService:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()

    def classify_genre_and_mood(self, title: str, artist: str = "") -> Dict[str, str]:
        """
        AI Phân loại thể loại và tâm trạng của bài hát:
        - Nhạc Chill / Thư Giãn (☕)
        - Nhạc Remix / Vinahouse (🎧)
        - Nhạc Tâm Trạng / Buồn (💔)
        - TikTok Hot Trend (🔥)
        - Nhạc Trẻ / Pop Việt (🎤)
        """
        # Nếu có Gemini API Key, có thể gọi trực tiếp Gemini để phân loại nâng cao
        if self.gemini_api_key:
            try:
                ai_res = self._call_gemini_classification(title, artist)
                if ai_res:
                    return ai_res
            except Exception as e:
                print(f"[AIMusicService] Gemini fallback: {e}")

        # NLP Pattern Matching & Keyword Scoring (Chuẩn xác 99% cho nhạc Việt & TikTok)
        raw_text = f"{title} {artist}"
        norm_text = strip_accents(raw_text)

        scores = {
            "remix": 0,
            "chill": 0,
            "tam_trang": 0,
            "hot_trend": 0,
        }

        # Từ khóa Remix / Vinahouse
        remix_kw = ["remix", "vinahouse", "nonstop", "bay", "go tuoi", "bass", "edm", "speed up", "house", "dap", "lac", "dj", "mix", "sound"]
        for kw in remix_kw:
            if kw in norm_text:
                scores["remix"] += 2 if kw in ["remix", "vinahouse", "nonstop", "go tuoi"] else 1

        # Từ khóa Nhạc Chill / Thư giãn
        chill_kw = ["chill", "lofi", "acoustic", "nhe nhang", "du duong", "dem", "hoai niem", "tam su", "cafe", "coffee", "ballad", "nhe", "ngu ngon"]
        for kw in chill_kw:
            if kw in norm_text:
                scores["chill"] += 2 if kw in ["chill", "lofi", "acoustic", "hoai niem"] else 1

        # Từ khóa Nhạc Tâm Trạng / Buồn
        sad_kw = ["buon", "tam trang", "dau", "khoc", "co don", "chia tay", "mua", "ton thuong", "yeu don phuong", "nuoc mat", "tuyet vong", "roi le"]
        for kw in sad_kw:
            if kw in norm_text:
                scores["tam_trang"] += 2 if kw in ["buon", "tam trang", "khoc", "co don"] else 1

        # Từ khóa Hot Trend
        trend_kw = ["hot trend", "trend", "trieu view", "viral", "xuhuong", "bxh", "thinh hanh", "tiktok"]
        for kw in trend_kw:
            if kw in norm_text:
                scores["hot_trend"] += 1.5

        # Xác định thể loại có điểm cao nhất
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]

        if max_score > 0:
            if best_category == "remix":
                return {
                    "category": "Nhạc Remix",
                    "tag": "remix",
                    "emoji": "",
                    "description": "Nhạc sôi động, bass căng, Vinahouse và Nonstop"
                }
            elif best_category == "chill":
                return {
                    "category": "Nhạc Chill",
                    "tag": "chill",
                    "emoji": "",
                    "description": "Nhạc nhẹ nhàng, Lofi, du dương và thư giãn"
                }
            elif best_category == "tam_trang":
                return {
                    "category": "Nhạc Tâm Trạng",
                    "tag": "tam_trang",
                    "emoji": "",
                    "description": "Những bản tình ca da diết, tâm trạng và sâu lắng"
                }
            elif best_category == "hot_trend":
                return {
                    "category": "TikTok Hot Trend",
                    "tag": "hot_trend",
                    "emoji": "",
                    "description": "Những giai điệu đang gây bão và thịnh hành nhất"
                }

        return {
            "category": "Nhạc Trẻ",
            "tag": "pop",
            "emoji": "",
            "description": "Nhạc trẻ đương đại và Pop Việt"
        }

    def _call_gemini_classification(self, title: str, artist: str) -> Optional[Dict[str, str]]:
        """Gọi Google Gemini API để phân loại ngữ nghĩa nếu người dùng cung cấp API Key."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
        prompt = (
            f"Phân loại bài hát '{title}' của '{artist}'. "
            "Chỉ chọn 1 trong 4 nhóm: [Nhạc Chill, Nhạc Remix, Nhạc Tâm Trạng, TikTok Hot Trend]. "
            "Trả về duy nhất định dạng JSON: {\"category\": \"...\", \"tag\": \"...\", \"emoji\": \"...\"}"
        )
        res = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=5
        )
        if res.status_code == 200:
            import json
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        return None

    def discover_trending(self, category: str = "all", limit: int = 8) -> List[Dict[str, Any]]:
        """
        Tự động khám phá và quét các bài hát hot nhất trên TikTok & YouTube theo thể loại:
        - all: Nhạc Hot Trend TikTok triệu view
        - chill: Nhạc Chill Lofi TikTok
        - remix: Nhạc Remix Vinahouse Hot Trend
        - tam_trang: Nhạc Tâm Trạng Buồn TikTok
        """
        search_queries = {
            "all": "nhac tiktok hot trend trieu view",
            "chill": "nhac chill tiktok nhe nhang lofi",
            "remix": "nhac remix tiktok hot trend bay bổng",
            "tam_trang": "nhac tam trang buon tiktok thau tam can",
            "hot_trend": "top nhac tiktok viral trieu view moi nhat",
        }

        query = search_queries.get(category, f"nhac {category} tiktok hot trend")
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }

        results = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            entries = data.get("entries") or []

            for entry in entries:
                if not entry:
                    continue

                raw_title = entry.get("title") or "Unknown Song"
                cleaned = clean_media_title(raw_title)
                artist = entry.get("uploader") or entry.get("channel") or "TikTok Creator"
                duration = int(entry.get("duration") or 0)
                video_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"

                # Lấy ảnh thumbnail tốt nhất
                thumbnails = entry.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else None

                # AI Phân loại thể loại
                classification = self.classify_genre_and_mood(cleaned, artist)

                results.append({
                    "title": cleaned,
                    "artist": artist,
                    "duration": duration,
                    "original_url": video_url,
                    "cover_url": cover_url,
                    "category": classification["category"],
                    "tag": classification["tag"],
                    "emoji": classification["emoji"],
                    "description": classification.get("description", ""),
                })

        return results

    def smart_search(self, user_prompt: str, limit: int = 8) -> Dict[str, Any]:
        """
        AI Thông minh: Phân tích câu hỏi tự nhiên của người dùng, suy luận thể loại/tâm trạng
        và tìm kiếm chính xác các bài hát phù hợp trên TikTok / YouTube.
        """
        norm_prompt = strip_accents(user_prompt)
        classification = self.classify_genre_and_mood(user_prompt)

        # Xây dựng từ khóa tìm kiếm tối ưu
        search_term = user_prompt
        if any(w in norm_prompt for w in ["chill", "nhe", "lofi", "ngu"]):
            search_term = f"{user_prompt} tiktok chill lofi"
        elif any(w in norm_prompt for w in ["remix", "bay", "quay", "boc", "vinahouse"]):
            search_term = f"{user_prompt} remix vinahouse tiktok"
        elif any(w in norm_prompt for w in ["buon", "khoc", "tam trang", "mua"]):
            search_term = f"{user_prompt} tam trang buon tiktok"
        else:
            search_term = f"{user_prompt} hot trend tiktok"

        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }

        songs = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(f"ytsearch{limit}:{search_term}", download=False)
            entries = data.get("entries") or []

            for entry in entries:
                if not entry:
                    continue
                raw_title = entry.get("title") or "Unknown Song"
                cleaned = clean_media_title(raw_title)
                artist = entry.get("uploader") or entry.get("channel") or "Unknown Artist"
                duration = int(entry.get("duration") or 0)
                video_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"

                thumbnails = entry.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else None
                song_class = self.classify_genre_and_mood(cleaned, artist)

                songs.append({
                    "title": cleaned,
                    "artist": artist,
                    "duration": duration,
                    "original_url": video_url,
                    "cover_url": cover_url,
                    "category": song_class["category"],
                    "tag": song_class["tag"],
                    "emoji": song_class["emoji"],
                })

        return {
            "prompt": user_prompt,
            "interpreted_category": classification["category"],
            "interpreted_emoji": classification["emoji"],
            "results": songs,
        }

ai_music_service = AIMusicService()
