@echo off
chcp 65001 >nul
echo Instalando las dependencias del prototipo (solo la primera vez)...
python -m venv venv || (echo No se encontro Python. Instala Python 3.12 marcando "Add python.exe to PATH". & pause & exit /b 1)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist conexion.ini copy conexion.ejemplo.ini conexion.ini >nul
echo.
echo Listo. Ahora edita conexion.ini (datos de la base de datos) y ejecuta iniciar.bat
pause
