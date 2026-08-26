@echo off
REM ==============================================================================
REM Script đóng gói ứng dụng thành 1 FILE .EXE DUY NHẤT cho Windows (Onefile)
REM ==============================================================================

echo ==============================================================================
echo  Bat dau dong goi PDFSerialRenamer thanh 1 file .exe duy nhat...
echo ==============================================================================

REM 1. Tao virtualenv neu chua co
if not exist venv (
    echo [1/3] Dang tao moi truong ao Python venv...
    python -m venv venv
)

REM 2. Kich hoat va cai dat thu vien
echo [2/3] Dang cai dat cac thu vien can thiet...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM 3. Don dep ban build cu
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 4. Thuc thi dong goi Onefile
echo [3/3] Dang dong goi file EXE doc lap...

set TESS_DATA_PARAM=
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo [OK] Phat hien Tesseract OCR tai C:\Program Files\Tesseract-OCR, dang nhung truc tiep vao file EXE...
    set TESS_DATA_PARAM=--add-data "C:\Program Files\Tesseract-OCR;tesseract_engine"
)

pyinstaller --noconfirm --onefile --windowed ^
    --name "PDFSerialRenamer" ^
    --add-data "ui/style.qss;ui" ^
    %TESS_DATA_PARAM% ^
    main.py

echo.
echo ==============================================================================
echo  BUILD THANH CONG!
echo  File chay duy nhat nam tai: dist\PDFSerialRenamer.exe
echo ==============================================================================
pause
