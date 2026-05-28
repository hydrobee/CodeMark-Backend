import os
import httpx
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def upload_to_supabase(file_bytes: bytes, filename: str, bucket: str) -> str:
    """Upload file to Supabase Storage and return the public URL."""
    try:
        supabase.storage.from_(bucket).remove([filename])
    except Exception:
        pass

    supabase.storage.from_(bucket).upload(
        filename,
        file_bytes,
        {"content-type": "application/octet-stream", "upsert": "true"}
    )
    return supabase.storage.from_(bucket).get_public_url(filename)


def download_to_tmp(url: str | None) -> str | None:
    """
    If the path is a Supabase URL, download it to /tmp and return the local path.
    If it's already a local path (or None), return as-is.
    """
    if not url or not url.startswith("http"):
        return url

    filename = url.split("/")[-1]
    local_path = f"/tmp/{filename}"

    response = httpx.get(url)
    response.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(response.content)

    return local_path