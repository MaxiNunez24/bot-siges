"""Cómo se completa el formulario REAL del SiGeS.

Está separado de bot.py a propósito: el simulador de la clase y el sistema del
Ministerio son dos formularios distintos, y mezclarlos en una sola función llena
de `if` termina en que se rompen los dos.

De dónde salen estos selectores
-------------------------------
De las 16 pantallas reales del proceso entero, guardadas el 15/10/2026 (en
`capturas/`, fuera de Git: tienen datos de personas). Ver `mapa_siges.md`.
`probar_selectores.py` verifica, sobre esas pantallas, que cada selector de acá
encuentre EXACTAMENTE un elemento.

Cómo se encuentra cada cosa (y por qué así)
-------------------------------------------
- **Los campos de texto, por `formcontrolname` o `name`** (`apellido`, `calle`).
  Los pusieron los programadores del sistema: no cambian solos. Los `id`
  (`mat-input-12`) sí, los genera Angular.
- **Las opciones, por el nombre del grupo y su `value`**: `sexo` = `femenino`,
  `hijos` = `false`. NO por el texto: en el formulario hay nueve pares "Si / No".
  Se hace clic en la etiqueta (el `<input>` lo tapa el circulito de Material).
- **Distrito y Localidad, por su rótulo**: son buscadores, se escribe y se elige.

Lo que no viene de la planilla
------------------------------
Vivienda, Transportes y WhatsApp sí/no no están en el formulario de
inscripción. Por defecto quedan resaltados para la preceptora. Si en la
aplicación se activa **"Completar con valores fijos"** (provisorio, hasta que
esas preguntas estén en el formulario), se cargan los valores que la persona
eligió en la pantalla de Opciones: nunca valores que el bot decida solo.

La encuesta del final (decisión del 21/10)
------------------------------------------
La completa el bot: la razón de inscripción y cómo se enteró, al azar entre las
opciones; las cuatro preguntas Si/No en No; nivel de contenidos y experiencia en
"Muy bueno"; y una palabra al azar de la lista de Opciones. Después toca
"Finalizar inscripción". En modo demo la confirmación ("Si" y "Entendido") la
hace la preceptora; si no, también el bot.

Lo que este módulo NO hace nunca
--------------------------------
Iniciar sesión · tocar salud, discapacidad, restricción judicial, redes o
programas sociales · pisar los datos de alguien ya cargado · guardar el
formulario "Agregar estudiante" · "Generar matrícula inicial".
"""
import random
import re
import unicodedata

# El tiempo que se le da a cada pantalla para aparecer. Es un sistema del
# Ministerio, con días lentos: mejor esperar de más que fallar por apurado.
ESPERA_MS = 20_000

# Lo que se usa si la aplicación no manda otra cosa. Se edita en la pantalla de
# Opciones (y se guarda en configuracion.json), no acá.
CONFIG_INICIAL = {
    'distrito': 'Ensenada',
    'localidad': 'Ensenada',
    'codigo_postal': '1925',
    'valores_fijos': False,
    'transporte': 'Colectivo',
    'whatsapp': True,
    'vivienda_zona': 'zona urbana',
    'vivienda_personas': 1,
    'vivienda_adultos': 1,
    'vivienda_ninios': 0,
    'vivienda_hijos': False,
    'lengua_extranjera': False,
    'lengua_indigena': False,
    'pueblos_originarios': False,
    'educacion_nivel': 'Secundario',
    'educacion_completo': True,
    'educacion_cursando': False,
    # Para "Si tuviera que definir en una palabra lo que espera de este curso": una al azar.
    'encuesta_palabras': ['Muy bueno', 'Excelente', 'Hermoso', 'Interesante', 'Útil', 'Enriquecedor',
                          'Motivador', 'Productivo', 'Genial', 'Fantástico'],
}

