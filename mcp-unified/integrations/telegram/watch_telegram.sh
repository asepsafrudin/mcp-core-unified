#!/bin/bash
# Telegram Watcher - Opsi 1: Polling
# Script ini akan mengecek pesan Telegram setiap 30 detik

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL=30

echo "=========================================="
echo "📱 Telegram Watcher - Cline Bridge"
echo "=========================================="
echo "Cek pesan setiap ${INTERVAL} detik..."
echo "Tekan Ctrl+C untuk berhenti"
echo ""

while true; do
    clear
    echo "=========================================="
    echo "📱 Telegram Watcher - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""
    
    cd "$SCRIPT_DIR" && python3 cline_reader.py
    
    echo ""
    echo "⏳ Menunggu ${INTERVAL} detik..."
    echo "Tekan Ctrl+C untuk berhenti"
    
    sleep $INTERVAL
done
