"""App FastAPI que serve o frontend estático e expõe /info e /download.

Uso pessoal, apenas em localhost. Sem autenticação nesta etapa.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import downloader

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="YT Audio/Video Downloader", docs_url="/docs")


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format: str = "mp3"   # "mp3" | "mp4"
    quality: str = "high"  # "high" | "medium"


@app.post("/info")
def info(req: InfoRequest):
    url = req.url.strip()
    if not downloader.is_valid_youtube_url(url):
        raise HTTPException(
            status_code=400,
            detail="Informe um link válido do YouTube (youtube.com ou youtu.be).",
        )
    try:
        return downloader.get_info(url)
    except downloader.DownloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/download")
def download(req: DownloadRequest):
    url = req.url.strip()
    if not downloader.is_valid_youtube_url(url):
        raise HTTPException(
            status_code=400, detail="Informe um link válido do YouTube."
        )
    try:
        path = downloader.download(url, req.format, req.quality)
    except downloader.DownloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "video/mp4"
    # O arquivo é devolvido diretamente para download; a cópia permanece
    # em ./downloads para pegar de novo depois.
    return FileResponse(path, media_type=media_type, filename=path.name)


# O frontend é servido na raiz. Precisa ficar depois das rotas de API:
# StaticFiles só responde a GET, então não conflita com os POST acima.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