# Las opciones de cada cosa, tal como están en el formulario.
ZONAS = ['zona urbana', 'zona rural', 'contexto de encierro']
TRANSPORTES = ['A pie /Bicicleta', 'Colectivo', 'Tren', 'Vehículo particular', 'Taxi/Remis', 'Otro']
NIVELES = ['Primario', 'Secundario', 'Terciario', 'Universitario']
# "¿De qué manera accedió a la información…?": al azar entre estas ("Otros" no,
# que puede pedir aclarar cuál).
COMO_SE_ENTERO = ['Recomendacion de amigo-familiar', 'Cercanía a la institución', 'Publicidad en redes']
# Las preguntas Si/No de la encuesta: todas en No. "curso_de_interes" y
# "otro_curso" quedan así hasta que salgan del formulario de inscripción.
ENCUESTA_NO = ['vinculado_a_trabajo', 'consideracion_de_logro', 'curso_de_interes', 'otro_curso']
ENCUESTA_OPINION = 'Muy bueno'

# Campo de texto (por formcontrolname) → clave de los datos de la planilla.
CAMPOS_DE_TEXTO = [
    ('apellido', 'apellidos', 'Apellido/s'),
    ('nombre', 'nombres', 'Nombres'),
    ('nacionalidad', 'nacionalidad', 'Nacionalidad'),
    ('lugar_de_nacimiento', 'lugar_nacimiento', 'Lugar de nacimiento'),
    ('fecha_nacimiento', 'fecha_nacimiento', 'Fecha de nacimiento'),
]

RADIOS_FIJOS = [
    ('tipo_de_carga', 'comun', 'Carga común'),
    ('estado_del_documento', 'DNI_fisico', 'DNI Físico'),
    # Viene marcado en "Si", y con "Si" el SiGeS exige completar la trayectoria laboral.
    ('esta_trabajando', 'false', '¿Está trabajando? No'),
]

SEXO = {'femenino': 'femenino', 'masculino': 'masculino', 'x': 'x'}


def sin_acentos(texto):
    t = unicodedata.normalize('NFD', str(texto or ''))
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn').lower().strip()


def si_no(valor):
    return 'true' if valor else 'false'


# ─────────────────────────── Piezas ──────────────────────────────────────

def _aparece(loc, ms=None):
    """Espera a que aparezca; True/False en vez de un error de Playwright, que en
    plena demo no le dice nada a nadie."""
    try:
        loc.wait_for(timeout=ms or ESPERA_MS)
        return True
    except Exception:                                   # noqa: BLE001
        return False


def _desaparece(loc, ms=8_000):
    try:
        loc.wait_for(state='detached', timeout=ms)
        return True
    except Exception:                                   # noqa: BLE001
        return loc.count() == 0


def _campo(page, nombre):
    """Un campo por su formcontrolname (o su name, en los sub-formularios)."""
    loc = page.locator(f'[formcontrolname="{nombre}"]')
    if loc.count() == 0:
        loc = page.locator(f'input[name="{nombre}"]')
    return loc


def _radio(page, grupo, valor):
    """Elige una opción por el nombre de su grupo y su value. Devuelve (ok, detalle)."""
    boton = page.locator(f'mat-radio-button:has(input[type="radio"][name="{grupo}"][value="{valor}"])')
    n = boton.count()
    if n != 1:
        return False, f'esperaba UNA opción {grupo}={valor} y hay {n}'
    boton.locator('label').first.click()
    return True, ''


def _casilla(page, rotulo):
    """Tilda una casilla por su rótulo exacto (las de transporte no se repiten)."""
    caja = page.get_by_label(rotulo, exact=True)
    if caja.count() != 1:
        return False, f'esperaba UNA casilla "{rotulo}" y hay {caja.count()}'
    if not caja.is_checked():
        page.locator(f'label[for="{caja.get_attribute("id")}"]').first.click()
    return True, ''


def _boton(page, texto, exacto=True):
    return page.get_by_role('button', name=texto, exact=exacto)


def _elegir_opcion(page, texto):
    """En un menú o lista ya abierta, elige la opción con ese texto (sin importar
    tildes ni mayúsculas). Nunca elige una "parecida"."""
    opciones = page.get_by_role('option')
    if not _aparece(opciones.first, 5_000):
        return False
    buscado = sin_acentos(texto)
    for i in range(opciones.count()):
        op = opciones.nth(i)
        if sin_acentos(op.inner_text()) == buscado:
            op.click()
            return True
    return False


def _menu(page, abridor, opcion):
    abridor.click()
    if _elegir_opcion(page, opcion):
        return True, ''
    page.keyboard.press('Escape')
    return False, f'el menú no tiene la opción "{opcion}"'


