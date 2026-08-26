#!/bin/bash
# ==============================================================================
# Script đóng gói ứng dụng PDF Serial Renamer thành file .app cho macOS
# ==============================================================================

set -e

echo "🚀 Bắt đầu quá trình build cho macOS..."

# Kích hoạt virtualenv nếu có
if [ -d "venv" ]; then
    echo "📦 Kích hoạt virtualenv..."
    source venv/bin/activate
fi

# Cài đặt pyinstaller nếu chưa có
pip install pyinstaller

# Dọn dẹp bản build cũ
echo "🧹 Dọn dẹp thư mục build cũ..."
rm -rf build dist

# Thực thi PyInstaller
echo "⚙️ Đang đóng gói với PyInstaller..."
pyinstaller --noconfirm --onedir --windowed \
    --name "PDFSerialRenamer" \
    --add-data "ui/style.qss:ui" \
    main.py

echo "✅ Build thành công! Ứng dụng nằm tại: dist/PDFSerialRenamer.app"
