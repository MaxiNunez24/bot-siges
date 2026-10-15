# El proceso de carga en el SiGeS, paso a paso

> Sacado de las 36 capturas del proceso real (agosto 2026). Sirve para dos cosas: entender qué
> tiene que hacer el bot, y saber qué se rompe si el Ministerio cambia el formulario.

**Dónde ocurre:** `sisge.abc.gob.ar/#/gestion/centro/ver-estudiantes/<id-del-trayecto>`
Es una aplicación Angular: **no recarga la página**, cambia el contenido. Por eso el bot tiene que
*esperar a que aparezca* cada pantalla en vez de esperar a que cargue una página nueva.

**De dónde salen los datos:** la hoja de respuestas del formulario de Google
(`1 SEDE OP SW ADM CONTABLE 2026 (respuestas)`, pestaña `Form_Responses1`).

---

## Los pasos

| # | Dónde | Qué se hace |
|---|---|---|
| 1 | Estudiantes del trayecto | Botón **+** → se abre el buscador |
| 2 | Buscador | **Tipo de documento** = DNI, **Numero de documento** = el DNI → **Buscar estudiante** |
| 3 | Agregar estudiante | Se abre el formulario largo, ya con el DNI puesto |
| 4 | | Completar sección por sección (abajo el detalle) |
| 5 | | **Guardar** |
| 6 | Alerta | *"Estudiante asignado correctamente"* → **Entendido** |
| 7 | Pre inscriptos | La persona aparece en la tabla, con un 🗑️ para borrarla |
| 8 | ⛔ | **Generar matrícula inicial** — ESTO NO LO HACE EL BOT |

---

## Las secciones del formulario

| Sección | Campos | De dónde sale |
|---|---|---|
| **Tipo de carga** (oblig.) | Carga común / Clan / Matrícula indirecta / Eps / Contexto de encierro | Siempre **Carga común** |
| **Documento** (oblig.) | DNI ya cargado + estado: Físico / extraviado en trámite / extraviado no en trámite | Siempre **DNI Físico** |
| **Apellido/s y nombre/s** (oblig.) | Apellido/s *, Nombres | Planilla (columnas C y D) |
| **Sobrenombre** | Sobrenombre | — (vacío) |
| **Sexo según DNI** (oblig.) | Femenino / Masculino / X | Planilla, columna GÉNERO |
| **Identidad de género** (oblig.) | `mat-select` (⚠️ **no** es un `<select>`): Mujer / Varón / … | Planilla, columna GÉNERO |
| **Nacionalidad** (oblig.) | Nacionalidad | Planilla — **hay que normalizar** (`Arg`, `Argentino`…) |
| **Lugar de nacimiento** (oblig.) | Lugar de nacimiento | Planilla, columna PROVINCIA |
| **Fecha de nacimiento** (oblig.) | fecha `d/m/aaaa` | Planilla — **hay que validar** (aparecieron fechas futuras) |
| **Dirección** (oblig.) | sub-formulario: Calle, Altura, Torre, Piso, Depto, **Código postal**, Distrito, Localidad, Entre calles → *Agregar* | Planilla, columnas DOMICILIO y LOCALIDAD. **Hay que partir calle y altura** |
| **Vivienda** (oblig.) | sub-formulario: zona rural/urbana/encierro, cuántas personas, cuántos adultos, cuántos niños, hijos a cargo, lengua extranjera, lengua indígena, pueblos originarios → *Agregar* | ⚠️ **NO está en el formulario de Google.** Hoy se inventa |
| **Datos de contacto** (oblig.) | sub-formulario → *Agregar* | Planilla, columna CELULAR (sin 0 y sin 15) |
| **Transportes** (oblig.) | casillas: A pie/Bicicleta, Colectivo, Tren, Vehículo particular, Taxi/Remis, Otro | ⚠️ **NO está en el formulario.** Hoy se inventa |
| **Redes** | … | — |

---

## Lo que hay que tener en cuenta al automatizar

1. **Los sub-formularios se abren con un botón y se cierran con "Agregar".** No alcanza con llenar
   los campos: si no se toca *Agregar*, el dato no queda. Es el error más fácil de cometer.
2. **Tres secciones obligatorias no tienen datos de origen** (Vivienda, Transportes, y parte de
   Contacto). O el bot pone valores por defecto y lo deja marcado para revisar, o se agregan esas
   preguntas al formulario de inscripción. Lo segundo es la solución de fondo.
3. **Los rótulos son la parte estable, los `id` no.** En Angular Material los identificadores se
   generan solos y cambian entre versiones. Hay que buscar los campos por su etiqueta visible
   (`get_by_label("Apellido/s")`), que es además lo que ve una persona.
4. **El estado "pre inscripto" es reversible.** Ahí termina el trabajo del bot.

---

## ✅ Verificado contra la pantalla real (23/9/2026)

Preceptoría guardó con Ctrl+S el formulario **Agregar estudiante** vacío
(`material-docente/capturas_bot/siges-alta-alumno-23-09-2026.html`, fuera de Git). Esto es lo que
confirmó y lo que corrigió:

