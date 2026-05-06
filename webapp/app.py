"""
Flask uygulamasi - ana giris.

Su an iskelet:
  GET  /          -> placeholder sayfa
  GET  /health    -> saglik kontrolu (deploy izleme icin)

Adim 4.2.b'de eklenecek:
  POST /api/upload
  POST /api/process
  GET  /api/preview/<session_id>/<filename>
  GET  /api/download/<session_id>
"""
import logging
from flask import Flask, jsonify, request

from . import config
from . import sessions as session_mgr


def create_app() -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
    )

    # Flask config
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_SIZE

    # Session klasoru hazir olsun
    session_mgr.ensure_sessions_dir()

    # Logging
    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    @app.before_request
    def cleanup_hook():
        """
        Her istek oncesi 1 saatten eski session klasorlerini temizle.
        Cron yerine bu yaklasim - lokal ve production'da bagimsiz calisir.
        Sadece statik olmayan istekler icin (CSS/JS her isteyene dogru).
        """
        if request.path.startswith('/static/'):
            return
        if request.path == '/health':
            return
        try:
            n = session_mgr.cleanup_old_sessions()
            if n > 0:
                app.logger.info(f"Cleaned up {n} old sessions")
        except Exception as e:
            # Cleanup hatalari istegimi bozmasin
            app.logger.warning(f"Session cleanup failed: {e}")

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @app.route('/')
    def index():
        """Ana sayfa - su an placeholder."""
        return """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <title>Wood Sculpture Slicer</title>
  <style>
    body {
      font-family: -apple-system, sans-serif;
      background: #0a0a0a;
      color: #e5e5e5;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .container {
      text-align: center;
      max-width: 480px;
      padding: 2rem;
    }
    h1 {
      font-weight: 300;
      letter-spacing: -0.02em;
      margin: 0 0 1rem;
    }
    .accent { color: #f59e0b; }
    p { color: #888; line-height: 1.5; }
    code {
      background: #1a1a1a;
      padding: 0.2em 0.4em;
      border-radius: 3px;
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Wood Sculpture <span class="accent">Slicer</span></h1>
    <p>Web arayuzu yapim asamasinda.</p>
    <p>Su an icin komut satiri:<br>
       <code>python3 main.py models/Hermes.stl --export</code></p>
  </div>
</body>
</html>
"""

    @app.route('/health')
    def health():
        """Saglik kontrolu - deploy izleme icin."""
        return jsonify({
            'status': 'ok',
            'version': '0.4.2a',
        })

    # Hata yakalayicilar
    @app.errorhandler(413)
    def too_large(e):
        max_mb = config.MAX_UPLOAD_SIZE / (1024 * 1024)
        return jsonify({
            'error': f'Dosya cok buyuk. Max boyut: {max_mb:.0f} MB.'
        }), 413

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Bulunamadi'}), 404

    return app


# Flask CLI ve gunicorn icin module-level app
app = create_app()