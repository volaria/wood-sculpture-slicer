"""
API endpoint'lerinin is mantigi. Flask blueprint olarak app.py'ye baglanir.

Endpoint'ler:
  POST /api/upload                          - STL/OBJ dosya yukle
  POST /api/process                         - Pipeline calistir
  GET  /api/preview/<sid>/<filename>        - Preview PNG sun
  GET  /api/download/<sid>                  - Cikti ZIP olarak indir
"""
import io
import os
import zipfile
import logging
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, send_file, abort

from . import config
from . import sessions as session_mgr
from . import validators
from .validators import validate_nesting_params
from slicer.pipeline import run_pipeline
from slicer.loader import load_mesh, analyze_mesh

bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)


# =====================================================================
# UPLOAD
# =====================================================================

@bp.route('/upload', methods=['POST'])
def upload():
    """
    Multipart form-data: file=<.stl veya .obj>

    Yanit:
      200 {
        "session_id": "abc...",
        "filename": "Hermes.stl",
        "mesh_info": {vertex_count, face_count, extents, ...}
      }
      400 {"error": "..."}
      413 dosya cok buyuk (Flask MAX_CONTENT_LENGTH)
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya yuklenmedi (file alani eksik)'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Dosya adi bos'}), 400

    # Uzanti kontrolu
    safe_name = secure_filename(f.filename)
    if not safe_name:
        return jsonify({'error': 'Gecersiz dosya adi'}), 400

    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(config.ALLOWED_EXTENSIONS))
        return jsonify({
            'error': f'Sadece {allowed} kabul edilir (verilen: {ext})'
        }), 400

    # Yeni session olustur ve dosyayi kaydet
    try:
        session_id = session_mgr.create_session()
    except Exception as e:
        logger.exception("Session olusturulamadi")
        return jsonify({'error': 'Sunucu hatasi (session)'}), 500

    sp = session_mgr.session_path(session_id)
    upload_path = sp / f'upload{ext}'

    # Orijinal dosya adini sakla (uzantisiz) - process'te model_name olarak kullanilacak
    original_stem = os.path.splitext(safe_name)[0]
    (sp / 'model_name.txt').write_text(original_stem, encoding='utf-8')

    try:
        f.save(str(upload_path))
    except Exception as e:
        logger.exception("Dosya kaydedilemedi")
        session_mgr.delete_session(session_id)
        return jsonify({'error': 'Dosya kaydedilemedi'}), 500

    # Mesh analizi (hizli; pipeline'in tamami degil)
    try:
        mesh = load_mesh(str(upload_path))
        info = analyze_mesh(mesh)
    except Exception as e:
        logger.exception("Mesh okunamadi")
        session_mgr.delete_session(session_id)
        return jsonify({
            'error': f'Mesh dosyasi okunamadi: {type(e).__name__}'
        }), 400

    return jsonify({
        'session_id': session_id,
        'filename': safe_name,
        'mesh_info': {
            'vertex_count': int(info['vertex_count']),
            'face_count': int(info['face_count']),
            'is_watertight': bool(info['is_watertight']),
            'extents': [float(x) for x in info['extents']],
            'bounds_min': [float(x) for x in info['bounds_min']],
            'bounds_max': [float(x) for x in info['bounds_max']],
        },
    }), 200


# =====================================================================
# PROCESS
# =====================================================================

@bp.route('/process', methods=['POST'])
def process():
    """
    JSON govde:
      {
        "session_id": "abc...",
        "axis": "X", "size_axis": "Z",
        "size_mm": 250, "thickness_mm": 3.0,
        "kerf_mm": 0.08, "pin_diameter_mm": 3.0,
        "pin_min_size_mm": 30, "pin_grid_size_mm": 60,
        "edge_tick": false,
        "formats": ["dxf", "svg"]
      }

    Yanit:
      200 {
        "success": true,
        "slice_report": {...},
        "preview_urls": {"grid": "/api/preview/.../grid.png", ...},
        "plate_summary": [...],
        "download_url": "/api/download/abc..."
      }
      400 hata mesaji
    """
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'JSON govdesi gerekli'}), 400

    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id eksik'}), 400

    # Session var mi?
    sp = session_mgr.session_path(session_id)
    if sp is None:
        return jsonify({'error': 'Session bulunamadi (suresi dolmus olabilir)'}), 404

    # Yuklenmis dosyayi bul
    upload_files = list(sp.glob('upload.*'))
    if not upload_files:
        return jsonify({'error': 'Bu session\'da yuklenmis dosya yok'}), 400
    upload_path = upload_files[0]

    # Parametreleri dogrula
    clean, err = validators.validate_process_params(data)
    if err:
        return jsonify({'error': err}), 400

    # Nesting parametrelerini dogrula
    nclean, nerr = validate_nesting_params(data)
    if nerr:
        return jsonify({'error': nerr}), 400

    # Pipeline calistir (sync, max 60 sn beklenir)
    output_dir = session_mgr.session_output_dir(session_id)

    # Pipeline cagrisi - log_callback ile bilgi topla (debug icin)
    log_lines = []

    # Orijinal dosya adini oku (yoksa fallback)
    name_file = sp / 'model_name.txt'
    if name_file.exists():
        try:
            model_name = name_file.read_text(encoding='utf-8').strip()
        except Exception:
            model_name = 'sculpture'
    else:
        model_name = 'sculpture'

    try:
        result = run_pipeline(
            model_path=str(upload_path),
            output_dir=str(output_dir),
            model_name=model_name,
            axis=clean['axis'],
            size_axis=clean['size_axis'],
            size_mm=clean['size_mm'],
            thickness_mm=clean['thickness_mm'],
            kerf_mm=clean['kerf_mm'],
            pin_diameter_mm=clean['pin_diameter_mm'],
            pin_min_size_mm=clean['pin_min_size_mm'],
            pin_grid_size_mm=clean['pin_grid_size_mm'],
            edge_tick=clean['edge_tick'],
            formats=clean['formats'],
            generate_preview=True,
            export=True,
            verbose=False,
            log_callback=log_lines.append,
            # Nesting
            run_nesting=nclean.get('run_nesting', False),
            nesting_sheet_width=nclean.get('nesting_sheet_width', 297.0),
            nesting_sheet_height=nclean.get('nesting_sheet_height', 420.0),
            nesting_gap=nclean.get('nesting_gap', 2.0),
            nesting_rotation=nclean.get('nesting_rotation', True),
            nesting_preserve_grain=nclean.get('nesting_preserve_grain', False),
        )

    except Exception as e:
        logger.exception("Pipeline crashed")
        return jsonify({
            'error': f'Pipeline hatasi: {type(e).__name__}',
            'detail': str(e),
        }), 500

    if not result.get('success'):
        return jsonify({
            'error': result.get('error', 'Bilinmeyen hata'),
            'log': log_lines,
        }), 400

    # Preview URL'leri (frontend bunlarla img src yapacak)
    preview_urls = {}
    for key, abs_path in result.get('preview_paths', {}).items():
        # abs_path bir output/slices_grid_X.png gibi
        filename = os.path.basename(abs_path)
        preview_urls[key] = f'/api/preview/{session_id}/{filename}'

    return jsonify({
        'success': True,
        'session_id': session_id,
        'slice_report': result['slice_report'],
        'preview_urls': preview_urls,
        'plate_summary': result['plate_summary'],
        'download_url': f'/api/download/{session_id}',
        'formats': clean['formats'],
        'nesting': result.get('nesting'),
    }), 200


# =====================================================================
# PREVIEW (PNG sun)
# =====================================================================

@bp.route('/preview/<session_id>/<filename>', methods=['GET'])
def preview(session_id, filename):
    """
    Onizleme PNG'sini sandbox'la sun. Path traversal'i onler.
    """
    # Filename'i sandbox'la
    safe = secure_filename(filename)
    if not safe.endswith('.png'):
        abort(404)

    out_dir = session_mgr.session_output_dir(session_id)
    if out_dir is None:
        abort(404)

    target = session_mgr.safe_filename_within_session(
        session_id, f'output/{safe}'
    )
    if target is None or not target.exists():
        abort(404)

    return send_file(str(target), mimetype='image/png')


# =====================================================================
# DOWNLOAD ZIP
# =====================================================================

@bp.route('/download/<session_id>', methods=['GET'])
def download(session_id):
    """
    Session'in cikti dosyalarini ZIP olarak don.

    ZIP icerigi:
      - Pipeline'da uretilmis formatlara gore dxf/ ve/veya svg/ klasorleri
      - assembly_guide.txt
      - slices_grid_X.png ve slices_overlay_X.png (her zaman dahil)
    """
    sp = session_mgr.session_path(session_id)
    if sp is None:
        abort(404)

    out_dir = sp / 'output'
    if not out_dir.exists():
        abort(404)

    # Bellekte ZIP olustur
    buf = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in out_dir.rglob('*'):
            if path.is_file():
                # ZIP icindeki goreli yol
                arcname = path.relative_to(out_dir).as_posix()
                zf.write(path, arcname)
                file_count += 1

    if file_count == 0:
        abort(404)

    buf.seek(0)

    # Dosya adi: ilk yuklenmis dosyadan turet (eger varsa)
    filename = 'wood_sculpture_output.zip'
    upload_files = list(sp.glob('upload.*'))
    if upload_files:
        # 'upload' yerine session'in kisa hali
        short_id = session_id[:8]
        filename = f'sculpture_{short_id}.zip'

    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename,
    )
