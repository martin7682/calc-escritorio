# Calc

Calculadora de escritorio para Windows hecha en **Python + PySide6**.

## Características

- interfaz minimalista y compacta
- ingreso de operaciones por teclado
- formato numérico argentino
  - `.` como separador de millares
  - `,` como separador decimal
- el punto del teclado numérico se interpreta como coma decimal
- resultado siempre visible con decimales configurables
- memorias múltiples
- variables algebraicas
- historial reutilizable
- temas claro, oscuro y gris
- menú mínimo y atajos de teclado
- compilación a `.exe` con PyInstaller

## Archivo principal

El archivo principal del proyecto es:

```text
calculadora_minimal_teclado_menubar_formato_ar_v7.py
```

## Requisitos

- Python 3.10 o superior recomendado
- Windows
- PySide6

## Ejecutar desde Python

Instalar dependencias:

```bash
pip install PySide6
```

Ejecutar:

```bash
python calculadora_minimal_teclado_menubar_formato_ar_v7.py
```

## Compilar a .exe

### Opción rápida (onedir)

Genera una carpeta con el ejecutable y sus archivos asociados.  
Suele abrir más rápido que la versión `onefile`.

Archivo:

```text
generar_calc_v7_rapido_onedir.bat
```

Resultado esperado:

```text
dist\Calc\Calc.exe
```

### Opción archivo único (onefile)

Genera un único ejecutable.

Archivo:

```text
generar_calc_v7_onefile.bat
```

Resultado esperado:

```text
dist\Calc.exe
```

## Icono

Si el archivo `icono.ico` está en la misma carpeta que el script y el `.bat`, se usará automáticamente al compilar.

## Uso en otra PC

### Si compilaste en modo onedir
Copiar la carpeta completa:

```text
dist\Calc\
```

### Si compilaste en modo onefile
Copiar el archivo:

```text
dist\Calc.exe
```

No hace falta instalar Python en la otra PC si el ejecutable fue generado correctamente con PyInstaller.

## Atajos de teclado

- `Enter` → calcular
- `Esc` → limpiar operación
- `F1` → ayuda
- `Alt+A` → menú Acciones
- `Alt+T` → menú Tema
- `Alt+Y` → menú Ayuda
- `Ctrl+M` → memorias
- `Ctrl+Shift+V` → variables
- `Ctrl+H` → historial
- `Ctrl+G` → guardar resultado en memoria
- `Ctrl+Shift+G` → guardar resultado en variable

## Formato numérico

- `1234` se muestra como `1.234`
- `12,5` se autocompleta como `12,50`
- `12,` se autocompleta como `12,00`

## Estructura sugerida del repositorio

```text
Calc/
├─ calculadora_minimal_teclado_menubar_formato_ar_v7.py
├─ icono.ico
├─ generar_calc_v7_rapido_onedir.bat
├─ generar_calc_v7_onefile.bat
├─ README.md
└─ .gitignore
```

## Archivos que no conviene subir al repositorio

No conviene versionar artefactos generados o temporales:

- `dist/`
- `build/`
- `__pycache__/`
- `*.pyc`
- `*.spec`

## Licencia

Definir según el uso que quieras dar al proyecto.
