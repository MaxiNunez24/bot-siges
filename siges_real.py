"""Cómo se completa el formulario REAL del SiGeS.

Está separado de bot.py a propósito: el simulador de la clase y el sistema del
Ministerio son dos formularios distintos, y mezclarlos en una sola función llena
de `if` termina en que se rompen los dos. `bot.py` elige uno u otro según se
corra con `--real`.

De dónde salen estos rótulos
----------------------------
De la pantalla real guardada el 23/9/2026 (Ctrl+S sobre el formulario abierto),
en `material-docente/capturas_bot/`. Verificado sobre ese archivo: los 68
rótulos del formulario tienen `for=`, es decir que **cada etiqueta está asociada
a su campo**. Por eso se busca por el texto que se ve, con `get_by_label`, y no
por identificadores: los `id` de Angular Material (`mat-input-1`,
`mat-radio-12-input`) los genera el framework y cambian entre versiones.

Lo que este módulo NO hace, y no es un olvido
---------------------------------------------
1. **No inicia sesión ni busca el DNI.** Cuando arranca, la persona ya tiene que
   estar logueada y con el formulario "Agregar estudiante" abierto. Esa pantalla
   previa todavía no está relevada, y además mantiene la regla de siempre: la
   sesión la abre una persona.
2. **No toca salud, discapacidad, restricción judicial, redes ni programas
   sociales.** Son datos sensibles que no vienen del formulario de inscripción.
   Un valor por defecto inventado ahí no es un error menor: es un dato falso
   sobre la salud de alguien, en el sistema del Ministerio.
3. **No completa los sub-formularios** (Dirección, Vivienda, Contacto): se abren
   con sus propios botones y sus campos no están relevados todavía. El bot avisa
   cuáles quedan pendientes.
4. **No guarda.** Deja el formulario completo y la persona revisa y aprieta
   "Guardar estudiante". Y nunca, en ningún caso, "Generar matrícula inicial".
"""

# Rótulo visible en el formulario → clave de los datos que trae la planilla.
# El orden es el mismo en el que están en la pantalla, para que en una demo se
# vea al bot bajando por el formulario como lo haría una persona.
CAMPOS_DE_TEXTO = [
    ('Apellido/s', 'apellidos'),
    ('Nombres', 'nombres'),
    ('Nacionalidad', 'nacionalidad'),
    ('Lugar de nacimiento', 'lugar_nacimiento'),
    ('Fecha de nacimiento', 'fecha_nacimiento'),
]

# Opciones que se eligen siempre igual, sin mirar la planilla.
RADIOS_FIJOS = [
    ('Carga común', 'tipo de carga'),
    ('DNI Físico', 'estado del documento'),
]

# La planilla trae F / M / X; el formulario los llama así.
SEXO = {'F': 'Femenino', 'M': 'Masculino', 'X': 'X'}

# Secciones obligatorias que quedan para una persona (ver el punto 3 de arriba).
SUBFORMULARIOS = ['Dirección', 'Vivienda', 'Datos de contacto']


def _rotulo(page, texto):
    """El campo cuya etiqueta visible contiene `texto`.

    `exact=False` a propósito: en la pantalla los rótulos llevan el asterisco de
    obligatorio ("Apellido/s *") y no conviene depender de ese detalle.
    """
    return page.get_by_label(texto, exact=False).first


def _marcar(page, etiqueta):
    """Marca una opción (radio o casilla) haciendo clic en su ETIQUETA.

    No se usa `check()` sobre el input, aunque sería lo natural: en Angular
    Material el `<input type="radio">` de verdad está tapado por el circulito
    que dibuja el framework, y Playwright se queda esperando para siempre a que
    el punto quede libre ("intercepts pointer events"). Una persona tampoco le
    pega al input: le pega al texto de al lado. Eso es lo que hacemos, y además
    es lo que dispara los eventos que Angular escucha.
    """
    campo = _rotulo(page, etiqueta)
    if campo.count() == 0:
        return False
    ident = campo.get_attribute('id')
    if ident:
        page.locator(f'label[for="{ident}"]').first.click()
    else:
        campo.check(force=True)
    return True


def completar(page, datos, respirar=lambda: None):
    """Completa el formulario ya abierto. Devuelve (ok, detalle).

    No guarda: cuando termina, el formulario queda en pantalla para que una
    persona lo revise.
    """
    faltan = []

    for etiqueta, seccion in RADIOS_FIJOS:
        if not _marcar(page, etiqueta):
            return False, f'no encontré la opción "{etiqueta}" ({seccion}): ¿cambió el formulario?'
        respirar()

    for etiqueta, clave in CAMPOS_DE_TEXTO:
        valor = datos.get(clave)
        if valor in (None, ''):
            faltan.append(etiqueta)
            continue
        campo = _rotulo(page, etiqueta)
        if campo.count() == 0:
            return False, f'no encontré el campo "{etiqueta}": ¿cambió el formulario?'
        campo.fill(str(valor))
        respirar()

    # Sexo según DNI: son tres opciones, una por cada valor posible.
    etiqueta_sexo = SEXO.get(str(datos.get('sexo', '')).upper())
    if etiqueta_sexo is None:
        faltan.append('Sexo según DNI')
    elif not _marcar(page, etiqueta_sexo):
        return False, f'no encontré la opción de sexo "{etiqueta_sexo}"'
    else:
        respirar()

    # Identidad de género es un mat-select: un menú que dibuja Angular. No es un
    # <select> de HTML, así que se abre con un clic y se elige la opción, igual
    # que lo haría una persona.
    genero = datos.get('identidad_genero')
    if genero:
        ok, detalle = _elegir_en_menu(page, 'Identidad de genero', genero)
        if not ok:
            return False, detalle
        respirar()
    else:
        faltan.append('Identidad de género')

    pendientes = SUBFORMULARIOS + faltan
    return True, 'queda a mano: ' + ', '.join(pendientes)


def _elegir_en_menu(page, etiqueta, opcion):
    """Abre un mat-select por su rótulo y elige una opción por su texto."""
    menu = _rotulo(page, etiqueta)
    if menu.count() == 0:
        # Segundo intento: el campo que está adentro del bloque con ese rótulo.
        menu = page.locator('mat-form-field', has_text=etiqueta).locator('mat-select').first
        if menu.count() == 0:
            return False, f'no encontré el menú "{etiqueta}"'
    menu.click()
    eleccion = page.get_by_role('option', name=opcion, exact=False).first
    if eleccion.count() == 0:
        page.keyboard.press('Escape')
        return False, f'el menú "{etiqueta}" no tiene la opción "{opcion}"'
    eleccion.click()
    return True, ''