def _buscador(page, rotulo, texto):
    # Por rol y no por rótulo: al tocarlo, Angular arma la lista desplegable
    # (role=listbox) con el mismo rótulo, y get_by_label encuentra dos.
    campo = page.get_by_role('combobox', name=rotulo, exact=True)
    if campo.count() != 1:
        return False, f'no encontré el buscador "{rotulo}"'
    campo.click()
    campo.fill('')
    campo.press_sequentially(texto, delay=60)   # como una persona: la lista se arma letra por letra
    if _elegir_opcion(page, texto):
        return True, ''
    campo.fill('')
    return False, f'"{texto}" no apareció en la lista de {rotulo}'


def _menu_al_azar(page, abridor):
    """Abre un menú y elige una de sus opciones al azar. Devuelve su texto, o None."""
    abridor.click()
    opciones = page.get_by_role('option')
    if not _aparece(opciones.first, 5_000):
        page.keyboard.press('Escape')
        return None
    textos = [opciones.nth(i).inner_text().strip() for i in range(opciones.count())]
    validas = [i for i, t in enumerate(textos) if t]
    if not validas:
        page.keyboard.press('Escape')
        return None
    i = random.choice(validas)
    opciones.nth(i).click()
    return textos[i]


def _resaltar(page, texto):
    """Recuadro amarillo alrededor de lo que falta: solo visual, en esta pantalla."""
    page.evaluate(
        """(texto) => {
            const t = texto.toLowerCase();
            const quien = [...document.querySelectorAll('button, h3, h4, mat-card-title, legend, span, div')]
              .find(e => e.children.length <= 2 &&
                         [t, t + ' (obligatorio)'].includes(e.textContent.trim().toLowerCase()));
            if (quien) { quien.style.outline = '3px solid #f1c40f'; quien.style.outlineOffset = '3px'; }
        }""",
        texto,
    )


def _agregar(page, campo_del_subform):
    """Toca "Agregar" y confirma que el sub-formulario se cerró (si no, el sistema
    no lo aceptó: falta algo obligatorio)."""
    _boton(page, 'Agregar').click()
    return _desaparece(campo_del_subform)


# ─────────────────────────── Los pasos ───────────────────────────────────

FORMULARIO, YA_EN_EL_CENTRO = 'formulario', 'ya en el centro'


def _carteles_renaper(page):
    """Las dos opciones del cartel "Actualizar datos por RENAPER": (actual, renaper)."""
    tarjeta = 'button:has(h3:text-is("Datos del estudiante {}"))'
    return page.locator(tarjeta.format('actual')), page.locator(tarjeta.format('por RENAPER'))


def buscar_dni(page, dni):
    """Del listado del trayecto a lo que muestre el SiGeS para ese DNI.

    Devuelve (resultado, detalle). `resultado` es FORMULARIO (se abrió "Agregar
    estudiante"), YA_EN_EL_CENTRO (la persona ya está inscripta en otro curso del
    centro: el SiGeS pregunta si usar sus datos actuales o los de RENAPER, y
    después va directo a la encuesta) o None si no se pudo (el motivo en `detalle`).
    """
    mas = page.locator('button:has(mat-icon:text-is("add"))')
    if mas.count() != 1:
        return None, f'esperaba UN botón "+" y hay {mas.count()}: ¿está abierto el listado del trayecto?'
    mas.click()
    tipo = page.get_by_label('Tipo de documento', exact=True)
    if not _aparece(tipo):
        return None, 'no se abrió el buscador de estudiantes al tocar "+"'
    if sin_acentos(tipo.inner_text()) != 'dni':
        ok, detalle = _menu(page, tipo, 'DNI')
        if not ok:
            return None, 'Tipo de documento: ' + detalle
    page.locator('input[name="numero_de_documento"]').fill(str(dni))
    _boton(page, 'Buscar estudiante', exacto=False).click()
    actual, _ = _carteles_renaper(page)
    if not _aparece(_campo(page, 'apellido').or_(actual)):
        return None, ('no se abrió el formulario "Agregar estudiante": '
                      'fijate qué mostró el sistema (¿ya está inscripto? ¿DNI inválido?)')
    return que_mostro(page), ''


