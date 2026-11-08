import requests
from typing import Optional

def fetch_synced_lyrics(track_name: str, artist_name: str = "") -> Optional[str]:
    """
    Tự động tìm kiếm lời bài hát đồng bộ (Synced Lyrics định dạng .lrc)
    thông qua open API LRCLIB (hoàn toàn miễn phí, hỗ trợ nhiều ngôn ngữ).
    """
    try:
        # 1. Thử tìm kiếm chính xác track_name + artist_name
        params = {
            "track_name": track_name.strip(),
        }
        if artist_name and artist_name != "Unknown Artist":
            params["artist_name"] = artist_name.strip()

        headers = {
            "User-Agent": "MusicEcosystem/1.0 (https://github.com/phanthanhquy917/music)"
        }

        res = requests.get("https://lrclib.net/api/get", params=params, headers=headers, timeout=1.5)
        if res.status_code == 200:
            data = res.json()
            synced = data.get("syncedLyrics")
            if synced:
                return synced
            return data.get("plainLyrics")

        # 2. Thử tìm kiếm fuzzy search
        query = f"{track_name} {artist_name}".strip()
        search_res = requests.get("https://lrclib.net/api/search", params={"q": query}, headers=headers, timeout=1.5)
        if search_res.status_code == 200:
            items = search_res.json()
            if items and isinstance(items, list):
                for item in items:
                    if item.get("syncedLyrics"):
                        return item["syncedLyrics"]
                if items[0].get("plainLyrics"):
                    return items[0]["plainLyrics"]

    except Exception as e:
        print(f"[LyricsService] Không tìm thấy lời bài hát: {e}")

    return None

