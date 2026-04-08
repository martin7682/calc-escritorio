@echo off
title Generar Calc.exe rapido (v7)
echo ==========================================
echo   Generando ejecutable rapido de Calc
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en PATH.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install pyinstaller PySide6

if not exist "calculadora_minimal_teclado_menubar_formato_ar_v7.py" (
    echo ERROR: No se encontro el archivo calculadora_minimal_teclado_menubar_formato_ar_v7.py
    echo Copia este .bat en la misma carpeta que el archivo .py
    pause
    exit /b 1
)

echo.
echo Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Calc.spec del /q Calc.spec

echo.
if exist "icono.ico" (
    echo Se encontro icono.ico. Compilando version rapida con icono...
    python -m PyInstaller --windowed --name Calc --icon=icono.ico "calculadora_minimal_teclado_menubar_formato_ar_v7.py"
) else (
    echo No se encontro icono.ico. Compilando version rapida sin icono...
    python -m PyInstaller --windowed --name Calc "calculadora_minimal_teclado_menubar_formato_ar_v7.py"
)

if errorlevel 1 (
    echo.
    echo ERROR: La compilacion fallo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Compilacion finalizada correctamente
echo ==========================================
echo Ejecutable generado en:
echo dist\Calc\Calc.exe
echo.
pause
