"""Lógica de extração de metadados e download via yt-dlp + ffmpeg.

Mantido simples de propósito: é um projeto pessoal para rodar em localhost.
"""

from __future__ import annotations

import re
from pathlib import Path

import yt_dlp

DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Bitrate usado tanto para a estimativa de tamanho quanto para a conversão real.
MP3_BITRATE = {"high": 320, "medium": 192}

# Bitrate de áudio assumido (kbps) ao estimar o tamanho de um MP4 cujo
# stream de vídeo escolhido não informa o tamanho do áudio separadamente.
_ASSUMED_AUDIO_KBPS = 129


class DownloadError(Exception):
    """Erro já traduzido para uma mensagem amigável ao usuário."""


def is_valid_youtube_url(url: str) -> bool:
    """Aceita links normais, encurtados, shorts, music, live e embed.

    Deixamos a validação fina para o próprio yt-dlp; aqui só barramos o
    que claramente não é um link do YouTube.
    """
    url = (url or "").strip().lower()
    if not url.startswith(("http://", "https://")):
        return False
    return "youtube.com/" in url or "youtu.be/" in url


# --------------------------------------------------------------------------- #
# Metadados (sem baixar)
# --------------------------------------------------------------------------- #
def get_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(_friendly_error(str(exc))) from exc

    # Se o link apontar para uma playlist, usamos o primeiro item.
    if info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise DownloadError("Nenhum vídeo acessível foi encontrado nesse link.")
        info = entries[0]

    duration = int(info.get("duration") or 0)

    return {
        "title": info.get("title") or "Sem título",
        "channel": info.get("channel") or info.get("uploader") or "Desconhecido",
        "duration": duration,
        "duration_string": _format_duration(duration),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or url,
        "estimated_size_mb": {
            "mp3_high": _estimate_mp3_mb(duration, MP3_BITRATE["high"]),
            "mp3_medium": _estimate_mp3_mb(duration, MP3_BITRATE["medium"]),
            "mp4": _estimate_mp4_mb(info),
        },
    }


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def download(url: str, fmt: str, quality: str) -> Path:
    fmt = (fmt or "mp3").lower()
    quality = (quality or "high").lower()
    if fmt not in ("mp3", "mp4"):
        raise DownloadError("Formato inválido. Use 'mp3' ou 'mp4'.")
    if quality not in MP3_BITRATE:
        quality = "high"

    # %(title).150B corta o título em 150 bytes para não estourar o limite
    # de caminho do Windows; o id garante nome único.
    outtmpl = str(DOWNLOADS_DIR / "%(title).150B [%(id)s].%(ext)s")

    ydl_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "windowsfilenames": True,
        "overwrites": True,
    }

    if fmt == "mp3":
        # Pega o melhor stream de áudio original e converte para MP3 com o
        # ffmpeg — sem passar pelo vídeo, sem reencode desnecessário.
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(MP3_BITRATE[quality]),
            }
        ]
    else:
        # Vídeo + áudio mesclados, até 1080p, preferindo mp4/m4a.
        ydl_opts["format"] = (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=1080]+bestaudio/"
            "best[height<=1080]/best"
        )
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info.get("entries"):
                info = next(e for e in info["entries"] if e)
            final_path = _resolve_final_path(ydl, info, fmt)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(_friendly_error(str(exc))) from exc

    if not final_path or not final_path.exists():
        raise DownloadError(
            "O download terminou, mas o arquivo final não foi encontrado. "
            "Confirme que o ffmpeg está instalado e no PATH."
        )
    return final_path


def _resolve_final_path(ydl: "yt_dlp.YoutubeDL", info: dict, fmt: str) -> Path | None:
    """Descobre o caminho do arquivo já pós-processado."""
    downloads = info.get("requested_downloads") or []
    if downloads and downloads[0].get("filepath"):
        return Path(downloads[0]["filepath"])

    # Fallback: nome previsto pelo template, com a extensão final.
    guessed = Path(ydl.prepare_filename(info)).with_suffix("." + fmt)
    if guessed.exists():
        return guessed

    # Último recurso: arquivo mais recente na pasta de downloads.
    files = sorted(
        (p for p in DOWNLOADS_DIR.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


# --------------------------------------------------------------------------- #
# Estimativas de tamanho
# --------------------------------------------------------------------------- #
def _estimate_mp3_mb(seconds: int, kbps: int) -> float | None:
    if not seconds:
        return None
    size_bytes = kbps * 1000 / 8 * seconds
    return round(size_bytes / (1024 * 1024), 1)


def _estimate_mp4_mb(info: dict) -> float | None:
    """Maior tamanho plausível entre os formatos de vídeo <= 1080p.

    O tamanho exato só é conhecido após o merge; isto é uma aproximação.
    """
    duration = int(info.get("duration") or 0)
    best_bytes = 0.0
    for fmt in info.get("formats") or []:
        vcodec = fmt.get("vcodec")
        if not vcodec or vcodec == "none":
            continue
        height = fmt.get("height") or 0
        if height and height > 1080:
            continue

        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if not size and fmt.get("tbr") and duration:
            size = fmt["tbr"] * 1000 / 8 * duration
        if not size:
            continue

        # Formato só de vídeo: soma uma faixa de áudio estimada.
        if (fmt.get("acodec") in (None, "none")) and duration:
            size += _ASSUMED_AUDIO_KBPS * 1000 / 8 * duration

        best_bytes = max(best_bytes, size)

    if not best_bytes:
        return None
    return round(best_bytes / (1024 * 1024), 1)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _format_duration(seconds: int) -> str:
    if not seconds:
        return "?"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _friendly_error(raw: str) -> str:
    text = raw.lower()
    # Remove o prefixo "ERROR: " que o yt-dlp costuma colocar.
    clean = re.sub(r"^error:\s*", "", raw, flags=re.IGNORECASE).strip()

    if "unavailable" in text or "this video is not available" in text:
        return "Este vídeo está indisponível."
    if "private video" in text:
        return "Este vídeo é privado."
    if "members-only" in text or "join this channel" in text:
        return "Este vídeo é exclusivo para membros do canal."
    if "age" in text and ("restrict" in text or "confirm your age" in text):
        return "Este vídeo tem restrição de idade e exige login no YouTube."
    if "sign in" in text or "log in" in text or "not a bot" in text or "cookies" in text:
        return (
            "O YouTube pediu login/confirmação para acessar este vídeo. "
            "Tente outro link."
        )
    if "geo" in text or "not available in your country" in text or "region" in text:
        return "Este vídeo está bloqueado na sua região."
    if "unsupported url" in text or "is not a valid url" in text:
        return "Link não reconhecido como um vídeo do YouTube."
    if "unable to download webpage" in text or "getaddrinfo" in text or "timed out" in text:
        return "Falha de conexão ao acessar o YouTube. Verifique sua internet."
    if "ffmpeg" in text or "ffprobe" in text:
        return (
            "ffmpeg não encontrado. Instale o ffmpeg e garanta que ele está "
            "no PATH do sistema (veja o USAGE.md)."
        )
    return f"Não foi possível processar este vídeo: {clean}"
