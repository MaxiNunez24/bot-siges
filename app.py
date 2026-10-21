"""La aplicación de escritorio del bot: importar la planilla, elegir a quién cargar, y ver el proceso.

    python app.py                (o el .exe, que es esto mismo empaquetado)

Las decisiones las toma la preceptora, en la ventana: a quién se carga, con qué
valores se completa lo que la planilla no trae, y cuándo se sigue con la
próxima persona. El bot nunca guarda, nunca contesta la encuesta y nunca toca
"Generar matrícula inicial".
"""
import queue
import threading
import unicodedata
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import motor
import normalizar
import planilla_google
import siges_real

FUENTE = ('Segoe UI', 11)

TUTORIAL = """\
Este programa completa el formulario "Agregar estudiante" del SiGeS a partir de la
planilla de inscripción. Escribe por vos lo que ya está en la planilla, y te deja a
vos todo lo que hay que decidir.

LOS PASOS

0.  La primera vez en cada compu: pestaña "Opciones" → "Probar esta compu". En
    medio minuto te dice si el bot anda y con qué navegador.

1.  Bajá la planilla de Google: Archivo → Descargar → Microsoft Excel (.xlsx).
    Tiene que ser .xlsx: así se ven las filas pintadas de amarillo.

2.  Pestaña "Planilla": elegí el archivo. Aparecen todos los inscriptos.
      · Las filas AMARILLAS vienen destildadas: no se cargan, salvo que las tildes.
      · Las que tienen un problema (un DNI raro, una fecha imposible) aparecen en
        rojo, con el motivo, y no se pueden tildar hasta corregirlas.
      · Para corregir los datos de alguien, tocá el lápiz ✏️ de su fila. Los
        cambios quedan en el programa: la planilla no se toca.
    Tildá y destildá a quién cargar.
      · Para cargar solo una parte: en "Cargar desde … hasta …" escribí la fila,
        el DNI, el apellido o el nombre de la primera y la última persona, o
        mové los dos extremos del deslizador. Solo se carga lo que queda a la vista.
      · "Buscar en cualquier columna" achica el listado mientras escribís.

3.  Pestaña "Opciones": la dirección del SiGeS, y qué hacer con lo que la planilla
    no trae (vivienda, transporte, WhatsApp). Se guarda para la próxima vez.

4.  Pestaña "Cargar": tocá Empezar. Se abre una ventana de navegador APARTE (Chrome,
    si está), en el menú de ABC: iniciá sesión VOS ahí, aunque ya tengas el SiGeS
    abierto en tu Chrome de siempre, entrá al SiGeS y abrí el listado del trayecto. Desde ahí, por cada persona, el bot busca el DNI y
    completa. Vos revisás, completás lo marcado en amarillo, apretás "Guardar
    estudiante", hacés la encuesta, y tocás "Siguiente".
    Si hace falta frenar, "Cancelar la carga": no hay que cerrar el programa.
    El navegador queda ABIERTO al terminar o al cancelar: la sesión se inicia una
    sola vez, y podés corregir a mano o cargar a los que faltaron. Se cierra
    cuando cerrás su ventana (o el programa). "Abrir el navegador" lo abre sin
    cargar a nadie, por ejemplo para iniciar sesión antes.

LO QUE EL BOT NO HACE NUNCA

  · Iniciar sesión, ni ver tu contraseña.
  · Guardar, contestar la encuesta, o "Generar matrícula inicial".
  · Pisar los datos de alguien que ya estaba cargado: te avisa qué difiere.
  · Tocar salud, discapacidad o restricción judicial.

Para practicar sin tocar el sistema real: en Opciones, tildá "Ensayo con el
simulador".
"""


# Lo que se puede corregir de una fila desde la aplicación (si la planilla trae esa columna).
CAMPOS_EDITABLES = [
    ('dni', 'DNI'), ('apellidos', 'Apellido/s'), ('nombres', 'Nombre/s'), ('genero', 'Género'),
    ('fecha_nacimiento', 'Fecha de nacimiento'), ('nacionalidad', 'Nacionalidad'),
    ('provincia', 'Provincia de nacimiento'), ('domicilio', 'Domicilio'), ('localidad', 'Localidad'),
    ('celular', 'Celular'), ('edu_primario', 'Primario'), ('edu_secundario', 'Secundario'),
    ('edu_terciario', 'Terciario'), ('edu_universitario', 'Universitario'),
]


def sin_tildes(texto):
    """Para buscar: 'Pérez' encuentra 'perez' y al revés."""
    texto = unicodedata.normalize('NFD', str(texto).lower())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


class RangoDoble(tk.Canvas):
    """Un deslizador con dos extremos: elige de qué fila a qué fila del listado.

    Trabaja con posiciones 0..n-1 (el orden del listado). Cuando la persona
    mueve un extremo, llama a `al_cambiar(desde, hasta)`."""

    RADIO = 9

    def __init__(self, padre, al_cambiar, **kw):
        super().__init__(padre, height=2 * self.RADIO + 8, highlightthickness=0, **kw)
        self.al_cambiar = al_cambiar
        self.n, self.a, self.b = 0, 0, 0
        self._arrastrando = None
        self.bind('<Configure>', lambda e: self._dibujar())
        self.bind('<Button-1>', self._tocar)
        self.bind('<B1-Motion>', self._mover)
        self.bind('<ButtonRelease-1>', lambda e: setattr(self, '_arrastrando', None))

    def configurar(self, n):
        self.n, self.a, self.b = n, 0, max(n - 1, 0)
        self._dibujar()

    def poner(self, a, b):
        self.a, self.b = sorted((a, b))
        self._dibujar()

    def _x(self, i):
        ancho = self.winfo_width() - 2 * self.RADIO - 2
        return self.RADIO + 1 + (ancho * i / (self.n - 1) if self.n > 1 else 0)

    def _i(self, x):
        if self.n <= 1:
            return 0
        ancho = self.winfo_width() - 2 * self.RADIO - 2
        return max(0, min(self.n - 1, round((x - self.RADIO - 1) * (self.n - 1) / max(ancho, 1))))

    def _dibujar(self):
        self.delete('all')
        y = self.RADIO + 4
        self.create_line(self._x(0), y, self._x(max(self.n - 1, 0)), y, fill='#ccc', width=4)
        if not self.n:
            return
        self.create_line(self._x(self.a), y, self._x(self.b), y, fill='#2e86c1', width=6)
        for i in (self.a, self.b):
            x = self._x(i)
            self.create_oval(x - self.RADIO, y - self.RADIO, x + self.RADIO, y + self.RADIO,
                             fill='white', outline='#2e86c1', width=3)

    def _tocar(self, evento):
        if not self.n:
            return
        i = self._i(evento.x)
        self._arrastrando = 'a' if abs(i - self.a) <= abs(i - self.b) and i <= self.b else 'b'
        self._mover(evento)

    def _mover(self, evento):
        if not self._arrastrando:
            return
        i = self._i(evento.x)
        if self._arrastrando == 'a':
            self.a = min(i, self.b)
        else:
            self.b = max(i, self.a)
        self._dibujar()
        self.al_cambiar(self.a, self.b)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bot de carga al SiGeS')
        self.geometry('980x720')
        self.option_add('*Font', FUENTE)
        estilo = ttk.Style(self)
        estilo.configure('.', font=FUENTE)
        estilo.configure('Treeview', rowheight=28)
        estilo.configure('Grande.TButton', font=('Segoe UI', 12, 'bold'), padding=8)

        self.ajustes = motor.cargar_ajustes()
        self.filas = []          # (número de fila, datos, problemas, amarilla)
        self.origen = []         # por fila, su diccionario de la planilla (lo que se edita)
        self.marcadas = set()    # índices de self.filas
        self.textos = []         # por fila, todo su contenido junto y sin tildes, para buscar
        self.visibles = []       # índices de self.filas que pasan el rango y la búsqueda
        self.rango = (0, 0)
        self.cola = queue.Queue()
        self.corriendo = False
        self.cancelar = threading.Event()
        self.ui_motor = UiDesdeHilo(self.cola, self.cancelar)
        self.sesion = motor.Sesion(self.ui_motor, lambda abierto: self.cola.put(('navegador', abierto)))

        self.pestanas = ttk.Notebook(self)
        self.pestanas.pack(fill='both', expand=True, padx=8, pady=8)
        self._pestana_tutorial()
        self._pestana_planilla()
        self._pestana_opciones()
        self._pestana_cargar()
        self.after(100, self._atender_cola)
        self.protocol('WM_DELETE_WINDOW', self._cerrar)

    # ─────────────────────────── 1. Cómo se usa ─────────────────────────
    def _pestana_tutorial(self):
        marco = ttk.Frame(self.pestanas, padding=16)
        self.pestanas.add(marco, text='👋 Cómo se usa')
        texto = tk.Text(marco, wrap='word', relief='flat', background=self.cget('background'))
        texto.insert('1.0', TUTORIAL)
        texto.configure(state='disabled')
        texto.pack(fill='both', expand=True)
        ttk.Button(marco, text='Empezar: elegir la planilla →', style='Grande.TButton',
                   command=lambda: self.pestanas.select(1)).pack(pady=8)

    # ─────────────────────────── 2. Planilla ────────────────────────────
    def _pestana_planilla(self):
        marco = ttk.Frame(self.pestanas, padding=12)
        self.pestanas.add(marco, text='📂 Planilla')

        arriba = ttk.Frame(marco)
        arriba.pack(fill='x')
        ttk.Button(arriba, text='Elegir planilla (.xlsx o .csv)…', command=self._elegir).pack(side='left')
        self.lbl_archivo = ttk.Label(arriba, text='Todavía no elegiste ninguna.')
        self.lbl_archivo.pack(side='left', padx=10)

        filtro = ttk.Frame(marco)
        filtro.pack(fill='x', pady=(8, 0))
        ttk.Label(filtro, text='Solo inscriptos desde').pack(side='left')
        self.desde = ttk.Entry(filtro, width=11)
        self.desde.pack(side='left', padx=4)
        ttk.Label(filtro, text='hasta').pack(side='left')
        self.hasta = ttk.Entry(filtro, width=11)
        self.hasta.pack(side='left', padx=4)
        ttk.Label(filtro, text='(dd/mm/aaaa, opcional)').pack(side='left')
        ttk.Button(filtro, text='Aplicar', command=self._mostrar).pack(side='left', padx=8)

        # El rango: los inscriptos vienen en orden, así que alcanza con decir el
        # primero y el último. Cada extremo se puede escribir (fila, DNI, apellido,
        # nombre, lo que sea de cualquier columna) o mover en el deslizador.
        rango = ttk.Frame(marco)
        rango.pack(fill='x', pady=(8, 0))
        ttk.Label(rango, text='Cargar desde').pack(side='left')
        self.rango_desde = ttk.Entry(rango, width=18)
        self.rango_desde.pack(side='left', padx=4)
        ttk.Label(rango, text='hasta').pack(side='left')
        self.rango_hasta = ttk.Entry(rango, width=18)
        self.rango_hasta.pack(side='left', padx=4)
        ttk.Label(rango, text='(número de fila, DNI, apellido o nombre)', foreground='#555').pack(side='left')
        for entrada in (self.rango_desde, self.rango_hasta):
            entrada.bind('<KeyRelease>', lambda e: self._rango_escrito())
        ttk.Button(rango, text='Todos', command=self._rango_todo).pack(side='left', padx=8)
        self.deslizador = RangoDoble(marco, self._rango_movido)
        self.deslizador.pack(fill='x', pady=(4, 0))
        self.lbl_rango = ttk.Label(marco, text='', foreground='#555')
        self.lbl_rango.pack(anchor='w')

        buscar = ttk.Frame(marco)
        buscar.pack(fill='x', pady=(4, 0))
        ttk.Label(buscar, text='🔎 Buscar en cualquier columna:').pack(side='left')
        self.buscar = ttk.Entry(buscar, width=30)
        self.buscar.pack(side='left', padx=4)
        self.buscar.bind('<KeyRelease>', lambda e: self._pintar())

        self.lbl_columnas = ttk.Label(marco, text='', foreground='#555', wraplength=920, justify='left')
        self.lbl_columnas.pack(fill='x', pady=6)

        tabla = ttk.Frame(marco)
        tabla.pack(fill='both', expand=True)
        self.arbol = ttk.Treeview(tabla, columns=('marca', 'fila', 'quien', 'dni', 'estado', 'editar'),
                                  show='headings', selectmode='none')
        for col, titulo, ancho in (('marca', '✔', 40), ('fila', 'Fila', 50), ('quien', 'Apellido y nombre', 260),
                                   ('dni', 'DNI', 100), ('estado', 'Estado', 420), ('editar', 'Editar', 60)):
            self.arbol.heading(col, text=titulo)
            self.arbol.column(col, width=ancho, anchor='center' if col in ('marca', 'fila', 'editar') else 'w')
        self.arbol.tag_configure('amarilla', background='#fff3b0')
        self.arbol.tag_configure('problema', background='#f8d7da')
        barra = ttk.Scrollbar(tabla, orient='vertical', command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side='left', fill='both', expand=True)
        barra.pack(side='right', fill='y')
        self.arbol.bind('<Button-1>', self._tocar_fila)

        abajo = ttk.Frame(marco)
        abajo.pack(fill='x', pady=(8, 0))
        ttk.Button(abajo, text='Tildar todos los que no son amarillos', command=self._tildar_listos).pack(side='left')
        ttk.Button(abajo, text='Destildar todos', command=self._destildar).pack(side='left', padx=6)
        self.lbl_cuenta = ttk.Label(abajo, text='')
        self.lbl_cuenta.pack(side='right')

    def _elegir(self):
        ruta = filedialog.askopenfilename(title='La planilla de inscripción',
                                          filetypes=[('Planillas', '*.xlsx *.csv'), ('Todos', '*.*')])
        if not ruta:
            return
        try:
            columnas, crudas, faltan = planilla_google.todas(ruta)
        except Exception as e:                          # noqa: BLE001
            messagebox.showerror('No se pudo leer', f'No pude leer la planilla:\n\n{e}')
            return
        self.ruta, self.crudas = ruta, crudas
        self.lbl_archivo.configure(text=ruta.replace('\\', '/').split('/')[-1])
        reconocidas = [f'{clave} ← "{enc[:30]}"' for enc, clave in columnas if clave]
        texto = 'Columnas reconocidas: ' + ' · '.join(reconocidas)
        if faltan:
            texto += f'\n⚠️ No encontré: {", ".join(faltan)}. Esas quedan vacías para todos.'
        if ruta.lower().endswith('.csv'):
            texto += '\nℹ️ Es un .csv: no trae colores, así que no se ven las filas amarillas.'
        self.lbl_columnas.configure(text=texto)
        self._mostrar()

    def _mostrar(self):
        if not getattr(self, 'crudas', None):
            return
        try:
            desde = planilla_google.a_fecha(self.desde.get()) if self.desde.get().strip() else None
            hasta = planilla_google.a_fecha(self.hasta.get()) if self.hasta.get().strip() else None
        except Exception:                               # noqa: BLE001
            desde = hasta = None
        self.filas, self.marcadas, self.textos, self.origen = [], set(), [], []
        for cruda in self.crudas:
            f = cruda.get('_fecha')
            if (desde or hasta) and (f is None or (desde and f < desde) or (hasta and f > hasta)):
                continue
            self.filas.append(None)
            self.textos.append('')
            self.origen.append(cruda)
            self._interpretar(len(self.filas) - 1)
        self.deslizador.configurar(len(self.filas))
        self._rango_todo()

    def _interpretar(self, i):
        """Vuelve a leer la fila i de su diccionario de la planilla (al importar o al editarla)."""
        cruda = self.origen[i]
        datos, problemas = normalizar.normalizar_fila(cruda)
        self.filas[i] = (cruda['_fila'], datos, problemas, cruda['_amarilla'])
        if not problemas and not cruda['_amarilla']:
            self.marcadas.add(i)
        elif problemas:
            self.marcadas.discard(i)
        self.textos[i] = sin_tildes(' '.join(str(v) for k, v in cruda.items() if not k.startswith('_')))

    def _pintar(self):
        """Vuelve a llenar la tabla con las filas que pasan el rango y la búsqueda."""
        a, b = self.rango
        busca = sin_tildes(self.buscar.get().strip())
        self.visibles = [i for i in range(a, min(b, len(self.filas) - 1) + 1)
                         if not busca or busca in self.textos[i] or busca == str(self.filas[i][0])]
        self.arbol.delete(*self.arbol.get_children())
        for i in self.visibles:
            numero, datos, problemas, amarilla = self.filas[i]
            if problemas:
                estado, tag = '⛔ ' + '; '.join(problemas), 'problema'
            elif amarilla:
                estado, tag = '🟨 Pintada de amarillo: no se carga (tildala si querés)', 'amarilla'
            else:
                estado, tag = '✅ Lista', ''
            if self.origen[i].get('_editada'):
                estado = '✏️ Editada · ' + estado
            quien = f'{datos["apellidos"]}, {datos["nombres"]}'.strip(', ')
            self.arbol.insert('', 'end', iid=str(i), tags=(tag,),
                              values=('☑' if i in self.marcadas else '☐', numero, quien, datos['dni'] or '', estado, '✏️'))
        if self.filas:
            self.lbl_rango.configure(text=f'De {self._describir(a)}  a  {self._describir(b)}  '
                                          f'({b - a + 1} de {len(self.filas)} filas)')
        else:
            self.lbl_rango.configure(text='')
        self._contar()

    def _describir(self, i):
        numero, datos, _, _ = self.filas[i]
        return f'fila {numero} ({datos["apellidos"]}, {datos["nombres"]})'.replace(' (, )', '')

    def _buscar_fila(self, texto, ultima=False):
        """La posición de la fila que corresponde a lo escrito: un número de fila
        exacto, o si no la primera (o la última) que lo contiene en alguna columna."""
        texto = sin_tildes(texto.strip())
        if not texto:
            return None
        if texto.isdigit():
            for i, (numero, *_) in enumerate(self.filas):
                if str(numero) == texto:
                    return i
        cuales = [i for i, t in enumerate(self.textos) if texto in t]
        return (cuales[-1] if ultima else cuales[0]) if cuales else None

    def _rango_escrito(self):
        if not self.filas:
            return
        a = self._buscar_fila(self.rango_desde.get())
        b = self._buscar_fila(self.rango_hasta.get(), ultima=True)
        a = 0 if a is None else a
        b = len(self.filas) - 1 if b is None else b
        self.rango = tuple(sorted((a, b)))
        self.deslizador.poner(*self.rango)
        self._pintar()

    def _rango_movido(self, a, b):
        self.rango = (a, b)
        for entrada, i in ((self.rango_desde, a), (self.rango_hasta, b)):
            entrada.delete(0, 'end')
            entrada.insert(0, str(self.filas[i][0]))
        self._pintar()

    def _rango_todo(self):
        for entrada in (self.rango_desde, self.rango_hasta):
            entrada.delete(0, 'end')
        self.rango = (0, max(len(self.filas) - 1, 0))
        self.deslizador.poner(*self.rango)
        self._pintar()

    def _tocar_fila(self, evento):
        iid = self.arbol.identify_row(evento.y)
        if not iid:
            return
        i = int(iid)
        if self.arbol.identify_column(evento.x) == '#6':
            self._editar(i)
            return
        if self.filas[i][2]:
            if messagebox.askyesno('No se puede cargar', 'Esta fila tiene un problema en los datos:\n\n'
                                   + '\n'.join(self.filas[i][2]) + '\n\n¿La corregís acá?'):
                self._editar(i)
            return
        self.marcadas ^= {i}
        self.arbol.set(iid, 'marca', '☑' if i in self.marcadas else '☐')
        self._contar()

    def _editar(self, i):
        """Una ventana para corregir los datos de la fila i. Muestra en vivo cómo se
        van a cargar, y antes de guardar pide confirmar cada cambio. La planilla
        no se toca: los cambios quedan en el programa hasta que se importe de nuevo."""
        cruda = self.origen[i]
        campos = [(clave, rotulo) for clave, rotulo in CAMPOS_EDITABLES if clave in cruda]
        ventana = tk.Toplevel(self)
        ventana.title(f'Editar la fila {cruda["_fila"]}')
        ventana.transient(self)
        ventana.grab_set()
        marco = ttk.Frame(ventana, padding=14)
        marco.pack(fill='both', expand=True)

        valores = {}
        for fila, (clave, rotulo) in enumerate(campos):
            ttk.Label(marco, text=rotulo + ':').grid(row=fila, column=0, sticky='w', pady=2)
            valores[clave] = tk.StringVar(value=cruda.get(clave) or '')
            ttk.Entry(marco, textvariable=valores[clave], width=48).grid(row=fila, column=1, sticky='we', pady=2, padx=6)
        vista = ttk.Label(marco, wraplength=560, justify='left')
        vista.grid(row=len(campos), column=0, columnspan=2, sticky='w', pady=(10, 0))

        def nueva():
            return {**cruda, **{clave: v.get().strip() for clave, v in valores.items()}}

        def mostrar(*_):
            datos, problemas = normalizar.normalizar_fila(nueva())
            texto = (f'Se carga así →  Calle: {datos["calle"] or "—"}  ·  Altura: {datos["altura"]}  ·  '
                     f'Entre calles: {datos["entre_calles"] or "—"}')
            texto += ('\n⛔ ' + '; '.join(problemas)) if problemas else '\n✅ Sin problemas: se puede cargar.'
            vista.configure(text=texto, foreground='#a12622' if problemas else '#1f5f8b')

        for v in valores.values():
            v.trace_add('write', mostrar)
        mostrar()

        def guardar():
            cambios = [(rotulo, cruda.get(clave) or '', valores[clave].get().strip())
                       for clave, rotulo in campos if (cruda.get(clave) or '') != valores[clave].get().strip()]
            if not cambios:
                ventana.destroy()
                return
            detalle = '\n'.join(f'{rotulo}: "{antes}" → "{despues}"' for rotulo, antes, despues in cambios)
            if not messagebox.askyesno('Confirmar los cambios', f'Fila {cruda["_fila"]}:\n\n{detalle}\n\n'
                                       'Los cambios quedan en el programa (la planilla no se toca). ¿Los guardo?',
                                       parent=ventana):
                return
            cruda.update(nueva())
            cruda['_editada'] = True
            self._interpretar(i)
            ventana.destroy()
            self._pintar()

        botones = ttk.Frame(marco)
        botones.grid(row=len(campos) + 1, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(botones, text='Cancelar', command=ventana.destroy).pack(side='right')
        ttk.Button(botones, text='Guardar cambios', command=guardar).pack(side='right', padx=6)

    def _tildar_listos(self):
        for i in self.visibles:
            _, _, problemas, amarilla = self.filas[i]
            if not problemas and not amarilla:
                self.marcadas.add(i)
                self.arbol.set(str(i), 'marca', '☑')
        self._contar()

    def _destildar(self):
        for i in self.visibles:
            self.arbol.set(str(i), 'marca', '☐')
        self.marcadas.clear()
        self._contar()

    def _contar(self):
        self.lbl_cuenta.configure(text=f'Se van a cargar: {len(self.elegidas())} de {len(self.visibles)} a la vista')

    def elegidas(self):
        """Las tildadas que además están a la vista: fuera del rango o de la búsqueda no se cargan."""
        return [i for i in self.visibles if i in self.marcadas]

    # ─────────────────────────── 3. Opciones ────────────────────────────
    def _pestana_opciones(self):
        marco = ttk.Frame(self.pestanas, padding=12)
        self.pestanas.add(marco, text='⚙️ Opciones')
        cfg = self.ajustes['config']
        self.v = {}

        general = ttk.LabelFrame(marco, text='General', padding=10)
        general.pack(fill='x')
        ttk.Label(general, text='Dirección del SiGeS:').grid(row=0, column=0, sticky='w')
        self.v['url'] = tk.StringVar(value=self.ajustes['url'])
        ttk.Entry(general, textvariable=self.v['url'], width=70).grid(row=0, column=1, columnspan=3, sticky='we', pady=2)
        for fila, (clave, texto) in enumerate((
                ('demo', 'Modo demo: después de cada persona, preguntar si quedó bien cargada'),
                ('lento', 'Despacio, para que se vea cada campo llenarse'),
                ('simulador', 'Ensayo con el simulador (no toca el SiGeS real)')), start=1):
            self.v[clave] = tk.BooleanVar(value=self.ajustes[clave])
            ttk.Checkbutton(general, text=texto, variable=self.v[clave]).grid(row=fila, column=0, columnspan=4, sticky='w')

        lugar = ttk.LabelFrame(marco, text='Dirección del alumno', padding=10)
        lugar.pack(fill='x', pady=8)
        for col, (clave, texto) in enumerate((('distrito', 'Distrito'), ('localidad', 'Localidad'),
                                                  ('codigo_postal', 'Código postal'))):
            ttk.Label(lugar, text=texto + ':').grid(row=0, column=col * 2, sticky='w')
            self.v[clave] = tk.StringVar(value=cfg[clave])
            ttk.Entry(lugar, textvariable=self.v[clave], width=22).grid(row=0, column=col * 2 + 1, padx=6)

        self.v['valores_fijos'] = tk.BooleanVar(value=cfg['valores_fijos'])
        fijos = ttk.LabelFrame(marco, padding=10, labelwidget=ttk.Checkbutton(
            marco, text='Completar con valores fijos lo que la planilla no trae (provisorio)',
            variable=self.v['valores_fijos']))
        fijos.pack(fill='x')
        ttk.Label(fijos, foreground='#8a5a00', wraplength=900, text=(
            'Provisorio, hasta que estas preguntas estén en el formulario de inscripción. Cada persona '
            'cargada así queda anotada en el resumen. Si está destildado, el bot deja estas secciones '
            'marcadas en amarillo para completarlas a mano.')).grid(row=0, column=0, columnspan=6, sticky='w', pady=(0, 6))

        def combo(fila, col, clave, texto, opciones):
            ttk.Label(fijos, text=texto).grid(row=fila, column=col, sticky='w')
            self.v[clave] = tk.StringVar(value=cfg[clave])
            ttk.Combobox(fijos, textvariable=self.v[clave], values=opciones, state='readonly', width=20).grid(
                row=fila, column=col + 1, sticky='w', padx=6, pady=2)

        def numero(fila, col, clave, texto):
            ttk.Label(fijos, text=texto).grid(row=fila, column=col, sticky='w')
            self.v[clave] = tk.IntVar(value=cfg[clave])
            ttk.Spinbox(fijos, from_=0, to=20, textvariable=self.v[clave], width=5).grid(
                row=fila, column=col + 1, sticky='w', padx=6, pady=2)

        def si_no(fila, col, clave, texto):
            self.v[clave] = tk.BooleanVar(value=cfg[clave])
            ttk.Checkbutton(fijos, text=texto, variable=self.v[clave]).grid(row=fila, column=col, columnspan=2, sticky='w')

        combo(1, 0, 'transporte', 'Transporte:', siges_real.TRANSPORTES)
        self.v['whatsapp_txt'] = tk.StringVar(value='Tiene WhatsApp' if cfg['whatsapp'] else 'No tiene WhatsApp')
        ttk.Label(fijos, text='WhatsApp:').grid(row=1, column=2, sticky='w')
        ttk.Combobox(fijos, textvariable=self.v['whatsapp_txt'], values=['Tiene WhatsApp', 'No tiene WhatsApp'],
                     state='readonly', width=18).grid(row=1, column=3, sticky='w', padx=6)
        combo(2, 0, 'vivienda_zona', 'Vivienda:', siges_real.ZONAS)
        numero(3, 0, 'vivienda_personas', 'Personas en el hogar:')
        numero(3, 2, 'vivienda_adultos', 'Adultos:')
        numero(3, 4, 'vivienda_ninios', 'Niños/as:')
        si_no(4, 0, 'vivienda_hijos', 'Tiene hijos/as a cargo')
        si_no(4, 2, 'lengua_extranjera', 'Habla lengua extranjera')
        si_no(5, 0, 'lengua_indigena', 'Habla lengua indígena')
        si_no(5, 2, 'pueblos_originarios', 'Pertenece a pueblos originarios')
        ttk.Label(fijos, text='Educación, solo si la planilla no la trae:', foreground='#555').grid(
            row=6, column=0, columnspan=4, sticky='w', pady=(8, 0))
        combo(7, 0, 'educacion_nivel', 'Nivel máximo:', siges_real.NIVELES)
        si_no(7, 2, 'educacion_completo', 'Completo')
        si_no(7, 4, 'educacion_cursando', 'Cursando')

        abajo = ttk.Frame(marco)
        abajo.pack(fill='x', pady=10)
        self.btn_probar = ttk.Button(abajo, text='🩺 Probar esta compu', command=self._probar)
        self.btn_probar.pack(side='left')
        self.lbl_probar = ttk.Label(abajo, text='', foreground='#555')
        self.lbl_probar.pack(side='left', padx=10)
        ttk.Button(abajo, text='Guardar opciones', command=self._guardar_ajustes).pack(side='right')

    def _probar(self):
        """La autoprueba, en otro hilo para que la ventana no se congele."""
        if self.corriendo:
            return
        self.corriendo = True
        self.btn_probar.configure(state='disabled')
        self.lbl_probar.configure(text='Probando, tarda medio minuto… (no se toca nada real)')
        threading.Thread(target=lambda: self.cola.put(('aviso', *autoprueba())), daemon=True).start()

    def _leer_opciones(self):
        self.ajustes['url'] = self.v['url'].get().strip()
        for clave in ('demo', 'lento', 'simulador'):
            self.ajustes[clave] = self.v[clave].get()
        cfg = self.ajustes['config']
        for clave in siges_real.CONFIG_INICIAL:
            if clave in self.v:
                try:
                    cfg[clave] = self.v[clave].get()
                except tk.TclError:                     # un número borrado: queda el anterior
                    pass
        cfg['whatsapp'] = self.v['whatsapp_txt'].get() == 'Tiene WhatsApp'

    def _guardar_ajustes(self, avisar=True):
        self._leer_opciones()
        try:
            motor.guardar_ajustes(self.ajustes)
            if avisar:
                messagebox.showinfo('Opciones', 'Guardadas. Se usan desde ahora y la próxima vez que abras el programa.')
        except Exception as e:                          # noqa: BLE001
            messagebox.showwarning('Opciones', f'Se usan ahora, pero no se pudieron guardar:\n{e}')

    # ─────────────────────────── 4. Cargar ──────────────────────────────
    def _pestana_cargar(self):
        marco = ttk.Frame(self.pestanas, padding=12)
        self.pestanas.add(marco, text='▶️ Cargar')
        botonera = ttk.Frame(marco)
        botonera.pack(anchor='w')
        self.btn_empezar = ttk.Button(botonera, text='Empezar', style='Grande.TButton', command=self._empezar)
        self.btn_empezar.pack(side='left')
        self.btn_cancelar = ttk.Button(botonera, text='⏹ Cancelar la carga', command=self._cancelar, state='disabled')
        self.btn_cancelar.pack(side='left', padx=10)
        self.btn_navegador = ttk.Button(botonera, text='🌐 Abrir el navegador', command=self._abrir_navegador)
        self.btn_navegador.pack(side='left')
        self.lbl_navegador = ttk.Label(botonera, text='Navegador cerrado', foreground='#555')
        self.lbl_navegador.pack(side='left', padx=10)
        self.lbl_progreso = ttk.Label(marco, text='')
        self.lbl_progreso.pack(anchor='w', pady=(8, 2))
        self.barra = ttk.Progressbar(marco, mode='determinate')
        self.barra.pack(fill='x')

        self.zona_accion = ttk.LabelFrame(marco, text='Te toca', padding=10)
        self.lbl_accion = ttk.Label(self.zona_accion, text='', wraplength=900, justify='left', font=('Segoe UI', 12))
        self.lbl_accion.pack(anchor='w')
        botones = ttk.Frame(self.zona_accion)
        botones.pack(anchor='w', pady=(8, 0))
        self.btn_accion = ttk.Button(botones, style='Grande.TButton', command=lambda: self._responder(True))
        self.btn_si = ttk.Button(botones, text='Sí, quedó bien', style='Grande.TButton', command=lambda: self._responder(True))
        self.btn_no = ttk.Button(botones, text='No, hubo un error', style='Grande.TButton', command=lambda: self._responder(False))

        self.registro = tk.Text(marco, height=18, wrap='word', state='disabled')
        for tipo, color in (('ok', '#1e8449'), ('aviso', '#9a6700'), ('mal', '#c0392b'), ('info', '#333')):
            self.registro.tag_configure(tipo, foreground=color)
        self.registro.pack(fill='both', expand=True, pady=(10, 0))

    def _empezar(self):
        if self.corriendo:
            return
        self._guardar_ajustes(avisar=False)
        elegidas = [(self.filas[i][0], self.filas[i][1]) for i in self.elegidas()]
        if not elegidas:
            messagebox.showinfo('Nadie para cargar', 'En la pestaña Planilla no hay ninguna persona tildada.')
            return
        ajustes = dict(self.ajustes)
        if not ajustes['simulador']:
            if not ajustes['url'].startswith('http'):
                messagebox.showerror('Falta la dirección', 'En Opciones, poné la dirección del SiGeS.')
                return
            if not messagebox.askyesno('Sistema REAL del Ministerio',
                                       f'Esto va contra el SiGeS REAL, con {len(elegidas)} persona(s).\n\n'
                                       'El bot completa y para: guardás vos, hacés la encuesta vos.\n\n¿Seguimos?'):
                return
        self.corriendo = True
        self.cancelar.clear()
        self.btn_empezar.configure(state='disabled')
        self.btn_cancelar.configure(state='normal')
        self.barra.configure(maximum=len(elegidas), value=0)
        self.lbl_progreso.configure(text=f'0 de {len(elegidas)}')
        self.registro.configure(state='normal')
        self.registro.delete('1.0', 'end')
        self.registro.configure(state='disabled')
        # El navegador queda abierto al terminar: la próxima carga usa la misma sesión.
        self.sesion.cargar(elegidas, ajustes, lambda resultados: self.cola.put(('fin',)))

    def _abrir_navegador(self):
        """Abre el navegador sin cargar a nadie: para iniciar sesión antes, o para
        corregir a mano. Queda abierto hasta que se cierra su ventana."""
        if self.sesion.abierta():
            return
        self._guardar_ajustes(avisar=False)
        self.lbl_navegador.configure(text='Abriendo…')
        self.btn_navegador.configure(state='disabled')
        self.sesion.abrir(self.ajustes)

    # El hilo del motor no puede tocar la ventana: deja pedidos en la cola, y
    # acá (en el hilo de la ventana) se atienden cada 100 ms.
    def _atender_cola(self):
        try:
            while True:
                pedido = self.cola.get_nowait()
                tipo = pedido[0]
                if tipo == 'contar':
                    self.registro.configure(state='normal')
                    self.registro.insert('end', pedido[1] + '\n', pedido[2])
                    self.registro.see('end')
                    self.registro.configure(state='disabled')
                elif tipo == 'progreso':
                    hechos, total, quien = pedido[1:]
                    self.barra.configure(maximum=total, value=hechos)
                    self.lbl_progreso.configure(text=f'{hechos} de {total}' + (f'  ·  ahora: {quien}' if quien else ''))
                elif tipo in ('esperar', 'preguntar'):
                    self._pedido = pedido
                    self.lbl_accion.configure(text=pedido[1])
                    self.zona_accion.pack(fill='x', pady=(10, 0), before=self.registro)
                    for b in (self.btn_accion, self.btn_si, self.btn_no):
                        b.pack_forget()
                    if tipo == 'esperar':
                        self.btn_accion.configure(text=pedido[2])
                        self.btn_accion.pack(side='left')
                    else:
                        self.btn_si.pack(side='left')
                        self.btn_no.pack(side='left', padx=8)
                    self.bell()
                    self.lift()
                elif tipo == 'fin':
                    self.corriendo = False
                    self.btn_empezar.configure(state='normal')
                    self.btn_cancelar.configure(state='disabled')
                    self.zona_accion.pack_forget()
                    self._pedido = None
                    if self.cancelar.is_set():          # cancelada: no queda "1 de 11" colgado
                        self.barra.configure(value=0)
                        self.lbl_progreso.configure(text='Cancelada. Lo hecho está en el registro de abajo.')
                elif tipo == 'navegador':
                    abierto = pedido[1]
                    self.lbl_navegador.configure(text='Navegador abierto: queda así hasta que lo cierres'
                                                 if abierto else 'Navegador cerrado')
                    self.btn_navegador.configure(state='disabled' if abierto else 'normal')
                elif tipo == 'aviso':
                    ok, mensaje = pedido[1:]
                    self.corriendo = False
                    self.btn_probar.configure(state='normal')
                    self.lbl_probar.configure(text='')
                    (messagebox.showinfo if ok else messagebox.showerror)('Prueba del bot', mensaje)
        except queue.Empty:
            pass
        self.after(100, self._atender_cola)

    def _responder(self, valor):
        pedido = getattr(self, '_pedido', None)
        if not pedido:
            return
        self._pedido = None
        self.zona_accion.pack_forget()
        respuesta, listo = pedido[-2], pedido[-1]
        respuesta.append(valor)
        listo.set()

    def _cancelar(self):
        """Frena la carga sin cerrar el programa. Lo que ya se escribió en el
        formulario abierto queda ahí: no se guarda nada solo."""
        if not self.corriendo or self.cancelar.is_set():
            return
        if not messagebox.askyesno('Cancelar la carga',
                                   'El bot deja de cargar. El navegador queda abierto, con lo que '
                                   'haya en pantalla, para que lo termines o corrijas a mano.\n\n'
                                   'Lo que ya guardaste en el SiGeS queda guardado.\n\n¿Cancelar?'):
            return
        self.cancelar.set()
        self.btn_cancelar.configure(state='disabled')
        self._responder(None)                           # si estaba esperando un botón, lo suelta

    def _cerrar(self):
        if self.corriendo and not messagebox.askyesno('Salir', 'Hay una carga en curso. ¿Cerrar igual?'):
            return
        self.cancelar.set()
        self._responder(None)
        self.sesion.cerrar(esperar_hasta=3)
        self.destroy()


class UiDesdeHilo:
    """Lo que ve el motor: cada método deja un pedido en la cola y, si hace falta
    una respuesta de la persona, espera a que la ventana la conteste."""

    def __init__(self, cola, cancelar=None):
        self.cola = cola
        self.cancelar = cancelar or threading.Event()

    def cancelado(self):
        return self.cancelar.is_set()

    def contar(self, texto, tipo='info'):
        self.cola.put(('contar', texto, tipo))

    def progreso(self, hechos, total, quien):
        self.cola.put(('progreso', hechos, total, quien))

    def _pedir(self, *pedido):
        respuesta, listo = [], threading.Event()
        self.cola.put((*pedido, respuesta, listo))
        listo.wait()
        return respuesta[0]

    def esperar(self, mensaje, boton):
        self._pedir('esperar', mensaje, boton)

    def preguntar(self, pregunta):
        return self._pedir('preguntar', pregunta)


def autoprueba(navegador=None):
    """¿Anda el bot en esta compu? Carga los datos de ejemplo en el simulador, sin
    mostrar el navegador, y no toca nada real. Devuelve (ok, mensaje).

    Lo usan el botón "Probar esta compu" de Opciones y `Bot-SiGeS.exe --autoprueba`.
    `navegador` ('chrome', 'msedge' o 'chromium') fuerza uno, para probar cada uno."""
    import pathlib
    ejemplo = str(pathlib.Path(__file__).parent / 'datos_ejemplo.csv')
    _, filas, _ = planilla_google.todas(ejemplo)
    personas = []
    for f in filas:
        datos, problemas = normalizar.normalizar_fila(f)
        if not problemas:
            personas.append((f['_fila'], datos))

    class Callado:
        usado = '?'
        def contar(self, texto, tipo='info'):
            if texto.startswith('Navegador: '):
                self.usado = texto.removeprefix('Navegador: ')
        def progreso(self, hechos, total, quien): pass
        def esperar(self, mensaje, boton): pass
        def preguntar(self, pregunta): return True

    ui = Callado()
    ajustes = dict(motor.cargar_ajustes(), simulador=True, demo=False, lento=False,
                   sin_ventana=True, navegador=navegador)
    try:
        resultados = motor.correr(personas, ajustes, ui)
    except Exception as e:                              # noqa: BLE001
        return False, f'❌ El bot NO anda en esta compu.\n\n{e}'
    bien = sum(r['resultado'] == 'completado' for r in resultados)
    if resultados and bien == len(resultados):
        return True, (f'✅ El bot anda en esta compu.\n\nUsó {ui.usado} y cargó las {bien} personas '
                      'de prueba en el simulador. No se tocó nada real.')
    return False, (f'⚠️ Se abrió {ui.usado}, pero solo cargó {bien} de {len(resultados)} personas de '
                   'prueba. Mirá el resumen en la carpeta resultados.')


if __name__ == '__main__':
    import sys
    if '--autoprueba' in sys.argv:
        # --navegador=chrome|msedge|chromium prueba uno solo; --callado no muestra la ventanita.
        forzado = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--navegador=')), None)
        ok, mensaje = autoprueba(forzado)
        motor.RESULTADOS.mkdir(exist_ok=True)
        (motor.RESULTADOS / 'autoprueba.txt').write_text(mensaje, encoding='utf-8')
        if '--callado' not in sys.argv:
            raiz = tk.Tk()
            raiz.withdraw()
            (messagebox.showinfo if ok else messagebox.showerror)('Prueba del bot', mensaje)
        sys.exit(0 if ok else 1)
    try:
        # Sin esto, con la pantalla al 125% Windows estira la ventana y la letra se ve borrosa.
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:                                   # noqa: BLE001
        pass
    App().mainloop()
