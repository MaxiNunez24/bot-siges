@echo off
rem Arma dist\Bot-SiGeS\Bot-SiGeS.exe (y un .zip para pasarlo) a partir de app.py.
rem Se corre UNA vez en la compu del docente; la preceptora recibe el .zip.
rem El bot usa Chrome o Edge si estan; si no, el Chromium que va adentro del .zip.
cd /d "%~dp0"
if not exist .venv (
    py -m venv .venv || goto :error
)
.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller || goto :error
rem Con la variable en 0, Chromium se instala ADENTRO del paquete de Playwright,
rem y PyInstaller lo copia con el resto. --no-shell: sin la version "headless
rem shell", que el bot no usa (son ~100 MB menos).
set PLAYWRIGHT_BROWSERS_PATH=0
.venv\Scripts\python -m playwright install --no-shell chromium || goto :error
.venv\Scripts\pyinstaller --noconfirm --clean --windowed --name Bot-SiGeS ^
    --add-data "siges_falso.html;." ^
    --add-data "datos_ejemplo.csv;." ^
    app.py || goto :error
powershell -NoProfile -Command "Compress-Archive -Force dist\Bot-SiGeS Bot-SiGeS.zip" || goto :error
echo.
echo Listo: dist\Bot-SiGeS\Bot-SiGeS.exe  y  Bot-SiGeS.zip
echo Probalo con:  dist\Bot-SiGeS\Bot-SiGeS.exe --autoprueba --navegador=chromium
exit /b 0
:error
echo.
echo Algo fallo. Mira el mensaje de arriba.
exit /b 1
