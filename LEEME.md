# 🤖 El bot del SiGeS — proyecto de la clase

Este proyecto carga alumnos en el **simulador** del SiGeS, solo, como lo haría una
persona con el mouse. Lo importante no es que tipee: es que **antes decide quién se puede
cargar y quién no**. Esa decisión la escriben ustedes.

## Qué hay en la carpeta

| Archivo | ¿De quién? | Qué hace |
|---|---|---|
| `alumno.py` | ✏️ **de ustedes** | La clase `Alumno`, que dice si está lista para cargarse |
| `planilla.py` | ✏️ **de ustedes** | Lee la planilla y arma un `Alumno` por fila |
| `bot.py` | ya viene hecho | Hace el control y después maneja el navegador |
| `ayudas.py` | ya viene hecho | Lo que el bot necesita y no es lo importante |
| `inscriptos.csv` | datos de prueba | Ocho inscriptos **inventados**, con errores a propósito |
| `siges_falso.html` | el simulador | Una copia del formulario del SiGeS, para practicar sin romper nada |
| `requirements.txt` | — | Lo que hay que instalar: Playwright |

## Para arrancar (una sola vez)

En VS Code: **Archivo → Abrir carpeta** y elegir esta carpeta. Después, en la terminal:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Para correrlo

```
python bot.py --solo-control    el control, sin abrir el navegador
python bot.py                   el control y después el navegador
python bot.py --lento           igual, pero con pausas para ver cada campo
```

## Las tres reglas del bot

1. Va contra el **simulador**, nunca contra el sistema real.
2. No se loguea en ningún lado: no tiene usuario ni contraseña.
3. Deja a los alumnos como **pre inscriptos**. La matrícula la genera una persona.

**El bot no decide: tipea.**
