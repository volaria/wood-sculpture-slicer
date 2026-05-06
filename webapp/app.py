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
from flask import Flask, jsonify, request, render_template

from . import config
from . import sessions as session_mgr
from . import api

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

    # Blueprint'leri kaydet
    app.register_blueprint(api.bp)

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
        """Ana sayfa."""
        return render_template('index.html')

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