def que_mostro(page):
    """Después de "Buscar estudiante": FORMULARIO, YA_EN_EL_CENTRO o None."""
    if _visible(_carteles_renaper(page)[0]):
        return YA_EN_EL_CENTRO
    if _visible(_campo(page, 'apellido')):
        return FORMULARIO
    return None


def comparar_con_el_centro(page, datos):
    """Con el cartel de RENAPER abierto: lo que difiere entre los datos que el centro
    ya tiene de la persona y la planilla (solo para avisar: se usan los del centro)."""
    actual, _ = _carteles_renaper(page)
    en_el_centro = {}
    for linea in actual.inner_text().splitlines():
        rotulo, _, valor = linea.partition(':')
        if valor.strip():
            en_el_centro[sin_acentos(rotulo)] = valor.strip()
    diferencias = []
    for rotulo, clave in (('Apellido', 'apellidos'), ('Nombres', 'nombres'),
                          ('Fecha de nacimiento', 'fecha_nacimiento')):
        en_siges = en_el_centro.get(sin_acentos(rotulo), '')
        en_planilla = str(datos.get(clave) or '')
        if sin_acentos(en_siges) != sin_acentos(en_planilla):
            diferencias.append(f'{rotulo}: en el centro "{en_siges}", en la planilla "{en_planilla}"')
    return diferencias


def usar_datos_actuales(page):
    """En el cartel de RENAPER elige "Datos del estudiante actual": en el centro se usan
    siempre esos, nunca los de RENAPER (que suelen venir incompletos). Devuelve
    True si se cerró el cartel y apareció la encuesta."""
    actual, _ = _carteles_renaper(page)
    actual.click()
    return _aparece(_boton(page, 'Finalizar inscripción'))


def ya_tiene_datos(page, datos):
    """None si el formulario vino vacío; si no, la lista de diferencias con la planilla."""
    if not _campo(page, 'apellido').input_value().strip():
        return None
    diferencias = []
    for nombre, clave, rotulo in CAMPOS_DE_TEXTO:
        en_pantalla = _campo(page, nombre).input_value().strip()
        en_planilla = str(datos.get(clave) or '').strip()
        if en_pantalla and en_planilla and sin_acentos(en_pantalla) != sin_acentos(en_planilla):
            diferencias.append(f'{rotulo}: en el SiGeS "{en_pantalla}", en la planilla "{en_planilla}"')
    return diferencias


