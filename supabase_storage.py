import os
import httpx
from urllib.parse import unquote

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def _headers():
    return {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
    }

def upload_to_supabase(file_bytes: bytes, filename: str, bucket: str) -> str:
    """Upload file to Supabase Storage and return the public URL."""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"

    # Try delete first (ignore errors)
    try:
        httpx.delete(url, headers=_headers())
    except Exception:
        pass

    response = httpx.post(
        url,
        headers={
            **_headers(),
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        },
        content=file_bytes,
    )
    response.raise_for_status()

    # Return public URL
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"


def download_to_tmp(url: str | None) -> str | None:
    if not url or not url.startswith("http"):
        return url

    filename = unquote(url.split("/")[-1])  # decode %20 etc.
    local_path = f"/tmp/{filename}"

    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)
        print(f"[DEBUG] Downloaded → {local_path} ({len(response.content)} bytes)")
        return local_path
    except Exception as e:
        print(f"[ERROR] download_to_tmp failed for {url}: {e}")
        raise