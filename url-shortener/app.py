from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from datetime import timezone
from db import Base, engine, get_db
from models import URL, Click
from schemas import CreateShortURLReq, CreateShortURLResp, StatsResp, ClickItem
from utils import base62, valid_shortcode, valid_url, mins_from_now, iso_z, utc_now, coarse_ip
from middleware.custom_logger import StructuredAuditMiddleware, audit

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Affordmed URL Shortener")
app.add_middleware(StructuredAuditMiddleware)

DEFAULT_VALIDITY_MIN = 30
MAX_VALIDITY_MIN = 60 * 24 * 7

def as_utc(dt):
    return dt.astimezone(timezone.utc) if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=timezone.utc)

def make_short_link(request: Request, shortcode: str) -> str:
    base = str(request.base_url)
    if not base.endswith("/"):
        base += "/"
    return base + shortcode

@app.post("/shorturls", response_model=CreateShortURLResp, status_code=201)
def create_short_url(payload: CreateShortURLReq, request: Request, db: Session = Depends(get_db)):
    if not valid_url(payload.url):
        raise HTTPException(status_code=400, detail="invalid url")
    validity = payload.validity if payload.validity is not None else DEFAULT_VALIDITY_MIN
    if not isinstance(validity, int) or validity <= 0 or validity > MAX_VALIDITY_MIN:
        raise HTTPException(status_code=400, detail="invalid validity")

    user_code: Optional[str] = payload.shortcode.strip() if payload.shortcode else None
    if user_code and not valid_shortcode(user_code):
        raise HTTPException(status_code=400, detail="invalid shortcode format")

    expiry_at = mins_from_now(validity)

    if user_code:
        exists = db.query(URL).filter(URL.shortcode == user_code).first()
        if exists:
            audit.event("shortcode_collision", shortcode=user_code)
            raise HTTPException(status_code=409, detail="shortcode collision")
        u = URL(shortcode=user_code, long_url=payload.url, expiry_at=expiry_at)
        db.add(u); db.commit(); db.refresh(u)
        audit.event("short_created", shortcode=u.shortcode, long_url=u.long_url, expiry=iso_z(u.expiry_at))
        return CreateShortURLResp(shortLink=make_short_link(request, u.shortcode), expiry=iso_z(u.expiry_at))

    tries = 0
    while tries < 5:
        code = base62(7)
        try:
            u = URL(shortcode=code, long_url=payload.url, expiry_at=expiry_at)
            db.add(u); db.commit(); db.refresh(u)
            audit.event("short_created", shortcode=u.shortcode, long_url=u.long_url, expiry=iso_z(u.expiry_at))
            return CreateShortURLResp(shortLink=make_short_link(request, u.shortcode), expiry=iso_z(u.expiry_at))
        except IntegrityError:
            db.rollback(); tries += 1
    audit.event("short_autogen_failed")
    raise HTTPException(status_code=500, detail="failed to generate shortcode")

@app.get("/{shortcode}")
def redirect_shortcode(shortcode: str, request: Request, db: Session = Depends(get_db)):
    if not valid_shortcode(shortcode):
        raise HTTPException(status_code=404, detail="shortcode not found")
    u: Optional[URL] = db.query(URL).filter(URL.shortcode == shortcode).first()
    if not u:
        raise HTTPException(status_code=404, detail="shortcode not found")
    if utc_now() >= as_utc(u.expiry_at):
        audit.event("redirect_expired", shortcode=shortcode)
        raise HTTPException(status_code=410, detail="expired link")

    ref = request.headers.get("referer") or request.headers.get("referrer") or "direct"
    ua = request.headers.get("user-agent", "")[:500]
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or getattr(request.client, "host", None)
    click = Click(url_id=u.id, source=ref if ref else "direct", user_agent=ua, geo=coarse_ip(ip))
    db.add(click); u.clicks_count += 1; db.commit()
    audit.event("redirect_hit", shortcode=shortcode, source=ref, geo=coarse_ip(ip))
    return RedirectResponse(url=u.long_url, status_code=302)

@app.get("/shorturls/{shortcode}", response_model=StatsResp)
def get_stats(shortcode: str, request: Request, db: Session = Depends(get_db)):
    if not valid_shortcode(shortcode):
        raise HTTPException(status_code=404, detail="shortcode not found")
    u: Optional[URL] = db.query(URL).filter(URL.shortcode == shortcode).first()
    if not u:
        raise HTTPException(status_code=404, detail="shortcode not found")

    items = [ClickItem(timestamp=iso_z(c.timestamp), source=c.source or "direct", geo=c.geo or "unknown")
             for c in db.query(Click).filter(Click.url_id == u.id).order_by(Click.timestamp.asc()).all()]
    audit.event("stats_view", shortcode=shortcode, totalClicks=u.clicks_count)
    return StatsResp(
        shortLink=make_short_link(request, u.shortcode),
        targetUrl=u.long_url,
        createdAt=iso_z(as_utc(u.created_at)),
        expiry=iso_z(as_utc(u.expiry_at)),
        totalClicks=u.clicks_count,
        clicks=items,
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})