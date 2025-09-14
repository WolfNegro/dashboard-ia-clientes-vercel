# app/utils.py
import os, json, time

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Detecta Vercel (serverless) y usa /tmp, que sí es escribible
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_URL"))
CACHE_DIR = os.getenv("CACHE_DIR") or (
    os.path.join("/tmp", "cache_raw") if IS_VERCEL else os.path.join(BASE_DIR, "cache_raw")
)
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(key: str) -> str:
    safe = "".join(c for c in key if c.isalnum() or c in ("-", "_", "."))
    return os.path.join(CACHE_DIR, f"{safe}.json")

def read_cache(key: str, ttl_seconds: int = 600):
    """Lee JSON del caché si no está vencido; si hay cualquier problema, devuelve None."""
    try:
        path = _cache_path(key)
        if not os.path.exists(path):
            return None
        if ttl_seconds:
            age = time.time() - os.path.getmtime(path)
            if age > ttl_seconds:
                return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_cache(key: str, data):
    """Guarda JSON en caché; en Vercel puede fallar y lo ignoramos silenciosamente."""
    try:
        path = _cache_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        # En serverless nunca tumbamos la request por un error de caché
        pass
