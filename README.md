# 🤖 Bot de carga al SiGeS

Completa el formulario "Agregar estudiante" del SiGeS a partir de la planilla de respuestas del
formulario de inscripción. **Antes de tocar el sistema, revisa los datos** y frena a quien tenga
algo raro (DNI con dígitos de más, fecha imposible, domicilio vacío…).

Es parte del Sistema de Asistencias que hace el curso de Pensamiento Computacional del CFP. Cómo
está pensado y por qué: [COMO-FUNCIONA.md](COMO-FUNCIONA.md).

---

## Para la preceptoría: la aplicación

Se recibe `Bot-SiGeS.zip`. Se descomprime en cualquier carpeta y se abre **`Bot-SiGeS.exe`**. No
hace falta instalar nada: usa Microsoft Edge, que viene con Windows.

La ventana tiene cuatro pestañas, en orden:

1. **Cómo se usa**: el tutorial.
2. **Planilla**: se elige la planilla bajada de Google (**Archivo → Descargar → Microsoft Excel
   (.xlsx)**). Aparecen todos los inscriptos con una casilla:
   - las filas **pintadas de amarillo** vienen destildadas (se pueden tildar a mano);
   - las que tienen un **problema en los datos** aparecen en rojo con el motivo, y no se pueden
     tildar: hay que corregir la planilla y volver a importarla;
   - se puede filtrar por fecha de inscripción.
3. **Opciones**: la dirección del SiGeS, el **modo demo** (después de cada persona pregunta si
   quedó bien cargada), y los **valores fijos** para lo que la planilla todavía no pregunta
   (transporte, WhatsApp, vivienda). Distrito y Localidad: Ensenada. Se guarda en
   `configuracion.json`, al lado del programa.
4. **Cargar**: se abre el navegador, **iniciás sesión vos** y abrís el listado del trayecto. Desde
   ahí el bot, por cada persona, toca **+**, busca el DNI, completa, y espera a que revises,
   apretes "Guardar estudiante" y hagas la encuesta.

Al terminar deja un resumen en `resultados/carga-AAAA-MM-DD_HH-MM.csv`: a quién completó, qué quedó
pendiente, qué se cargó con valores fijos y, en modo demo, si se marcó como bien cargado.

> **Valores fijos (provisorio).** Transporte, WhatsApp y Vivienda no están en el formulario de
> inscripción. Hasta que estén, con la casilla tildada el bot los completa siempre con los mismos
> valores (los que se eligen en Opciones), y lo anota en el resumen. Destildada, los deja marcados
> en amarillo para completarlos a mano. **Educación** sale de la planilla (una columna por nivel:
> completo, incompleto o cursando); solo si no viene se usan los valores fijos.

Para practicar sin tocar el sistema real: en Opciones, **Ensayo con el simulador**.

### Si el .exe no abre

Algunos antivirus frenan los programas armados con Python. Plan B: con Python instalado, doble clic
en **`abrir_bot.bat`** (la primera vez instala lo necesario). Es la misma ventana.

Para saber si el .exe anda en una compu, sin tocar nada real:

```
Bot-SiGeS.exe --autoprueba
```

Carga los datos inventados en el simulador, sin mostrar nada, y deja el resumen en `resultados/`.

## Lo que el bot NO hace, a propósito

1. **No inicia sesión.** La sesión la abre una persona; el bot no tiene ni pide contraseñas.
2. **No guarda, no contesta la encuesta, y nunca genera la matrícula inicial.** Completa, para y
   espera. Quedan como pre inscriptos.
3. **No pisa a nadie.** Si el DNI ya tenía datos cargados, no toca nada y avisa qué difiere.
4. **No toca salud, discapacidad, restricción judicial, redes ni programas sociales.**
5. **No elige "algo parecido".** Si un menú o un buscador no tiene exactamente la opción, la deja
   marcada para que la elijas vos.

---

## Para el docente

### Armar el .exe

```
armar_exe.bat
```

Deja `dist\Bot-SiGeS\Bot-SiGeS.exe` y `Bot-SiGeS.zip` (el que se pasa). Es una carpeta y no un solo
.exe a propósito: arranca más rápido y los antivirus la frenan menos.

### Desde la terminal

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python app.py                                   # la ventana
python planilla_google.py "planilla.xlsx"       # revisar, sin navegador
python bot.py --lento                           # el simulador, con los datos de ejemplo
python bot.py "planilla.xlsx" --desde 01/10/2026 --real "https://sisge.abc.gob.ar/"
python probar_selectores.py                     # los selectores contra las pantallas guardadas
```

`probar_selectores.py` necesita las pantallas del SiGeS real guardadas en
`capturas/siges-2026-10-15/` (fuera de Git: tienen datos de personas).

| Archivo | Qué hace |
|---|---|
| `app.py` | La ventana (tkinter). Corre el motor en otro hilo |
| `motor.py` | Maneja el navegador, persona por persona, y escribe el resumen |
| `siges_real.py` | El formulario real: qué toca, en qué orden, y qué no toca nunca |
| `planilla_google.py` | Lee el .xlsx (o .csv): columnas, filas amarillas, fechas |
| `normalizar.py` | Limpia los datos y frena lo que no se puede cargar con certeza |
| `bot.py` | La versión de terminal, y el simulador de la clase |
| `mapa_siges.md` | Cómo es el SiGeS por dentro, pantalla por pantalla |

> ⚠️ Las planillas `.xlsx`, las capturas, los resultados y `configuracion.json` están en el
> `.gitignore`: tienen datos personales y **no se suben** a este repositorio.
