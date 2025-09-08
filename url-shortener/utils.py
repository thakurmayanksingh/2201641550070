import re, random
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def base62(n: int = 7) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(n))

_shortcode_re = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
def valid_shortcode(s: str) -> bool:
    return bool(_shortcode_re.match(s))

def valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def mins_from_now(m: int) -> datetime:
    return utc_now() + timedelta(minutes=m)

def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def coarse_ip(ip: str | None) -> str:
    if not ip:
        return "unknown"
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3]) + "::/48"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.x.x"
    return "unknown"