| | Qué se verificó |
|---|---|
| ✅ | **Los 68 rótulos del formulario tienen `for=`**: cada etiqueta está asociada a su campo, así que `get_by_label` los encuentra a todos |
| ✅ | Los `id` son generados por Angular (`mat-input-1`, `mat-radio-12-input`): **inservibles como selector** |
| ⚠️ | **Identidad de género es un `mat-select`**, no un `<select>`: `select_option` no funciona. Hay que abrirlo con un clic y elegir la opción |
| ⚠️ | **`check()` no sirve para los radios ni las casillas.** El `<input>` está tapado por el círculo que dibuja Material y Playwright no llega: hay que **hacer clic en la etiqueta** |
| ✅ | El botón de guardar se llama **"Guardar estudiante"** |
| ✅ | Los sub-formularios se abren con **"Agregar direccion"**, "Agregar vivienda", "Agregar contacto", "Agregar educacion", "Agregar trayectoria laboral" |

**Secciones que no teníamos mapeadas y aparecieron:** redes sociales, programas sociales
(PRO.GRE.SAR, AUH, SUBE, SUMAR…), **una lista larga de salud** (14 condiciones, internaciones,
operaciones, medicación), discapacidad, situación laboral y restricción judicial.

> 🔒 **Regla nueva, por esas secciones:** el bot **no toca salud, discapacidad ni restricción
> judicial**. No vienen del formulario de inscripción, y un valor por defecto inventado ahí no es
> un error menor: es un dato falso sobre la salud de alguien en el sistema del Ministerio. Esas las
> completa una persona, siempre.

---

## ✅ El proceso entero, relevado (15/10/2026)

Preceptoría mostró la carga de una persona de punta a punta y se guardaron **16 pantallas**
(`material-docente/capturas_bot/siges-2026-10-15/`, fuera de Git: tienen datos de personas). Con
eso se completó lo que faltaba. `probar_selectores.py` verifica sobre esas pantallas que cada
selector del bot encuentre **exactamente un** elemento.

| # | Pantalla | Qué hay |
|---|---|---|
| 1 | Listado del trayecto | Botón de ícono **`add`** (el "+"); y **Generar matrícula inicial**, que el bot nunca toca |
| 2 | Buscador | **Tipo de documento** (`mat-select`, hay que elegir DNI: no siempre viene puesto), `input[name=numero_de_documento]`, **Buscar estudiante** |
| 3 | Agregar estudiante | El formulario principal (ya relevado) |
| 4 | Sub-form **Dirección** | `calle`, `altura`, `torre`, `piso`, `departamento`, `codigo_postal`, `entre_calles` (por `name`); **Distrito** y **Localidad** son **buscadores**: se escribe y se elige de una lista. Cierra con **Agregar** |
| 5 | Sub-form **Vivienda** | `vivienda` = zona rural / urbana / contexto de encierro; `cuantas_personas`, `cuantos_adultos`, `cuantos_ninios`; `hijos`, `extranjera`, `indigena`, `originarios` = `true`/`false` |
| 6 | Sub-form **Contacto** | `tipo_de_contacto` (`mat-select`: Celular…), `valor` (el número), `con_whatsapp` = `true`/`false`, `descripcion` |
| 7 | Sub-form **Educación** | `max_nivel_alcanzado` (`mat-select`), `cursando`, `completo`, `orientacion` (`mat-select`), `intencion_de_finalizacion` |
| 8 | Guardar estudiante | — |
| 9 | 🆕 **Encuesta** | Por qué se inscribió, cómo imagina el nivel y la experiencia, una palabra de lo que espera, cómo se enteró… → **Finalizar inscripción** / Cancelar inscripción |
| 10 | Confirmación | *"¿Desea Finalizar la inscripción?"* → Si |
| 11 | Aviso | *"Inscripción finalizada correctamente."* → Entendido |

### Cómo se encuentra cada cosa

- **Campos de texto, por `formcontrolname` o `name`**: los pusieron los programadores del sistema,
  no cambian solos (los `id` sí).
- **Opciones, por el nombre del grupo y su `value`**: `sexo` = `femenino` / `masculino` / `x`,
  `tipo_de_carga` = `comun`, `estado_del_documento` = `DNI_fisico`. **Nunca por el texto**: hay
  nueve pares "Si / No" en el formulario, y "Si" encuentra varios.
- Con un diálogo abierto, **el fondo queda `aria-hidden`**: `get_by_role` no ve lo de atrás.

### Lo que no se puede saber sin el sistema vivo

El **formato de fecha** que acepta el calendario, las **opciones de los menús** (estaban cerrados) y
las de los **buscadores** de Distrito y Localidad. Para eso el bot **frena y le pide a la persona que
elija**: si no encuentra la opción exacta, no elige otra "parecida".

### 🔒 Lo que el bot no inventa (decisión del 15/10)

Vivienda, Transportes, WhatsApp sí/no, Educación y **la encuesta** son obligatorios, pero **no
vienen del formulario de inscripción**. Hoy, en la práctica, se completan inventando. Se planteó que
el bot los eligiera **al azar** "para no sesgar"; se decidió que **no**:

- un dato al azar **parece real**: en las estadísticas del Ministerio no se distingue de uno
  verdadero, y se usa (transporte, SUBE, planificación);
- la encuesta es **la opinión de una persona**: contestarla es firmar por ella.

El bot completa lo que tiene dato, **deja esas secciones resaltadas en amarillo** y las completa la
preceptora. **La solución de fondo: agregar esas preguntas al formulario de Google de inscripción**,
con las mismas opciones que el SiGeS. Desde ese momento el dato es real y el bot lo carga solo.
