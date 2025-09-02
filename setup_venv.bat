@echo off
echo Creando entorno virtual...
python -m venv venv

echo Activando entorno virtual...
call venv\Scripts\activate

echo Instalando dependencias...
pip install -r requirements.txt

echo --------------------------------------
echo ✅ Entorno virtual listo y dependencias instaladas
echo ℹ️ Ejecuta "venv\Scripts\activate" para activarlo manualmente en el futuro
pause

