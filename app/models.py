from dataclasses import dataclass
from typing import Optional

@dataclass
class SongModel:
    id: str
    title: str
    artist: str
    duration: int
    audio_url: str
    cover_url: Optional[str]
    source_type: str
    original_url: str
    search_keywords: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

