#!/bin/bash
# Wood Sculpture Slicer - Deploy script
# Run on server: bash deploy.sh

set -e

echo "==> Pulling latest code..."
cd /opt/wood-sculpture-slicer
git pull origin main

echo "==> Installing dependencies..."
source .venv/bin/activate
pip install -r requirements.txt -q

echo "==> Restarting service..."
systemctl restart wss

echo "==> Status:"
systemctl status wss --no-pager -l

echo "==> Done. https://slicer.volkanduran.com"