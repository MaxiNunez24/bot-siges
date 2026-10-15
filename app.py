"""La aplicación de escritorio del bot: importar la planilla, elegir a quién cargar, y ver el proceso.

    python app.py                (o el .exe, que es esto mismo empaquetado)

Las decisiones las toma la preceptora, en la ventana: a quién se carga, con qué
valores se completa lo que la planilla no trae, y cuándo se sigue con la
próxima persona. El bot nunca guarda, nunca contesta la encuesta y nunca toca
"Generar matrícula inicial".
"""
import queue
import threading
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
        rojo, con el motivo, y no se pueden tildar: hay que corregir la planilla.
    Tildá y destildá a quién cargar.

3.  Pestaña "Opciones": la dirección del SiGeS, y qué hacer con lo que la planilla
    no trae (vivienda, transporte, WhatsApp). Se guarda para la próxima vez.

4.  Pestaña "Cargar": tocá Empezar. Se abre una ventana de navegador APARTE (Chrome,
    si está): iniciá sesión VOS ahí, aunque ya tengas el SiGeS abierto en tu Chrome
    de siempre, y abrí el listado del trayecto. Desde ahí, por cada persona, el bot busca el DNI y
    completa. Vos revisás, completás lo marcado en amarillo, apretás "Guardar
    estudiante", hacés la encuesta, y tocás "Siguiente".

LO QUE EL BOT NO HACE NUNCA

  · Iniciar sesión, ni ver tu contraseña.
  · Guardar, contestar la encuesta, o "Generar matrícula inicial".
  · Pisar los datos de alguien que ya estaba cargado: te avisa qué difiere.
  · Tocar salud, discapacidad o restricción judicial.

Para practicar sin tocar el sistema real: en Opciones, tildá "Ensayo con el
simulador".
"""


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
        self.marcadas = set()    # índices de self.filas
        self.cola = queue.Queue()
        self.corriendo = False

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

        self.lbl_columnas = ttk.Label(marco, text='', foreground='#555', wraplength=920, justify='left')
        self.lbl_columnas.pack(fill='x', pady=6)

        tabla = ttk.Frame(marco)
        tabla.pack(fill='both', expand=True)
        self.arbol = ttk.Treeview(tabla, columns=('marca', 'fila', 'quien', 'dni', 'estado'), show='headings',
                                  selectmode='none')
        for col, titulo, ancho in (('marca', '✔', 40), ('fila', 'Fila', 50), ('quien', 'Apellido y nombre', 260),
                                   ('dni', 'DNI', 100), ('estado', 'Estado', 460)):
            self.arbol.heading(col, text=titulo)
            self.arbol.column(col, width=ancho, anchor='center' if col in ('marca', 'fila') else 'w')
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
        self.filas, self.marcadas = [], set()
        self.arbol.delete(*self.arbol.get_children())
        for cruda in self.crudas:
            f = cruda.get('_fecha')
            if (desde or hasta) and (f is None or (desde and f < desde) or (hasta and f > hasta)):
                continue
            datos, problemas = normalizar.normalizar_fila(cruda)
            i = len(self.filas)
            self.filas.append((cruda['_fila'], datos, problemas, cruda['_amarilla']))
            if problemas:
                estado, tag = '⛔ ' + '; '.join(problemas), 'problema'
            elif cruda['_amarilla']:
                estado, tag = '🟨 Pintada de amarillo: no se carga (tildala si querés)', 'amarilla'
            else:
                estado, tag = '✅ Lista', ''
                self.marcadas.add(i)
            quien = f'{datos["apellidos"]}, {datos["nombres"]}'.strip(', ')
            self.arbol.insert('', 'end', iid=str(i), tags=(tag,),
                              values=('☑' if i in self.marcadas else '☐', cruda['_fila'], quien, datos['dni'] or '', estado))
        self._contar()

    def _tocar_fila(self, evento):
        iid = self.arbol.identify_row(evento.y)
        if not iid:
            return
        i = int(iid)
        if self.filas[i][2]:
            messagebox.showinfo('No se puede cargar', 'Esta fila tiene un problema en los datos:\n\n'
                                + '\n'.join(self.filas[i][2]) + '\n\nCorregila en la planilla y volvé a importarla.')
            return
        self.marcadas ^= {i}
        self.arbol.set(iid, 'marca', '☑' if i in self.marcadas else '☐')
        self._contar()

    def _tildar_listos(self):
        for i, (_, _, problemas, amarilla) in enumerate(self.filas):
            if not problemas and not amarilla:
                self.marcadas.add(i)
                self.arbol.set(str(i), 'marca', '☑')
        self._contar()

    def _destildar(self):
        for i in list(self.marcadas):
            self.arbol.set(str(i), 'marca', '☐')
        self.marcadas.clear()
        self._contar()

    def _contar(self):
        self.lbl_cuenta.configure(text=f'Se van a cargar: {len(self.marcadas)} de {len(self.filas)}')

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
        for col, (clave, texto) in enumerate((('distrito', 'Distrito'), ('localidad', 'Localidad'))):
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
        self.btn_empezar = ttk.Button(marco, text='Empezar', style='Grande.TButton', command=self._empezar)
        self.btn_empezar.pack(anchor='w')
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
        elegidas = [(self.filas[i][0], self.filas[i][1]) for i in sorted(self.marcadas)]
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
        self.btn_empezar.configure(state='disabled')
        self.registro.configure(state='normal')
        self.registro.delete('1.0', 'end')
        self.registro.configure(state='disabled')
        threading.Thread(target=self._trabajar, args=(elegidas, ajustes), daemon=True).start()

    def _trabajar(self, elegidas, ajustes):
        try:
            motor.correr(elegidas, ajustes, UiDesdeHilo(self.cola))
        except Exception as e:                          # noqa: BLE001
            self.cola.put(('contar', f'⛔ Se cortó: {type(e).__name__}: {e}', 'mal'))
        self.cola.put(('fin',))

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
                    self.zona_accion.pack_forget()
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

    def _cerrar(self):
        if self.corriendo and not messagebox.askyesno('Salir', 'Hay una carga en curso. ¿Cerrar igual?'):
            return
        self.destroy()


class UiDesdeHilo:
    """Lo que ve el motor: cada método deja un pedido en la cola y, si hace falta
    una respuesta de la persona, espera a que la ventana la conteste."""

    def __init__(self, cola):
        self.cola = cola

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
