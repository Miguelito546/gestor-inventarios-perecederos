@echo off
chcp 65001 >nul
echo Instalando las dependencias del prototipo (solo la primera vez)...
python -m venv venv || (echo No se encontro Python. Instala Python 3.12 marcando "Add python.exe to PATH". & pause & exit /b 1)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Listo. Ahora edita configuracion.py (contrasena y puerto de MariaDB) y ejecuta iniciar.bat
pause
