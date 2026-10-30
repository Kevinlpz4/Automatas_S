# ScriptAutomatas

Simulador de autómatas finitos por consola. Fase 1: autómata finito determinista (AFD)
ejecutable y estructuras de datos para AFN y AFN-λ. Solo biblioteca estándar de Python.

## Requisitos

- Python >= 3.10
- `pytest` (solo para ejecutar las pruebas)

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

El menú principal permite elegir AFD, AFN, AFN-λ o Salir. En fase 1, AFN y AFN-λ
muestran `Próximamente`. El submenú AFD permite cargar un JSON desde `ejemplos/`,
evaluar palabras y ver la definición del autómata.

## Pruebas

```bash
python -m pytest
```

Si tu sistema solo expone `python3`, usá `python3 -m pytest`.

## Nota para Windows

La consola puede no mostrar correctamente los símbolos no ASCII (por ejemplo `λ`) si la
página de códigos no es UTF-8. La aplicación reconfigura `stdout` a UTF-8 al iniciar, pero
para una visualización correcta usá Windows Terminal (o una consola con fuente UTF-8) y,
si hace falta, ejecutá `chcp 65001` antes de iniciar el programa.
