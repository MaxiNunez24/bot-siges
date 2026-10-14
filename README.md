# 🤖 Bot de carga al SiGeS

Completa el formulario "Agregar estudiante" del SiGeS a partir de la planilla de respuestas del
formulario de inscripción. **Antes de tocar el sistema, revisa los datos** y frena a quien tenga
algo raro (DNI con dígitos de más, fecha imposible, domicilio vacío…).

Es parte del Sistema de Asistencias que hace el curso de Pensamiento Computacional del CFP. Cómo
está pensado y por qué: [COMO-FUNCIONA.md](COMO-FUNCIONA.md).

---

## Instalarlo (una sola vez)

Hace falta tener **Python** y **Git**. En una terminal (PowerShell):

```
git clone https://github.com/MaxiNunez24/bot-siges.git
cd bot-siges
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Usarlo

**1. Bajar la planilla.** En Google Sheets: **Archivo → Descargar → Microsoft Excel (.xlsx)**, y
guardarla en la carpeta `bot-siges`. Tiene que ser .xlsx porque un CSV no guarda los colores.

**2. Abrir la terminal en la carpeta y activar el entorno:**

```
cd bot-siges
.venv\Scripts\activate
```

**3. Revisar, sin abrir el navegador.** Muestra a quién cargaría y a quién no, y por qué:

```
python planilla_google.py "planilla.xlsx" --desde 01/07/2026 --hasta 31/07/2026
```

**4. Si la lista está bien, cargar:**

```
python bot.py "planilla.xlsx" --desde 01/07/2026 --hasta 31/07/2026 --real "https://sisge.abc.gob.ar/"
```

Con la planilla, el bot hace esto:

- **Saltea las filas pintadas de amarillo**, con cualquier tono de amarillo, aunque esté pintada una sola celda.
- **Filtra por fechas** con `--desde` y `--hasta`, según la columna **FECHA INSCRIPCIÓN**. Si esa
  columna no está, usa la Marca temporal.
- Avisa cuando la FECHA INSCRIPCIÓN no coincide con el día en que respondieron, porque suele ser
  un error de tipeo.

## Lo que el bot NO hace, a propósito

1. **No inicia sesión.** La sesión la abre una persona; el bot no tiene ni pide contraseñas.
2. **No busca el DNI ni guarda.** De cada persona, vos buscás el DNI y abrís "Agregar
   estudiante"; el bot completa lo que sabe y espera. Revisás y apretás "Guardar estudiante" vos.
3. **No toca salud, discapacidad ni restricción judicial**, ni Dirección, Vivienda o Contacto
   (esos sub-formularios todavía no están relevados).
4. **Nunca genera la matrícula inicial.** Quedan como pre inscriptos.

## Para practicar sin tocar el sistema real

```
python bot.py --lento
```

Carga los datos inventados de `datos_ejemplo.csv` en `siges_falso.html`, una copia del
formulario.

> ⚠️ Las planillas `.xlsx` están en el `.gitignore`: tienen datos personales y **no se suben** a
> este repositorio.
