@echo off
rem Arma dist\Bot-SiGeS\Bot-SiGeS.exe (y un .zip para pasarlo) a partir de app.py.
rem Se corre UNA vez en la compu del docente; la preceptora recibe el .zip.
rem Usa Edge, que viene con Windows: no hace falta bajar ningun navegador.
cd /d "%~dp0"
if not exist .venv (
    py -m venv .venv || goto :error
)
.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller || goto :error
.venv\Scripts\pyinstaller --noconfirm --clean --windowed --name Bot-SiGeS ^
    --add-data "siges_falso.html;." ^
    --add-data "datos_ejemplo.csv;." ^
    app.py || goto :error
powershell -NoProfile -Command "Compress-Archive -Force dist\Bot-SiGeS Bot-SiGeS.zip" || goto :error
echo.
echo Listo: dist\Bot-SiGeS\Bot-SiGeS.exe  y  Bot-SiGeS.zip
exit /b 0
:error
echo.
echo Algo fallo. Mira el mensaje de arriba.
exit /b 1
