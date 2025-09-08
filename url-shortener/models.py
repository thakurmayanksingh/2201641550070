from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey
from datetime import datetime, timezone
from db import Base

class URL(Base):
    __tablename__ = "urls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shortcode: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    long_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expiry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clicks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[list["Click"]] = relationship("Click", back_populates="url", cascade="all, delete-orphan")

class Click(Base):
    __tablename__ = "clicks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url_id: Mapped[int] = mapped_column(ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source: Mapped[str] = mapped_column(String(512), default="direct")
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    geo: Mapped[str] = mapped_column(String(64), default="unknown")
    url: Mapped[URL] = relationship("URL", back_populates="clicks")