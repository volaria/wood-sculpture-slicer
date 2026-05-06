"""
Session yonetimi: UUID uretimi, klasor yonetimi, eski session'lari temizleme.

Her istek kendi UUID klasorunde calisir:
  sessions/<uuid>/
    upload.stl              # yuklenmis model
    output/                 # pipeline ciktisi
      slices_grid_X.png
      slices_overlay_X.png
      dxf/
      svg/
      assembly_guide.txt

1 saatten eski session klasorleri her istekte otomatik silinir.
"""
import os
import uuid
import shutil
import time
from pathlib import Path
from typing import Optional

from . import config


def _now() -> float:
    return time.time()


def ensure_sessions_dir() -> Path:
    """sessions/ klasoru yoksa olustur, mevcut Path'i don."""
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return config.SESSIONS_DIR


def create_session() -> str:
    """
    Yeni session UUID uretir ve klasorunu hazirlar.
    Returns: session_id (string)
    """
    ensure_sessions_dir()
    session_id = uuid.uuid4().hex
    session_path = config.SESSIONS_DIR / session_id
    session_path.mkdir(parents=True, exist_ok=False)
    (session_path / 'output').mkdir(parents=True, exist_ok=True)
    return session_id


def session_path(session_id: str) -> Optional[Path]:
    """
    Session ID'den Path doner. Mevcut degilse None.
    Path traversal saldirilarina karsi UUID format kontrolu yapar.
    """
    # UUID hex format dogrulamasi (32 hex karakter)
    if not _is_valid_session_id(session_id):
        return None

    p = config.SESSIONS_DIR / session_id
    if not p.exists() or not p.is_dir():
        return None
    return p


def _is_valid_session_id(session_id: str) -> bool:
    """
    Session ID 32 hex karakter mi? Path traversal'i (../) onlemek icin.
    """
    if not isinstance(session_id, str):
        return False
    if len(session_id) != 32:
        return False
    try:
        int(session_id, 16)
        return True
    except ValueError:
        return False


def session_output_dir(session_id: str) -> Optional[Path]:
    """Session'in output/ alt klasorunu doner."""
    sp = session_path(session_id)
    if sp is None:
        return None
    out = sp / 'output'
    out.mkdir(parents=True, exist_ok=True)
    return out


def cleanup_old_sessions(ttl_sec: Optional[int] = None) -> int:
    """
    config.SESSION_TTL_SEC'den eski session klasorlerini siler.

    Returns: silinen session sayisi
    """
    if not config.SESSION_CLEANUP_ENABLED:
        return 0
    if ttl_sec is None:
        ttl_sec = config.SESSION_TTL_SEC

    ensure_sessions_dir()
    now = _now()
    deleted = 0

    for entry in config.SESSIONS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if not _is_valid_session_id(entry.name):
            # Beklenmedik isim - guvenlik icin dokunma
            continue

        try:
            age = now - entry.stat().st_mtime
            if age > ttl_sec:
                shutil.rmtree(entry, ignore_errors=True)
                deleted += 1
        except Exception:
            # mtime okunamadi vs - atla
            continue

    return deleted


def delete_session(session_id: str) -> bool:
    """Belirli bir session'i sil."""
    sp = session_path(session_id)
    if sp is None:
        return False
    try:
        shutil.rmtree(sp, ignore_errors=True)
        return True
    except Exception:
        return False


def safe_filename_within_session(session_id: str, relative_path: str) -> Optional[Path]:
    """
    Bir session icindeki dosyaya guvenli sekilde erismek icin.
    relative_path icin path traversal koruma yapar.
    """
    sp = session_path(session_id)
    if sp is None:
        return None

    # Hedef path'i resolve et ve session dizininin icinde mi kontrol et
    try:
        target = (sp / relative_path).resolve()
        sp_resolved = sp.resolve()
        # target, sp'nin icinde mi?
        target.relative_to(sp_resolved)
        return target
    except (ValueError, OSError):
        # relative_to ValueError dondurur eger target sp icinde degilse
        return None