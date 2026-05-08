"""
API parametre dogrulama. Tum sinir kontrolleri burada toplansin.

Kotunyetli istemcilerden gelen sayilari (negatif, sifir, devasa) reddeder
ve insancil hata mesajlari uretir.
"""
from typing import Tuple, Optional, Any

# Sinir degerleri
LIMITS = {
    'size_mm': (10, 2000),  # heykel boyutu mm
    'thickness_mm': (0.5, 30),  # plywood kalinligi mm
    'kerf_mm': (0.0, 1.0),  # lazer kerf
    'pin_diameter_mm': (1.0, 10.0),  # dowel pin capi
    'pin_min_size_mm': (5, 200),  # min plaka boyutu pin icin
    'pin_grid_size_mm': (20, 500),  # grid pin esik
}

VALID_AXES = {'X', 'Y', 'Z'}
VALID_FORMATS = {'dxf', 'svg'}


def _validate_number(value: Any, key: str) -> Tuple[Optional[float], Optional[str]]:
    """Bir sayisal parametreyi dogrula. (value, error) doner."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None, f"'{key}' sayi olmali"

    if not (v == v):  # NaN check
        return None, f"'{key}' gecerli bir sayi olmali"

    lo, hi = LIMITS[key]
    if v < lo or v > hi:
        return None, f"'{key}' {lo} ile {hi} arasinda olmali (verilen: {v})"

    return v, None


def validate_axis(value: Any, key: str = 'axis') -> Tuple[Optional[str], Optional[str]]:
    """Eksen parametresi (X/Y/Z)."""
    if not isinstance(value, str):
        return None, f"'{key}' string olmali (X, Y veya Z)"
    v = value.upper()
    if v not in VALID_AXES:
        return None, f"'{key}' X, Y veya Z olmali (verilen: {value})"
    return v, None


def validate_formats(value: Any) -> Tuple[Optional[list], Optional[str]]:
    """formats listesi: ['dxf'], ['svg'], veya ['dxf', 'svg']."""
    if not isinstance(value, list):
        return None, "'formats' liste olmali (orn: ['dxf', 'svg'])"
    if len(value) == 0:
        return None, "'formats' bos olamaz"

    cleaned = []
    for f in value:
        if not isinstance(f, str):
            return None, f"'formats' icindeki ogeler string olmali"
        fl = f.lower()
        if fl not in VALID_FORMATS:
            return None, f"'formats' sadece dxf veya svg icerebilir (verilen: {f})"
        if fl not in cleaned:
            cleaned.append(fl)
    return cleaned, None


def validate_bool(value: Any, key: str) -> Tuple[Optional[bool], Optional[str]]:
    """Bool parametresi - JSON'dan gelirken bazen string olabilir."""
    if isinstance(value, bool):
        return value, None
    if isinstance(value, (int, float)):
        return bool(value), None
    if isinstance(value, str):
        v = value.lower().strip()
        if v in ('true', '1', 'yes', 'on'):
            return True, None
        if v in ('false', '0', 'no', 'off', ''):
            return False, None
    return None, f"'{key}' bool olmali (true/false)"


def validate_process_params(data: dict) -> Tuple[Optional[dict], Optional[str]]:
    """
    POST /api/process icin gelen JSON govdesini dogrula.
    Bos veya eksik alanlar default'a duser (config.DEFAULTS).

    Returns: (clean_params, error_msg). error_msg None ise basarili.
    """
    from . import config

    if not isinstance(data, dict):
        return None, "Gecersiz istek govdesi (JSON object bekleniyor)"

    clean = {}
    defaults = config.DEFAULTS

    # Eksenler
    axis_raw = data.get('axis', defaults['axis'])
    val, err = validate_axis(axis_raw, 'axis')
    if err:
        return None, err
    clean['axis'] = val

    sa_raw = data.get('size_axis', defaults['size_axis'])
    val, err = validate_axis(sa_raw, 'size_axis')
    if err:
        return None, err
    clean['size_axis'] = val

    # Sayisal parametreler
    for key in ('size_mm', 'thickness_mm', 'kerf_mm',
                'pin_diameter_mm', 'pin_min_size_mm', 'pin_grid_size_mm'):
        raw = data.get(key, defaults[key])
        val, err = _validate_number(raw, key)
        if err:
            return None, err
        clean[key] = val

    # Bool
    et_raw = data.get('edge_tick', defaults['edge_tick'])
    val, err = validate_bool(et_raw, 'edge_tick')
    if err:
        return None, err
    clean['edge_tick'] = val

    # Formats
    fmt_raw = data.get('formats', defaults['formats'])
    val, err = validate_formats(fmt_raw)
    if err:
        return None, err
    clean['formats'] = val

    return clean, None

def validate_nesting_params(data: dict) -> tuple:
    """
    Nesting parametrelerini dogrula.
    Returns: (clean_params, error_msg)
    """
    if not isinstance(data, dict):
        return None, "Invalid request body"

    clean = {}

    # run_nesting
    rn_raw = data.get('run_nesting', False)
    val, err = validate_bool(rn_raw, 'run_nesting')
    if err:
        return None, err
    clean['run_nesting'] = val

    if not val:
        return clean, None  # nesting istenmiyorsa diger parametrelere bakma

    # Sheet boyutlari
    for key in ('nesting_sheet_width', 'nesting_sheet_height'):
        raw = data.get(key, 297.0 if 'width' in key else 420.0)
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None, f"'{key}' must be a number"
        if v < 50 or v > 3000:
            return None, f"'{key}' must be between 50 and 3000 mm (got {v})"
        clean[key] = v

    # Gap
    raw = data.get('nesting_gap', 2.0)
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None, "'nesting_gap' must be a number"
    if v < 0 or v > 20:
        return None, f"'nesting_gap' must be between 0 and 20 mm (got {v})"
    clean['nesting_gap'] = v

    # Rotation ve grain
    for key in ('nesting_rotation', 'nesting_preserve_grain'):
        raw = data.get(key, True if key == 'nesting_rotation' else False)
        val, err = validate_bool(raw, key)
        if err:
            return None, err
        clean[key] = val

    return clean, None