def completar(page, datos, respirar=lambda: None, config=None, trabado=None):
    """Completa el formulario ya abierto. Devuelve (ok, pendientes, fijos).

    `ok` es False solo si la persona ya estaba cargada o algo del formulario no
    estaba donde se esperaba (el motivo va en `pendientes`). `fijos` dice qué se
    cargó con valores fijos, para dejarlo anotado en el resumen.

    `trabado(nombre, motivos, restantes, sigue_abierto)` se llama si un
    sub-formulario quedó abierto: le pide a la persona que lo arregle y devuelve
    True si lo cerró (entonces se sigue con los que faltan).
    """
    cfg = {**CONFIG_INICIAL, **(config or {})}
    pendientes, fijos = [], []

    previo = ya_tiene_datos(page, datos)
    if previo is not None:
        if previo:
            return False, ['la persona YA estaba cargada y no coincide: ' + '; '.join(previo)], []
        return False, ['la persona YA estaba cargada (coincide con la planilla): no se tocó nada'], []

    for grupo, valor, rotulo in RADIOS_FIJOS:
        ok, detalle = _radio(page, grupo, valor)
        if not ok:
            return False, [f'{rotulo}: {detalle}'], []
        respirar()

    for nombre, clave, rotulo in CAMPOS_DE_TEXTO:
        valor = datos.get(clave)
        if valor in (None, ''):
            pendientes.append(rotulo)
            continue
        campo = _campo(page, nombre)
        if campo.count() != 1:
            return False, [f'{rotulo}: esperaba UN campo y hay {campo.count()}'], []
        campo.fill(str(valor))
        if nombre == 'fecha_nacimiento':
            campo.press('Tab')              # el calendario interpreta la fecha al salir del campo
            if not campo.input_value().strip():
                pendientes.append('Fecha de nacimiento (el sistema no aceptó el formato)')
        respirar()

    sexo = SEXO.get(sin_acentos(datos.get('sexo')))
    if sexo is None:
        pendientes.append('Sexo según DNI')
    else:
        ok, detalle = _radio(page, 'sexo', sexo)
        if not ok:
            return False, [f'Sexo: {detalle}'], []
        respirar()

    genero = datos.get('identidad_genero')
    ok, detalle = (_menu(page, page.locator('mat-select[formcontrolname="identidad"]'), genero)
                   if genero else (False, 'no viene en la planilla'))
    if not ok:
        pendientes.append(f'Identidad de género ({detalle})')
    respirar()

    # Transporte: casillas sueltas, no un sub-formulario.
    if cfg['valores_fijos'] and cfg['transporte']:
        ok, detalle = _casilla(page, cfg['transporte'])
        if ok:
            fijos.append(f'Transporte: {cfg["transporte"]}')
        else:
            pendientes.append(f'Transportes ({detalle})')
    else:
        pendientes.append('Transportes')
        _resaltar(page, 'Transportes')

    # Los sub-formularios: uno abierto por vez. Contacto va ÚLTIMO porque, sin
    # valores fijos, queda abierto esperando el WhatsApp.
    # Cada uno con un campo que solo se ve mientras está abierto.
    pasos = [('Dirección', _direccion, lambda: _campo(page, 'calle')),
             ('Educación', _educacion, lambda: page.locator('mat-select[formcontrolname="max_nivel_alcanzado"]')),
             ('Vivienda', _vivienda, lambda: _campo(page, 'cuantas_personas')),
             ('Contacto', _contacto, lambda: page.locator('mat-select[formcontrolname="tipo_de_contacto"]'))]
    for i, (nombre, paso, campo) in enumerate(pasos):
        falta, fijo, abierto = paso(page, datos, cfg, respirar)
        fijos += fijo
        restantes = [otro for otro, *_ in pasos[i + 1:]]
        # Quedó uno abierto: los que siguen no se pueden abrir hasta cerrarlo. Se
        # le pide a la persona que lo arregle y, si lo cierra, se sigue con el resto.
        if abierto and restantes and trabado and trabado(nombre, falta, restantes,
                                                         lambda campo=campo: _visible(campo())):
            continue
        pendientes += falta
        if abierto:
            pendientes += [f'{otro} (después de cerrar {nombre})' for otro in restantes]
            break

    return True, pendientes, fijos


def hay_encuesta(page):
    return _visible(_boton(page, 'Finalizar inscripción'))


def completar_encuesta(page, cfg, respirar=lambda: None, confirmar=True):
    """Completa la encuesta abierta y toca "Finalizar inscripción". Con `confirmar`
    también contesta "Si" a "¿Desea finalizar…?" y "Entendido" al aviso; sin él
    (modo demo) eso queda para la preceptora.

    Devuelve (pendientes, respuestas): lo que no se pudo y lo que se contestó.
    Si falta algo, no toca "Finalizar inscripción".
    """
    cfg = {**CONFIG_INICIAL, **(cfg or {})}
    falta, respuestas = [], []
    # Los tres menús se llaman igual ("razon"): van en este orden.
    menus = page.locator('mat-select[name="razon"]')
    if menus.count() != 3:
        return [f'Encuesta: esperaba 3 menús y hay {menus.count()}'], []

    razon = _menu_al_azar(page, menus.nth(0))
    if razon:
        respuestas.append(f'razón: {razon}')
    else:
        falta.append('Encuesta: la razón de inscripción (el menú no mostró opciones)')
    respirar()
    for i, rotulo in ((1, 'nivel de contenidos'), (2, 'experiencia')):
        ok, detalle = _menu(page, menus.nth(i), ENCUESTA_OPINION)
        if not ok:
            falta.append(f'Encuesta: {rotulo} ({detalle})')
        respirar()
    for grupo in ENCUESTA_NO:
        ok, detalle = _radio(page, grupo, 'false')
        if not ok:
            falta.append(f'Encuesta: {detalle}')
        respirar()

    palabra = random.choice([p for p in cfg['encuesta_palabras'] if str(p).strip()] or [ENCUESTA_OPINION])
    _campo(page, 'definicion_por_palabra').fill(str(palabra).strip())
    respuestas.append(f'palabra: {palabra}')
    respirar()

    como = random.choice(COMO_SE_ENTERO)
    boton = page.locator(f'mat-radio-button:has(input[type="radio"][value="{como}"])')
    if boton.count() == 1:
        boton.locator('label').first.click()
        respuestas.append(f'se enteró por: {como}')
    else:
        falta.append(f'Encuesta: cómo se enteró (no encontré "{como}")')
    respirar()

    if falta:
        _resaltar(page, 'Finalizar inscripción')
        return falta, respuestas
    _boton(page, 'Finalizar inscripción').click()
    if not confirmar:
        return [], respuestas
    si = page.get_by_role('button', name=re.compile(r'^\s*s[ií]\s*$', re.IGNORECASE))
    if not _aparece(si):
        return ['Encuesta: no apareció "¿Desea finalizar la inscripción?": confirmala vos'], respuestas
    si.first.click()
    entendido = _boton(page, 'Entendido')
    if not _aparece(entendido):
        return ['Encuesta: no apareció "Inscripción finalizada correctamente"'], respuestas
    entendido.click()
    return [], respuestas


