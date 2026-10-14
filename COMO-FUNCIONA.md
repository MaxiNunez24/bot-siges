
## 1. Qué problema resuelve

Hoy, para inscribir a un alumno, alguien:

1. abre la planilla de respuestas del formulario de Google,
2. copia el DNI, lo pega en el SiGeS y toca **Buscar estudiante**,
3. completa a mano unos veinte campos leyendo de la planilla,
4. guarda,
5. **y vuelve a empezar con el siguiente.**

Con 30 inscriptos son unas dos horas de copiar y pegar, y cada campo es una oportunidad de
equivocarse. El bot hace los pasos 2 a 4.

---

## 2. Cómo funciona, en una frase

**Playwright abre un Chrome de verdad y hace exactamente lo que haría una persona**: escribe,
hace clic, espera que aparezca la pantalla siguiente.

No hay ninguna conexión secreta con el Ministerio ni nada "hackeado". Es el mismo navegador,
manejado desde Python en vez de con la mano. Si te parás al lado de la pantalla, ves los campos
llenarse solos.

> **Por qué así y no de otra forma.** Un sistema pensado para integrarse ofrecería una *API*: una
> puerta para que otros programas le hablen directo. El SiGeS no la tiene abierta para un CFP.
> Cuando no hay puerta, queda la ventana: automatizar el navegador. Es más frágil —si el
> Ministerio cambia el formulario, el bot deja de andar— pero es lo único disponible, y es
> exactamente lo que se hace en la industria cuando hay que integrarse con un sistema que no
> coopera.

---

## 3. Son DOS programas, no uno

Esta separación es la decisión de diseño más importante, y conviene poder explicarla:

```
   planilla de Google (CSV)
            │
            ▼
   [1] normalizar.py  ←── acá NO se toca el SiGeS
            │              limpia, controla y decide qué se puede cargar
            ├──────────────► ⛔ los que tienen problemas: los mira una persona
            ▼
   [2] bot.py         ←── acá recién se abre el navegador
            │              carga uno por uno lo que pasó el control
            ▼
        SiGeS (pre inscriptos)
```

**Por qué separado.** Los datos vienen de un formulario que llenaron 30 personas distintas, y
tienen de todo:

| Lo que llega | El problema |
|---|---|
| `Argentino`, `Argentina`, `Arg`, `argentina` | Cuatro formas de escribir lo mismo |
| Provincia: `Ensenada` | Es una localidad, no una provincia |
| Domicilio: `40000010` | Alguien pegó el DNI en la columna equivocada |
| Fecha: `13/10/2072` | Todavía no nació |
| Edad: `Completar` | Nunca lo completaron |

Si el bot cargara eso tal cual, **ensuciaría el sistema del Ministerio a 40 registros por minuto
en vez de a uno por minuto**. Esa frase es el corazón de todo esto:

> ⚠️ **Un bot no arregla un proceso malo: lo acelera.**

Por eso primero se limpia, y **lo que no se puede limpiar con certeza no se carga**: se informa
para que lo mire una persona. Con los datos de ejemplo, de 8 personas carga 5 y frena 3.

---

## 4. Las tres reglas que el bot no rompe

1. **Por defecto va contra el SIMULADOR**, no contra el sistema real. Para ir al real hay que
   pedirlo con `--real` y además escribir `CARGAR` cuando lo pregunta.
2. **Nunca inicia sesión solo.** No hay usuario ni contraseña en el código y no se los pide a
   nadie. La persona se loguea a mano y recién ahí el bot toma el control.
3. **Nunca aprieta "Generar matrícula inicial".** El bot deja a todos como **pre inscriptos**, que
   es un estado reversible —tiene un tachito al lado para borrarlo—. La matrícula la genera una
   persona, mirando la lista. Esa es la frontera entre "esto lo puede hacer una máquina" y "esto
   lo decide alguien".

---

## 5. El simulador

`siges_falso.html` es una copia de la estructura y los rótulos del formulario real, sacada de las
capturas del proceso. Se abre con doble clic.

Existe por tres razones, y las tres valen para cualquier proyecto:

1. **Se puede fallar sin consecuencias.** Un bot a medio hacer contra el sistema real deja
   registros basura que después alguien tiene que borrar a mano.
2. **No hace falta la contraseña de nadie.**
3. **Se puede mostrar en una demo o en la Expo** sin exponer datos de personas reales.

Cuando el bot anda contra el simulador, recién ahí se lo apunta al sistema de verdad. En la
industria a esto se le dice *entorno de pruebas*, y saltearlo es de las formas más caras de
ahorrar tiempo.

---

## 6. Cómo se corre

```bash
# 1. Ver qué se cargaría y qué no (no abre nada, es solo Python)
python normalizar.py datos_ejemplo.csv

# 2. El bot completo, contra el simulador, mostrando el navegador
python bot.py

# 3. Igual pero con pausas, para que se vea en una demo o en la Expo
python bot.py --lento

# 4. Contra el SiGeS de verdad (pide confirmación escrita)
python bot.py datos_reales.csv --real "https://sisge.abc.gob.ar/#/gestion/centro/ver-estudiantes/..."
```

Necesita, una sola vez:

```bash
pip install playwright
python -m playwright install chromium
```

---

## 7. Estado

✅ **Anda de punta a punta contra el simulador.** Probado: carga 5 de 8 personas y las 5 quedan en
la tabla de pre inscriptos con apellido, nombre, documento y fecha correctos. Las 3 restantes
quedan frenadas con el motivo.

❌ **Todavía no se probó contra el SiGeS real.** Falta:

- Ajustar los selectores. El simulador usa `id`; el SiGeS real es Angular Material y hay que
  ubicar los campos por su rótulo (`get_by_label`). Es media hora con el sistema abierto adelante.
- Los sub-formularios de **Vivienda**, **Datos de contacto** y **Transportes**, que en el real se
  abren con un botón "Agregar" y tienen campos que **no vienen del formulario de Google**
  (cuántas personas viven en el hogar, medio de transporte). Hoy los completa la preceptora
  inventando valores razonables. Dos caminos, y hay que elegir uno:
  - que el bot ponga valores por defecto y quede marcado para revisar, o
  - **agregar esas preguntas al formulario de inscripción** para que las conteste el propio
    alumno. Es lo que charlamos por WhatsApp y es la solución de fondo: el dato lo tiene que dar
    quien lo sabe.

---

## 8. Para la demo del viernes

Mostrar **en este orden**, que es el que cuenta la historia:

1. **La planilla de Google** con los datos como llegan, incluida la fila donde alguien puso el DNI
   en el domicilio. *"Esto es lo que hay."*
2. **`python normalizar.py`** — 5 listos, 3 frenados con el motivo. *"Antes de cargar nada, el
   programa revisa."* Este paso es el que más impresiona y es el más fácil de entender: es Python
   puro, sin navegador.
3. **`python bot.py --lento`** — el navegador llenando los campos solo. Acá no hace falta explicar
   nada, se ve.
4. **Decir que es el simulador**, y por qué. Que se note que es una decisión, no una limitación.

Y lo que hay que dejar dicho de entrada, antes de que lo pregunten:

> "Esto todavía no está conectado al SiGeS real. Cuando lo conectemos, va a dejar a los alumnos
> como **pre inscriptos** y la matrícula la va a seguir generando una persona. El bot no decide,
> tipea."
