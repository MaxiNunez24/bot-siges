@echo off
rem Plan B si el .exe no anda (un antivirus, una compu rara): abre la misma
rem ventana con Python. La primera vez instala lo necesario (tarda un poco).
cd /d "%~dp0"
if not exist .venv (
    echo Preparando todo por unica vez...
    py -m venv .venv || goto :sinpython
    .venv\Scripts\python -m pip install -q -r requirements.txt || goto :error
)
start "" .venv\Scripts\pythonw app.py
exit /b 0
:sinpython
echo No encontre Python. Instalalo desde https://www.python.org (tildar "Add to PATH").
pause
exit /b 1
:error
echo Algo fallo instalando. Mira el mensaje de arriba.
pause
exit /b 1