def _visible(loc):
    return loc.count() > 0 and loc.first.is_visible()


def en_el_listado(page):
    """¿Volvió la persona al listado del trayecto? (el formulario y los carteles, como el
    de RENAPER o la encuesta, cerrados, y el "+" a la vista)"""
    return (not _visible(_campo(page, 'apellido')) and not _visible(page.locator('mat-dialog-container'))
            and _visible(page.locator('button:has(mat-icon:text-is("add"))')))


# Cada sub-formulario devuelve (pendientes, cargado_con_fijos, quedo_abierto).
# Los `llenar_*` suponen el sub-formulario ya abierto: así se prueban solos sobre
# la pantalla guardada donde está abierto (ver probar_selectores.py).

def _direccion(page, datos, cfg, respirar):
    if not datos.get('calle'):
        _resaltar(page, 'Agregar direccion')
        return ['Dirección (no se pudo partir el domicilio de la planilla)'], [], False
    _boton(page, 'Agregar direccion').click()
    if not _aparece(_campo(page, 'calle')):
        return ['Dirección (no se abrió el sub-formulario)'], [], False
    return llenar_direccion(page, datos, cfg, respirar)


def llenar_direccion(page, datos, cfg, respirar, agregar=True):
    _campo(page, 'calle').fill(datos['calle'])
    respirar()
    if datos.get('altura'):
        _campo(page, 'altura').fill(str(datos['altura']))
        respirar()
    if datos.get('entre_calles'):
        _campo(page, 'entre_calles').fill(datos['entre_calles'])
        respirar()
    if cfg.get('codigo_postal'):
        _campo(page, 'codigo_postal').fill(str(cfg['codigo_postal']))
        respirar()
    falta = []
    # Lo que dice la planilla (Punta Lara → Ensenada, Berisso → La Plata…); si no, lo de Opciones.
    for rotulo, clave in (('Distrito', 'distrito'), ('Localidad', 'localidad')):
        ok, detalle = _buscador(page, rotulo, datos.get('lugar_siges') or cfg[clave])
        if not ok:
            falta.append(detalle)
        respirar()
    if falta:
        _resaltar(page, 'Agregar')
        return ['Dirección: ' + '; '.join(falta) + ', y tocá "Agregar"'], [], True
    if agregar and not _agregar(page, _campo(page, 'calle')):
        return ['Dirección: el sistema no aceptó "Agregar" (¿falta algo obligatorio?)'], [], True
    return [], [], False


def _educacion(page, datos, cfg, respirar):
    edu = datos.get('educacion')
    de_fijos = False
    if not edu:
        if not cfg['valores_fijos']:
            _resaltar(page, 'Agregar educacion')
            return ['Educación'], [], False
        edu = {'nivel': cfg['educacion_nivel'], 'completo': cfg['educacion_completo'],
               'cursando': cfg['educacion_cursando']}
        de_fijos = True
    _boton(page, 'Agregar educacion').click()
    if not _aparece(page.locator('mat-select[formcontrolname="max_nivel_alcanzado"]')):
        return ['Educación (no se abrió el sub-formulario)'], [], False
    falta, abierto = llenar_educacion(page, edu, respirar)
    return falta, ([f'Educación: {edu["nivel"]}'] if de_fijos and not falta else []), abierto


