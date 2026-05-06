"""
Flask sunucusunu baslatir.

Lokal:
    python3 run_server.py

Production (Hetzner):
    gunicorn 'webapp.app:app' -b 0.0.0.0:5001 -w 2 --timeout 120
"""
from webapp.app import app
from webapp import config


if __name__ == '__main__':
    print(f"Starting server on http://{config.HOST}:{config.PORT}")
    print(f"Debug mode: {'ON' if config.DEBUG else 'OFF'}")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )