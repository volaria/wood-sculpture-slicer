"""
Web uygulamasi yapilandirmasi.
Lokal ve production icin tek dosya - environment variable'larla overrride edilebilir.
"""
import os
from pathlib import Path


# Base path: webapp/'un bir ust klasoru (proje koku)
BASE_DIR = Path(__file__).resolve().parent.parent

# Session ve cikti yollari
SESSIONS_DIR = BASE_DIR / 'sessions'

# Flask ayarlari
HOST = os.getenv('WSS_HOST', '127.0.0.1')   # production: '0.0.0.0'
PORT = int(os.getenv('WSS_PORT', '5001'))
DEBUG = os.getenv('WSS_DEBUG', '1') == '1'   # production: '0'

# Upload limitleri
MAX_UPLOAD_SIZE = 50 * 1024 * 1024            # 50 MB
ALLOWED_EXTENSIONS = {'.stl', '.obj'}

# Pipeline limitleri
MAX_PROCESS_TIME_SEC = 60                     # tek istek max suresi (loglama icin)

# Session yonetimi
SESSION_TTL_SEC = 60 * 60                     # 1 saat sonra eskimis sayilir
SESSION_CLEANUP_ENABLED = True                # her istekte eski session'lari temizle

# Rate limiting (lokal'de devre disi, production'da acik)
RATE_LIMIT_ENABLED = os.getenv('WSS_RATE_LIMIT', '0') == '1'
RATE_LIMIT_PER_HOUR = 20                      # IP basina saatte 20 istek

# Pipeline default'lari (kullanici override edebilir UI'den)
DEFAULTS = {
    'axis': 'X',
    'size_axis': 'Z',
    'size_mm': 250.0,
    'thickness_mm': 3.0,
    'kerf_mm': 0.08,
    'pin_diameter_mm': 3.0,
    'pin_min_size_mm': 30.0,
    'pin_grid_size_mm': 60.0,
    'edge_tick': False,
    'formats': ['dxf', 'svg'],
}