def llenar_educacion(page, edu, respirar, agregar=True):
    menu = page.locator('mat-select[formcontrolname="max_nivel_alcanzado"]')
    ok, detalle = _menu(page, menu, edu['nivel'])
    if not ok:
        _resaltar(page, 'Agregar')
        return [f'Educación: {detalle}, y tocá "Agregar"'], True
    respirar()
    for grupo, valor in (('completo', edu.get('completo')), ('cursando', edu.get('cursando'))):
        if valor is not None:
            ok, detalle = _radio(page, grupo, si_no(valor))
            if not ok:
                return [f'Educación: {detalle}'], True
            respirar()
    if agregar and not _agregar(page, menu):
        return ['Educación: el sistema no aceptó "Agregar" (¿falta algo obligatorio?)'], True
    return [], False


def _vivienda(page, datos, cfg, respirar):
    if not cfg['valores_fijos']:
        _resaltar(page, 'Agregar vivienda')
        return ['Vivienda'], [], False
    _boton(page, 'Agregar vivienda').click()
    if not _aparece(_campo(page, 'cuantas_personas')):
        return ['Vivienda (no se abrió el sub-formulario)'], [], False
    falta, abierto = llenar_vivienda(page, cfg, respirar)
    return falta, ([] if falta else ['Vivienda']), abierto


def llenar_vivienda(page, cfg, respirar, agregar=True):
    radios = [('vivienda', cfg['vivienda_zona']), ('hijos', si_no(cfg['vivienda_hijos'])),
              ('extranjera', si_no(cfg['lengua_extranjera'])), ('indigena', si_no(cfg['lengua_indigena'])),
              ('originarios', si_no(cfg['pueblos_originarios']))]
    numeros = [('cuantas_personas', cfg['vivienda_personas']), ('cuantos_adultos', cfg['vivienda_adultos']),
               ('cuantos_ninios', cfg['vivienda_ninios'])]
    ok, detalle = _radio(page, *radios[0])
    if not ok:
        return [f'Vivienda: {detalle}'], True
    respirar()
    for nombre, valor in numeros:
        _campo(page, nombre).fill(str(valor))
        respirar()
    for grupo, valor in radios[1:]:
        ok, detalle = _radio(page, grupo, valor)
        if not ok:
            return [f'Vivienda: {detalle}'], True
        respirar()
    if agregar and not _agregar(page, _campo(page, 'cuantas_personas')):
        return ['Vivienda: el sistema no aceptó "Agregar" (¿falta algo obligatorio?)'], True
    return [], False


def _contacto(page, datos, cfg, respirar):
    celular = datos.get('celular')
    if not celular:
        _resaltar(page, 'Agregar contacto')
        return ['Contacto (no hay celular en la planilla)'], [], False
    _boton(page, 'Agregar contacto').click()
    if not _aparece(page.locator('mat-select[formcontrolname="tipo_de_contacto"]')):
        return [f'Contacto (no se abrió el sub-formulario): el celular es {celular}'], [], False
    return llenar_contacto(page, celular, cfg, respirar)


def llenar_contacto(page, celular, cfg, respirar, agregar=True):
    ok, detalle = _menu(page, page.locator('mat-select[formcontrolname="tipo_de_contacto"]'), 'Celular')
    if not ok:
        return [f'Contacto: {detalle}; el celular es {celular}'], [], True
    respirar()
    _campo(page, 'valor').fill(str(celular))
    respirar()
    if not cfg['valores_fijos']:
        _resaltar(page, 'Agregar')
        return ['Contacto: elegí si tiene WhatsApp y tocá "Agregar"'], [], True
    ok, detalle = _radio(page, 'con_whatsapp', si_no(cfg['whatsapp']))
    if not ok:
        return [f'Contacto: {detalle}'], [], True
    respirar()
    if agregar and not _agregar(page, _campo(page, 'valor')):
        return ['Contacto: el sistema no aceptó "Agregar" (¿falta algo obligatorio?)'], [], True
    return [], [f'WhatsApp: {"tiene" if cfg["whatsapp"] else "no tiene"}'], False
