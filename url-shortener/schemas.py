from pydantic import BaseModel, Field
from typing import Optional, List

class CreateShortURLReq(BaseModel):
    url: str = Field(..., description="Original long URL")
    validity: Optional[int] = Field(None, description="Minutes (default 30)")
    shortcode: Optional[str] = Field(None, description="Custom shortcode")

class CreateShortURLResp(BaseModel):
    shortLink: str
    expiry: str

class ClickItem(BaseModel):
    timestamp: str
    source: str
    geo: str

class StatsResp(BaseModel):
    shortLink: str
    targetUrl: str
    createdAt: str
    expiry: str
    totalClicks: int
    clicks: List[ClickItem]