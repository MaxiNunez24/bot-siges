# 🤖 Bot de carga al SiGeS

Completa el formulario "Agregar estudiante" del SiGeS a partir de la planilla de respuestas del
formulario de inscripción. **Antes de tocar el sistema, revisa los datos** y frena a quien tenga
algo raro (DNI con dígitos de más, fecha imposible, domicilio vacío…).

Es parte del Sistema de Asistencias que hace el curso de Pensamiento Computacional del CFP. Cómo
está pensado y por qué: [COMO-FUNCIONA.md](COMO-FUNCIONA.md).

---

## Para la preceptoría: la aplicación

### Instalarla (una sola vez)

Hace falta una compu con **Windows 10 u 11** y unos **600 MB libres**. No se instala Python ni
ningún otro programa: si la compu tiene **Chrome** usa Chrome; si no, **Edge**; y si no tiene
ninguno de los dos (pasa en algunas Windows "livianas"), usa un navegador que viene adentro del .zip.

1. **Bajar el archivo `Bot-SiGeS.zip`** (unos 240 MB):
   **[⬇️ Descargar Bot-SiGeS.zip](https://github.com/MaxiNunez24/bot-siges/releases/latest/download/Bot-SiGeS.zip)**
   (siempre baja la última versión). Queda en **Descargas**. Si el navegador avisa que "no se
   descarga habitualmente", elegí **Conservar**.
2. **Descomprimirlo.** Clic derecho sobre `Bot-SiGeS.zip` → **Extraer todo…** → en "Los archivos
   se extraerán en esta carpeta", elegí **Documentos** → **Extraer**. Queda la carpeta
   `Documentos\Bot-SiGeS`.
   > ⚠️ No lo abras con doble clic desde adentro del .zip: Windows deja ver el .exe, pero no
   > arranca porque le faltan los archivos que lo acompañan. Siempre **Extraer todo** primero.
3. **Abrir `Bot-SiGeS.exe`**, dentro de esa carpeta. La primera vez Windows puede mostrar
   **"Windows protegió su PC"**, porque el programa no está firmado por una empresa: tocá
   **Más información** → **Ejecutar de todas formas**. No vuelve a preguntar.
4. **Dejar un acceso directo en el escritorio** (opcional). Clic derecho sobre `Bot-SiGeS.exe` →
   **Mostrar más opciones** → **Enviar a** → **Escritorio (crear acceso directo)**. Copiar el .exe
   solo al escritorio no sirve: tiene que quedarse en su carpeta.
5. **Comprobar que anda en esta compu**, sin tocar el SiGeS real: en la pestaña **Opciones**,
   tocá **🩺 Probar esta compu**. En medio minuto aparece un cartel: **"✅ El bot anda en esta
   compu. Usó Google Chrome…"** (o el navegador que haya encontrado). Si dice ❌, sacale una foto
   al cartel y mandásela al docente.

**Actualizar a una versión nueva:** guardá aparte `configuracion.json` (tus opciones), borrá la
carpeta `Bot-SiGeS` vieja, descomprimí la nueva igual que en el paso 2 y volvé a poner
`configuracion.json` adentro.

**Desinstalar:** borrar la carpeta `Bot-SiGeS`. No deja nada en otro lugar de la compu. La carpeta
`resultados` tiene DNI y nombres: no la compartas.

### Usarla

La ventana tiene cuatro pestañas, en orden:

1. **Cómo se usa**: el tutorial.
2. **Planilla**: se elige la planilla bajada de Google (**Archivo → Descargar → Microsoft Excel
   (.xlsx)**). Aparecen todos los inscriptos con una casilla:
   - las filas **pintadas de amarillo** vienen destildadas (se pueden tildar a mano);
   - las que tienen un **problema en los datos** aparecen en rojo con el motivo, y no se pueden
     tildar: hay que corregir la planilla y volver a importarla;
   - se puede filtrar por fecha de inscripción;
   - **rango**: "Cargar desde … hasta …" acepta número de fila, DNI, apellido o nombre de la
     primera y la última persona, o se mueven los dos extremos del deslizador. Solo se carga lo
     que queda a la vista;
   - **Buscar en cualquier columna** achica el listado mientras se escribe.
3. **Opciones**: la dirección del SiGeS, el **modo demo** (después de cada persona pregunta si
   quedó bien cargada), y los **valores fijos** para lo que la planilla todavía no pregunta
   (transporte, WhatsApp, vivienda). Distrito y Localidad: Ensenada. Se guarda en
   `configuracion.json`, al lado del programa.
4. **Cargar**: se abre una ventana de navegador **aparte** (no usa tus pestañas ni tus contraseñas
   guardadas), en **menu.abc.gob.ar**: **iniciás sesión vos** ahí, aunque ya tengas el SiGeS abierto
   en tu Chrome de siempre, entrás al SiGeS y abrís el listado del trayecto. Desde
   ahí el bot, por cada persona, toca **+**, busca el DNI, completa, y espera a que revises,
   apretes "Guardar estudiante" y hagas la encuesta. **⏹ Cancelar la carga** la frena en
   cualquier momento sin cerrar el programa (deja el resumen de lo hecho hasta ahí).
   El navegador **queda abierto** al terminar o al cancelar, hasta que se cierra su ventana: la
   sesión se inicia una sola vez, y se puede corregir a mano o cargar a los que faltaron.
   **🌐 Abrir el navegador** lo abre sin cargar a nadie (por ejemplo, para iniciar sesión antes).

Al terminar deja un resumen en `resultados/carga-AAAA-MM-DD_HH-MM.csv`: a quién completó, qué quedó
pendiente, qué se cargó con valores fijos y, en modo demo, si se marcó como bien cargado.

> **Valores fijos (provisorio).** Transporte, WhatsApp y Vivienda no están en el formulario de
> inscripción. Hasta que estén, con la casilla tildada el bot los completa siempre con los mismos
> valores (los que se eligen en Opciones), y lo anota en el resumen. Destildada, los deja marcados
> en amarillo para completarlos a mano. **Educación** sale de la planilla (una columna por nivel:
> completo, incompleto o cursando); solo si no viene se usan los valores fijos.

Para practicar sin tocar el sistema real: en Opciones, **Ensayo con el simulador**.

### Si el .exe no abre

Algunos antivirus frenan los programas armados con Python (lo mandan a cuarentena o lo borran). Si
pasa, avisale al docente. Plan B: con Python instalado (https://www.python.org, tildando **Add
python.exe to PATH**), bajar este repositorio y hacer doble clic en **`abrir_bot.bat`**: la primera
vez instala lo necesario, y abre la misma ventana.

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
.exe a propósito: arranca más rápido y los antivirus la frenan menos. Lleva adentro un Chromium
(por eso pesa ~240 MB), para las compus sin Chrome ni Edge.

Para probar el .exe armado (sin ventanas; deja el resultado en `resultados\autoprueba.txt`):

```
dist\Bot-SiGeS\Bot-SiGeS.exe --autoprueba --callado --navegador=chromium
```

`--navegador=chrome|msedge|chromium` fuerza uno; sin eso, prueba Chrome → Edge → el incluido. Para
publicar una versión: `gh release create vX.Y.Z Bot-SiGeS.zip`.

### Desde la terminal

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python app.py                                   # la ventana
python planilla_google.py "planilla.xlsx"       # revisar, sin navegador
python bot.py --lento                           # el simulador, con los datos de ejemplo
python bot.py "planilla.xlsx" --desde 01/10/2026 --real "https://menu.abc.gob.ar/"
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
