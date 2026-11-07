from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class ExtractRequest(BaseModel):
    url: str
    custom_title: Optional[str] = None
    custom_artist: Optional[str] = None

class SongResponse(BaseModel):
    id: str
    title: str
    artist: str
    duration: int
    audio_url: str
    cover_url: Optional[str] = None
    source_type: str
    original_url: str
    lyrics: Optional[str] = None
    created_at: Optional[str] = None

class SearchFallbackItem(BaseModel):
    id: str
    title: str
    artist: str
    duration: int
    cover_url: Optional[str] = None
    original_url: str
    source_type: str = "youtube"

class SearchResultResponse(BaseModel):
    query: str
    total: int
    results: List[SongResponse]
    fallback_results: Optional[List[SearchFallbackItem]] = []

