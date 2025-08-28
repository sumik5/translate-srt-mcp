"""Data models for SRT subtitles."""

from datetime import timedelta
from typing import Optional
from pydantic import BaseModel, Field


class Subtitle(BaseModel):
    """Represents a single subtitle entry."""
    
    index: int = Field(..., description="Subtitle sequence number")
    start_time: timedelta = Field(..., description="Start time of subtitle")
    end_time: timedelta = Field(..., description="End time of subtitle")
    text: str = Field(..., description="Subtitle text content")
    
    def duration(self) -> timedelta:
        """Calculate the duration of the subtitle."""
        return self.end_time - self.start_time
    
    def __str__(self) -> str:
        """String representation of the subtitle."""
        return f"{self.index}: {self.start_time} -> {self.end_time} | {self.text}"


class TranslationContext(BaseModel):
    """Context information for translation."""
    
    previous_subtitles: list[str] = Field(default_factory=list, description="Previous subtitle texts")
    next_subtitles: list[str] = Field(default_factory=list, description="Next subtitle texts") 
    scene_description: Optional[str] = Field(None, description="Optional scene description")
    speaker_info: Optional[str] = Field(None, description="Optional speaker information")


class TranslationRequest(BaseModel):
    """Request payload for LM Studio API."""
    
    model: str = Field(..., description="Model name to use")
    messages: list[dict] = Field(..., description="Chat messages")
    temperature: float = Field(0.3, description="Temperature for translation")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")