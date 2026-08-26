@echo off
REM ==============================================================================
REM Script đóng gói ứng dụng PDF Serial Renamer thành file .exe cho Windows
REM ==============================================================================

echo 🚀 Bắt đầu quá trình build cho Windows...

REM Kích hoạt virtualenv nếu có
if exist venv\Scripts\activate.bat (
    echo 📦 Kích hoạt virtualenv...
    call venv\Scripts\activate.bat
)

REM Dọn dẹp thư mục build cũ
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo ⚙️ Đang đóng gói với PyInstaller...

set TESS_DATA_PARAM=
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo [OK] Phat hien Tesseract OCR tai C:\Program Files\Tesseract-OCR, dang nhung truc tiep vao file EXE...
    set TESS_DATA_PARAM=--add-data "C:\Program Files\Tesseract-OCR;tesseract_engine"
)

pyinstaller --noconfirm --onedir --windowed ^
    --name "PDFSerialRenamer" ^
    --add-data "ui/style.qss;ui" ^
    %TESS_DATA_PARAM% ^
    main.py

echo ✅ Build thành công! Ứng dụng nằm tại: dist\PDFSerialRenamer\PDFSerialRenamer.exe
pause
