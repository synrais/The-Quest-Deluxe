"""The Map tab: paint a level's squares, place things, and set the level's settings.

Left: the levels and the chosen level's settings. Middle: the map (100 x 100 squares, 10 x 10
screens), scrolled with the scrollbars, the mouse wheel (Shift for sideways) or the arrow keys.
Right: the tools, the layer, and the palette of what can go in that layer.

  Paint      left button paints the chosen thing, dragging paints a line of squares
  Rectangle  drag to fill a rectangle
  Fill       fills the connected area that has the same thing in this layer
  Pick       takes the thing under the mouse into the palette (the right button does this with any tool)
  Start      where the hero arrives on this level (START)
  Shop       which shop a screen's shopkeeper runs (SHOPS)
  Peaceful   screens where people and allies leave monsters alone (PEACEFUL_SCREENS)
  Respawn    where he wakes after dying on this level (RESPAWN; the Death and respawn... button sets the rest)
  Dark       screens where nothing shows but the hero, and what his light reaches (DARK_SCREENS; an item's Light)
  Entry      a named way in to this level (ENTRIES): click a square and name it; click it again to rename or remove.
             Exits, ladders and the like link to a level's entry by name.
  Link       where the ladder, rope, stairs, hole, jump pad or exit on the clicked square leads: a square on
             another level (LINKS); an exit can lead to any level's start, and each exit of a level can lead
             somewhere of its own (without a Link an exit goes on to the next level). Put the item on the square first.
  Mouse wheel scrolls the map up and down, Shift+wheel sideways, Ctrl+wheel zooms in and out round the pointer.
  The Screens and Squares boxes show the lines between screens and round every square.
  Ctrl+Z / Ctrl+Y undo and redo.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

import pygame

from .art import Art, photo, FIELD
from .project import SIZE
from .uikit import on_wheel, tip

LAYERS = [('floor', 'Floor'), ('wall', 'Wall / door'), ('deco', 'Decoration'), ('item', 'Item'),
          ('mon', 'Creature'), ('gold', 'Gold')]
SETTINGS_3D = [('SKY_3D', '3D sky colour'), ('FOG_3D', '3D fog colour'), ('RANGE_3D', '3D range')]
TOOLS = [('paint', 'Paint'), ('rect', 'Rectangle'), ('fill', 'Fill'), ('pick', 'Pick'),
         ('start', 'Start'), ('shop', 'Shop'), ('peace', 'Peaceful'), ('dark', 'Dark'), ('respawn', 'Respawn'), ('entry', 'Entry'), ('link', 'Link')]
ZOOMS = {'Large (40)': 40, 'Medium (24)': 24, 'Small (12)': 12}


class MapTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.level = 1
        self.size = 40
        self.ox = self.oy = 1                      # the top-left square in view
        self.tool = tk.StringVar(value='paint')
        self.layer = tk.StringVar(value='floor')
        self.value = {k: 0 for k, _ in LAYERS}     # what each layer paints
        self.value['floor'] = 1
        self.gold = tk.IntVar(value=10)
        self.grid_lines = tk.BooleanVar(value=True)        # the yellow lines between 10 x 10 screens
        self.square_lines = tk.BooleanVar(value=True)      # a thin line round every square, inside each screen
        self.drag_from = None
        self.stroke: dict = {}
        self.undo_stack, self.redo_stack = [], []
        self.hover = None
        self.selected = None                        # the square last clicked (test play starts there)
        self._build()

    # ── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        left = ttk.Frame(self, padding=4)
        left.pack(side='left', fill='y')
        ttk.Label(left, text='Levels').pack(anchor='w')
        self.levels = tk.Listbox(left, height=10, width=16, exportselection=False)
        self.levels.pack(fill='x')
        self.levels.bind('<<ListboxSelect>>', lambda e: self._pick_level())
        row = ttk.Frame(left)
        row.pack(fill='x', pady=2)
        ttk.Button(row, text='Add', width=6, command=self._add_level).pack(side='left')
        ttk.Button(row, text='Remove last', command=self._remove_level).pack(side='left', padx=2)

        box = ttk.LabelFrame(left, text='Level settings', padding=4)
        box.pack(fill='x', pady=8)
        self.start_label = ttk.Label(box, text='Start: -')
        self.start_label.grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(box, text='Stories before it').grid(row=1, column=0, sticky='w')
        self.stories = ttk.Entry(box, width=10)
        self.stories.grid(row=1, column=1, sticky='w')
        ttk.Button(box, text='Pick...', width=6, command=self._pick_story).grid(row=1, column=2, padx=2)
        ttk.Label(box, text='Teleporter jump').grid(row=2, column=0, sticky='w')
        self.teleport = ttk.Entry(box, width=10)
        self.teleport.grid(row=2, column=1, sticky='w')
        self.ask_leave = tk.BooleanVar()
        ttk.Checkbutton(box, text='Ask before leaving', variable=self.ask_leave).grid(row=3, column=0, columnspan=2,
                                                                                    sticky='w')
        self.jingle = tk.BooleanVar()
        ttk.Checkbutton(box, text='Jingle when leaving', variable=self.jingle).grid(row=4, column=0, columnspan=2,
                                                                                  sticky='w')
        self.look3d = {}
        for i, (name, label) in enumerate(SETTINGS_3D):
            ttk.Label(box, text=label).grid(row=5 + i, column=0, sticky='w')
            e = ttk.Entry(box, width=10)
            e.grid(row=5 + i, column=1, sticky='w')
            self.look3d[name] = e
        ttk.Button(box, text='Death and respawn...', command=self.open_death).grid(row=8, column=0, columnspan=2, pady=(4, 0))
        ttk.Button(box, text='Apply', command=self._apply_settings).grid(row=9, column=0, columnspan=2, pady=4)
        ttk.Label(left, text='Stories: numbers from\nthe Text tab, e.g. 2, 3.\nTeleporter: dx, dy.\n'
                             '3D: EGA colours 0-15 and\nhow far the eye sees\n(empty: the default).',
                  foreground='#555').pack(anchor='w')
        ttk.Button(left, text='3D view from here...', command=self.open_3d).pack(fill='x', pady=6)
        self.preview3d = None

        right = ttk.Frame(self, padding=4)
        right.pack(side='right', fill='y')
        tools = ttk.LabelFrame(right, text='Tool', padding=4)
        tools.pack(fill='x')
        for i, (k, label) in enumerate(TOOLS):
            ttk.Radiobutton(tools, text=label, value=k, variable=self.tool).grid(row=i // 2, column=i % 2, sticky='w')
        layers = ttk.LabelFrame(right, text='Layer', padding=4)
        layers.pack(fill='x', pady=4)
        for i, (k, label) in enumerate(LAYERS):
            ttk.Radiobutton(layers, text=label, value=k, variable=self.layer,
                            command=self._fill_palette).grid(row=i // 2, column=i % 2, sticky='w')
        g = ttk.Frame(right)
        g.pack(fill='x')
        ttk.Label(g, text='Gold per square').pack(side='left')
        ttk.Spinbox(g, from_=1, to=9999, width=6, textvariable=self.gold).pack(side='left', padx=4)
        f = ttk.Frame(right)
        f.pack(fill='x', pady=(4, 0))
        ttk.Label(f, text='Find').pack(side='left')
        self.find = tk.StringVar()
        self.find.trace_add('write', lambda *a: self._fill_palette())
        ttk.Entry(f, textvariable=self.find, width=18).pack(side='left', padx=4, fill='x', expand=True)
        pal = ttk.Frame(right)
        pal.pack(fill='both', expand=True, pady=4)
        self.palette = ttk.Treeview(pal, show='tree', selectmode='browse', height=18)
        sb = ttk.Scrollbar(pal, orient='vertical', command=self.palette.yview)
        self.palette.configure(yscrollcommand=sb.set)
        self.palette.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.palette.bind('<<TreeviewSelect>>', lambda e: self._palette_pick())
        style = ttk.Style(self)
        style.configure('Treeview', rowheight=28)
        v = ttk.Frame(right)
        v.pack(fill='x')
        self.zoom = ttk.Combobox(v, values=list(ZOOMS), width=12, state='readonly')
        self.zoom.set('Large (40)')
        self.zoom.bind('<<ComboboxSelected>>', lambda e: self._set_zoom())
        self.zoom.pack(side='left')
        ttk.Checkbutton(v, text='Screens', variable=self.grid_lines, command=self.redraw).pack(side='left', padx=4)
        ttk.Checkbutton(v, text='Squares', variable=self.square_lines, command=self.redraw).pack(side='left')

        mid = ttk.Frame(self)
        mid.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(mid, width=800, height=560, background='#202020', highlightthickness=0)
        self.hbar = ttk.Scrollbar(mid, orient='horizontal', command=self._xview)
        self.vbar = ttk.Scrollbar(mid, orient='vertical', command=self._yview)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vbar.grid(row=0, column=1, sticky='ns')
        self.hbar.grid(row=1, column=0, sticky='ew')
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        self.status = ttk.Label(mid, text='', anchor='w')
        self.status.grid(row=2, column=0, columnspan=2, sticky='ew')
        c = self.canvas
        c.bind('<Configure>', lambda e: self.redraw())
        c.bind('<ButtonPress-1>', self._press)
        c.bind('<B1-Motion>', self._drag)
        c.bind('<ButtonRelease-1>', self._release)
        c.bind('<ButtonPress-3>', lambda e: self._pick_at(*self._square(e)))
        c.bind('<Motion>', self._motion)
        on_wheel(mid, self._wheel)                 # the wheel scrolls, Shift sideways, Ctrl zooms (uikit)
        c.bind('<Enter>', lambda e: c.focus_set())
        for key, d in (('<Left>', (-1, 0)), ('<Right>', (1, 0)), ('<Up>', (0, -1)), ('<Down>', (0, 1))):
            c.bind(key, lambda e, d=d: self._scroll(d[0] * 5, d[1] * 5))
        tip(self.canvas, 'The level, 100 x 100 squares. Click with the chosen tool. Wheel scrolls, Shift+wheel '
                         'scrolls sideways, Ctrl+wheel zooms. Arrow keys scroll. Ctrl+Z undoes.')
        tip(self.levels, 'The quest\'s levels. Click one to edit its map, script and settings.')
        tip(self.palette, 'What the chosen layer can put on the map. Click one to paint with it; Find narrows the list.')
        tip(self.zoom, 'How big the squares are (Ctrl+wheel on the map zooms too).')
        tip(self.stories, 'Story numbers (Stories tab), e.g. 2, 3, shown before the level.')

    # ── the project ─────────────────────────────────────────────────────────
    def load(self):
        self.art = Art(self.app.project)
        self.levels.delete(0, 'end')
        for n in range(1, self.app.project.levels + 1):
            self.levels.insert('end', f'Level {n}')
        self.level = min(self.level, self.app.project.levels) or 1
        self.levels.selection_set(self.level - 1)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._fill_palette()
        self._show_settings()
        self.redraw()

    @property
    def grid(self):
        return self.app.project.grid(self.level)

    def _pick_level(self):
        sel = self.levels.curselection()
        if sel and sel[0] + 1 != self.level:
            self.level = sel[0] + 1
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._show_settings()
            self.redraw()

    def _add_level(self):
        n = self.app.project.add_level()
        self.levels.insert('end', f'Level {n}')
        self.levels.selection_clear(0, 'end')
        self.levels.selection_set(n - 1)
        self._pick_level()
        self.app.changed()

    def _remove_level(self):
        p = self.app.project
        if p.levels <= 1:
            return
        if not messagebox.askyesno('Remove level', f'Remove level {p.levels}, its map, script and shops?'):
            return
        p.remove_last_level()
        self.load()
        self.app.changed()

    # ── settings ────────────────────────────────────────────────────────────
    def _show_settings(self):
        p = self.app.project
        start = p.constant(self.level, 'START', (5, 5))
        self.start_label.config(text=f'Start: {start[0]}, {start[1]}   (Start tool)')
        self.stories.delete(0, 'end')
        self.stories.insert(0, ', '.join(str(s) for s in p.constant(self.level, 'STORIES', [])))
        tp = p.constant(self.level, 'TELEPORT', (0, 0))
        self.teleport.delete(0, 'end')
        self.teleport.insert(0, f'{tp[0]}, {tp[1]}')
        self.ask_leave.set(p.constant(self.level, 'ASK_TO_LEAVE', True))
        self.jingle.set(p.constant(self.level, 'LEAVE_JINGLE', True))
        for name, e in self.look3d.items():
            v = p.constant(self.level, name)
            e.delete(0, 'end')
            e.insert(0, '' if v is None else str(v))

    def _pick_story(self):
        """Add a story from the Stories tab's list to the stories shown before this level."""
        from engine.formats import parse_story
        from .event_wizard import Picker
        stories = parse_story(self.app.project.texts['stories'])
        rows = [(n, s.split('\n')[0][:80]) for n, s in sorted(stories.items())]
        got = Picker(self, 'A story shown before this level', rows, ('Number', 'Begins')).result
        if got is not None:
            now = [v for v in self.stories.get().replace(',', ' ').split() if v]
            if str(got) not in now:
                self.stories.delete(0, 'end')
                self.stories.insert(0, ', '.join(now + [str(got)]))

    def _apply_settings(self):
        p, n = self.app.project, self.level
        try:
            stories = [int(s) for s in self.stories.get().replace(',', ' ').split()]
            tp = tuple(int(s) for s in self.teleport.get().replace(',', ' ').split())
            assert len(tp) == 2
        except (ValueError, AssertionError):
            messagebox.showerror('Level settings', 'Stories are numbers like 2, 3 and the teleporter jump is dx, dy.')
            return
        if stories != p.constant(n, 'STORIES', []):
            p.set_constant(n, 'STORIES', stories, 'story screens shown before the level')
        if tp != tuple(p.constant(n, 'TELEPORT', (0, 0))):
            p.set_constant(n, 'TELEPORT', tp, 'where a teleporter pad sends the hero (dx, dy)')
        try:
            look3d = {name: (int(e.get()) if e.get().strip() else None) for name, e in self.look3d.items()}
            assert all(v is None or 0 <= v <= 15 for k, v in look3d.items() if k != 'RANGE_3D')
            assert look3d['RANGE_3D'] is None or 2 <= look3d['RANGE_3D'] <= 30
        except (ValueError, AssertionError):
            messagebox.showerror('Level settings', 'The 3D sky and fog are EGA colours 0-15, the range 2-30 squares.')
            return
        for name, v in look3d.items():
            if v is None:
                p.remove_constant(n, name)
            elif v != p.constant(n, name):
                p.set_constant(n, name, v, dict(SETTINGS_3D)[name].lower())
        for name, var, what in (('ASK_TO_LEAVE', self.ask_leave, 'ask before leaving by the exit'),
                                ('LEAVE_JINGLE', self.jingle, 'play the jingle when leaving')):
            if var.get() != p.constant(n, name, True):
                p.set_constant(n, name, var.get(), what)
        self.app.changed()
        self.app.scripts_changed(n)

    def open_death(self):
        """What happens on this level when the hero dies: respawn, and the Underworld."""
        from .death_dialog import DeathWindow
        DeathWindow(self)

    def open_3d(self):
        """FPS mode's view of this level, from the square last clicked."""
        from .preview3d import Preview3D
        if self.preview3d is not None and self.preview3d.winfo_exists():
            self.preview3d.destroy()
        self.preview3d = Preview3D(self, self.selected)

    # ── palette ─────────────────────────────────────────────────────────────
    def _fill_palette(self):
        t, layer = self.palette, self.layer.get()
        t.delete(*t.get_children())
        if layer == 'gold':
            t.insert('', 'end', iid='1', text='  Gold (amount below)', image=self.art.icon('gold', 1))
            t.insert('', 'end', iid='0', text='  (remove gold)', image=self.art.icon('gold', 0))
        else:
            t.insert('', 'end', iid='0', text='  (nothing)', image=self.art.icon(layer, 0))
            want = self.find.get().strip().lower()
            for r in self.app.project.entries(layer):
                name = r.get('name') or ''
                if want and want not in name.lower() and want != str(r['id']):
                    continue
                t.insert('', 'end', iid=str(r['id']), text=f'  {r["id"]}  {name}', image=self.art.icon(layer, r['id']))
        v = str(self.value[layer])
        if t.exists(v):
            t.selection_set(v)
            t.see(v)

    def _palette_pick(self):
        sel = self.palette.selection()
        if sel:
            self.value[self.layer.get()] = int(sel[0])

    # ── view ────────────────────────────────────────────────────────────────
    def _view_size(self):
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        return min(SIZE, w // self.size + 1), min(SIZE, h // self.size + 1)

    def _set_zoom(self):
        cx, cy = self.ox + self._view_size()[0] // 2, self.oy + self._view_size()[1] // 2
        self.size = ZOOMS[self.zoom.get()]
        cols, rows = self._view_size()
        self.ox, self.oy = cx - cols // 2, cy - rows // 2
        self._scroll(0, 0)

    def _scroll(self, dx, dy):
        cols, rows = self._view_size()
        self.ox = max(1, min(SIZE - cols + 2, self.ox + dx))
        self.oy = max(1, min(SIZE - rows + 2, self.oy + dy))
        self.redraw()

    def _xview(self, *args):
        self._bar(args, 0)

    def _yview(self, *args):
        self._bar(args, 1)

    def _bar(self, args, axis):
        cols, rows = self._view_size()
        span = (cols, rows)[axis]
        cur = (self.ox, self.oy)[axis]
        if args[0] == 'moveto':
            new = int(float(args[1]) * SIZE) + 1
        else:
            step = int(args[1]) * (span if args[2] == 'pages' else 1)
            new = cur + step
        self._scroll(new - cur if axis == 0 else 0, new - cur if axis == 1 else 0)

    ZOOM_STEPS = (8, 12, 16, 20, 24, 32, 40, 48, 64)

    def _wheel(self, steps, ctrl, shift):
        if ctrl:
            self._zoom_by(-steps)
        else:
            self._scroll(steps * 2, 0) if shift else self._scroll(0, steps * 2)

    def _zoom_by(self, direction):
        """Ctrl + wheel: one step bigger (up) or smaller, keeping the square under the pointer where it is."""
        c = self.canvas
        px, py = c.winfo_pointerx() - c.winfo_rootx(), c.winfo_pointery() - c.winfo_rooty()
        px, py = max(0, min(c.winfo_width(), px)), max(0, min(c.winfo_height(), py))
        fx, fy = self.ox + px / self.size, self.oy + py / self.size          # the map point under the pointer
        steps = self.ZOOM_STEPS
        at = min(range(len(steps)), key=lambda i: abs(steps[i] - self.size))
        new = steps[max(0, min(len(steps) - 1, at + direction))]
        if new == self.size:
            return
        self.size = new
        self.zoom.set(f'{new} pixels')
        self.ox, self.oy = round(fx - px / new), round(fy - py / new)
        self._scroll(0, 0)

    def redraw(self):
        if not hasattr(self, 'art'):
            return
        cols, rows = self._view_size()
        s = self.size
        surf = pygame.Surface((cols * s, rows * s))
        surf.fill((32, 32, 32))
        g = self.grid
        for i in range(cols):
            for j in range(rows):
                x, y = self.ox + i, self.oy + j
                if 1 <= x <= SIZE and 1 <= y <= SIZE:
                    self.art.draw_square(surf, i * s, j * s, g.get(x, y), s)
        self._overlays(surf, cols, rows)
        self._img = photo(surf)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, image=self._img, anchor='nw')
        self.hbar.set((self.ox - 1) / SIZE, min(1, (self.ox - 1 + cols) / SIZE))
        self.vbar.set((self.oy - 1) / SIZE, min(1, (self.oy - 1 + rows) / SIZE))

    def _overlays(self, surf, cols, rows):
        p, s = self.app.project, self.size
        font = pygame.font.Font(None, max(14, s // 2))

        def at(x, y):
            return (x - self.ox) * s, (y - self.oy) * s
        if self.square_lines.get() and s >= 12:
            for x in range(self.ox, self.ox + cols + 1):
                if (x - 1) % 10:
                    pygame.draw.line(surf, (70, 70, 70), (at(x, 0)[0], 0), (at(x, 0)[0], rows * s))
            for y in range(self.oy, self.oy + rows + 1):
                if (y - 1) % 10:
                    pygame.draw.line(surf, (70, 70, 70), (0, at(0, y)[1]), (cols * s, at(0, y)[1]))
        if self.grid_lines.get():
            for x in range(self.ox, self.ox + cols + 1):
                if (x - 1) % 10 == 0:
                    pygame.draw.line(surf, (255, 255, 0), (at(x, 0)[0], 0), (at(x, 0)[0], rows * s))
            for y in range(self.oy, self.oy + rows + 1):
                if (y - 1) % 10 == 0:
                    pygame.draw.line(surf, (255, 255, 0), (0, at(0, y)[1]), (cols * s, at(0, y)[1]))
        peaceful = set(map(tuple, p.constant(self.level, 'PEACEFUL_SCREENS', ()) or ()))
        shops = p.constant(self.level, 'SHOPS', {}) or {}
        dark = set(map(tuple, p.constant(self.level, 'DARK_SCREENS', ()) or ()))
        for sx in range(1, 11):
            for sy in range(1, 11):
                px, py = at((sx - 1) * 10 + 1, (sy - 1) * 10 + 1)
                if (sx, sy) in dark:                              # shaded: it is dark there
                    shade = pygame.Surface((10 * s, 10 * s), pygame.SRCALPHA)
                    shade.fill((0, 0, 40, 130))
                    surf.blit(shade, (px, py))
                    pygame.draw.rect(surf, (140, 140, 255), (px + 2, py + 2, 10 * s - 4, 10 * s - 4), 1)
                if (sx, sy) in peaceful:
                    pygame.draw.rect(surf, (80, 200, 255), (px + 2, py + 2, 10 * s - 4, 10 * s - 4), 2)
                if (sx, sy) in shops:
                    surf.blit(font.render(f'Shop {shops[(sx, sy)]}', True, (255, 255, 255), (0, 0, 160)),
                              (px + 4, py + 4))
        for (lx, ly), link in (p.constant(self.level, 'LINKS', {}) or {}).items():
            if self.ox <= lx < self.ox + cols and self.oy <= ly < self.oy + rows:
                px, py = at(lx, ly)
                pygame.draw.rect(surf, (255, 160, 0), (px + 1, py + 1, s - 2, s - 2), 2)
                surf.blit(font.render(f'>{link[0]}', True, (255, 160, 0)), (px + 3, py + s // 2))
        for name, (ex, ey) in (p.constant(self.level, 'ENTRIES', {}) or {}).items():
            if self.ox <= ex < self.ox + cols and self.oy <= ey < self.oy + rows:
                px, py = at(ex, ey)
                pygame.draw.rect(surf, (80, 255, 120), (px + 1, py + 1, s - 2, s - 2), 2)
                surf.blit(font.render(f'E {name}', True, (80, 255, 120), (0, 60, 20)), (px + 3, py + 2))
        start = p.constant(self.level, 'START', (5, 5))
        px, py = at(*start)
        pygame.draw.rect(surf, (255, 255, 255), (px + 1, py + 1, s - 2, s - 2), 2)
        surf.blit(font.render('S', True, (255, 255, 255)), (px + 3, py + 2))
        spot = p.constant(self.level, 'RESPAWN')
        if spot:
            px, py = at(*spot)
            pygame.draw.rect(surf, (80, 255, 80), (px + 3, py + 3, s - 6, s - 6), 2)
            surf.blit(font.render('R', True, (80, 255, 80)), (px + s // 2 - 3, py + s // 2 - 5))
        if self.selected:
            px, py = at(*self.selected)
            pygame.draw.rect(surf, (255, 80, 255), (px, py, s, s), 2)
        if self.drag_from and self.tool.get() == 'rect' and self.hover:
            (x0, y0), (x1, y1) = self.drag_from, self.hover
            a, b = at(min(x0, x1), min(y0, y1))
            pygame.draw.rect(surf, (255, 255, 255), (a, b, (abs(x1 - x0) + 1) * s, (abs(y1 - y0) + 1) * s), 2)

    # ── mouse ───────────────────────────────────────────────────────────────
    def _square(self, e):
        return self.ox + e.x // self.size, self.oy + e.y // self.size

    @staticmethod
    def _inside(x, y):
        return 1 <= x <= SIZE and 1 <= y <= SIZE

    def _motion(self, e):
        x, y = self._square(e)
        if not self._inside(x, y):
            self.status.config(text='')
            return
        p = self.app.project
        sq = self.grid.get(x, y)
        parts = [f'({x}, {y})  screen ({(x - 1) // 10 + 1}, {(y - 1) // 10 + 1})']
        for layer, label in LAYERS:
            v = sq[FIELD[layer]]
            if v:
                parts.append(f'{label}: {v} {p.name_of(layer, v)}'.strip())
        self.status.config(text='    '.join(parts))
        if self.drag_from and self.tool.get() == 'rect' and self.hover != (x, y):
            self.hover = (x, y)
            self.redraw()
        self.hover = (x, y)

    def _press(self, e):
        x, y = self._square(e)
        if not self._inside(x, y):
            return
        self.selected = (x, y)
        if self.preview3d is not None and self.preview3d.winfo_exists():
            self.preview3d.goto(x, y)
        tool = self.tool.get()
        self.stroke = {}
        if tool == 'paint':
            self.drag_from = (x, y)
            self._paint(x, y)
        elif tool == 'rect':
            self.drag_from = self.hover = (x, y)
        elif tool == 'fill':
            self._flood(x, y)
            self._end_stroke()
        elif tool == 'pick':
            self._pick_at(x, y)
        elif tool == 'start':
            self.app.project.set_constant(self.level, 'START', (x, y), 'where the hero arrives')
            self._show_settings()
            self.app.changed()
            self.app.scripts_changed(self.level)
        elif tool == 'respawn':
            self.app.project.set_constant(self.level, 'RESPAWN', (x, y), 'where he wakes after dying here')
            self.app.changed()
            self.app.scripts_changed(self.level)
        elif tool in ('shop', 'peace', 'dark'):
            self._screen_tool(tool, (x - 1) // 10 + 1, (y - 1) // 10 + 1)
        elif tool == 'entry':
            self._entry_tool(x, y)
        elif tool == 'link':
            self._link_tool(x, y)
        self.redraw()

    def _drag(self, e):
        x, y = self._square(e)
        if not self._inside(x, y):
            return
        if self.tool.get() == 'paint' and self.drag_from:
            # the mouse can jump several squares between events: paint the line between them
            (x0, y0), n = self.drag_from, max(abs(x - self.drag_from[0]), abs(y - self.drag_from[1]))
            for k in range(1, n + 1):
                self._paint(x0 + round((x - x0) * k / n), y0 + round((y - y0) * k / n))
            self.drag_from = (x, y)
            self.redraw()
        else:
            self._motion(e)

    def _release(self, e):
        if self.tool.get() == 'rect' and self.drag_from:
            (x0, y0), (x1, y1) = self.drag_from, self.hover or self.drag_from
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    self._paint(x, y)
        self.drag_from = None
        self._end_stroke()
        self.redraw()

    def _pick_at(self, x, y):
        if not self._inside(x, y):
            return
        layer = self.layer.get()
        v = self.grid.get(x, y)[FIELD[layer]]
        if layer == 'gold':
            if v > 0:
                self.gold.set(v)
            v = 1 if v > 0 else 0
        self.value[layer] = v
        self._fill_palette()

    # ── editing ─────────────────────────────────────────────────────────────
    def _new_value(self):
        layer = self.layer.get()
        if layer == 'gold':
            return self.gold.get() if self.value['gold'] else 0
        return self.value[layer]

    def _set(self, x, y, v):
        sq = self.grid.get(x, y)
        i = FIELD[self.layer.get()]
        if sq[i] != v:
            if (x, y) not in self.stroke:
                self.stroke[(x, y)] = list(sq)
            sq[i] = v

    def _paint(self, x, y):
        self._set(x, y, self._new_value())

    def _flood(self, x, y):
        i = FIELD[self.layer.get()]
        g, v = self.grid, self._new_value()
        old = g.get(x, y)[i]
        if old == v:
            return
        todo, seen = [(x, y)], {(x, y)}
        while todo:
            cx, cy = todo.pop()
            self._set(cx, cy, v)
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if self._inside(nx, ny) and (nx, ny) not in seen and g.get(nx, ny)[i] == old:
                    seen.add((nx, ny))
                    todo.append((nx, ny))

    def _end_stroke(self):
        if self.stroke:
            after = {k: list(self.grid.get(*k)) for k in self.stroke}
            self.undo_stack.append((self.level, self.stroke, after))
            self.redo_stack.clear()
            self.stroke = {}
            self.app.project.touch(('map', self.level))
            self.app.changed()

    def undo(self):
        self._swap(self.undo_stack, self.redo_stack, 1)

    def redo(self):
        self._swap(self.redo_stack, self.undo_stack, 2)

    def _swap(self, src, dst, which):
        if not src:
            return
        level, before, after = src.pop()
        g = self.app.project.grid(level)
        for (x, y), sq in (before if which == 1 else after).items():
            g.sq[x][y] = list(sq)
        dst.append((level, before, after))
        self.app.project.touch(('map', level))
        self.app.changed()
        self.redraw()

    LINK_ITEMS = ('ladder', 'rope', 'stairs', 'hole', 'jump_pad')

    def _entry_tool(self, x, y):
        """A named way in to this level: where an exit, ladder ... of another level can put the hero. Clicking one again
        renames it (or removes it: an empty name)."""
        p, n = self.app.project, self.level
        entries = dict(p.constant(n, 'ENTRIES', {}) or {})
        here = next((k for k, v in entries.items() if tuple(v) == (x, y)), None)
        free = next(f'entry {i}' for i in range(1, 1000) if f'entry {i}' not in entries)
        name = simpledialog.askstring('Entry', f'Name of the way in at ({x}, {y}) on level {n}:\n'
                                      '(empty: take this entry away)', initialvalue=here or free, parent=self)
        if name is None:
            return
        name = name.strip()
        if here:
            entries.pop(here)
        if name:
            entries[name] = (x, y)
        if entries:
            p.set_constant(n, 'ENTRIES', entries, 'name -> (x, y): a way in other levels can link to')
        else:
            p.remove_constant(n, 'ENTRIES')
        self.app.changed()
        self.app.scripts_changed(n)

    def _link_tool(self, x, y):
        """Where the stairs (ladder, rope, hole, pad) on (x, y) lead. A way back can be made at the same time:
        the link on the other level, with the same item put there if the square has none."""
        p, n = self.app.project, self.level
        links = dict(p.constant(n, 'LINKS', {}) or {})
        item = self.grid.get(x, y)[FIELD['item']]
        if p.item_type(item) not in self.LINK_ITEMS + ('exit',) and (x, y) not in links:
            messagebox.showinfo('Link', 'Put a ladder, rope, stairs, hole, jump pad or exit here first (Item layer; the '
                                        'Items tab makes them: their Type).')
            return
        is_exit = p.item_type(item) == 'exit'
        dlg = LinkDialog(self, f'{"Exit" if is_exit else "Link"} at ({x}, {y}) on level {n}', links.get((x, y)), p.levels,
                         two_way=p.item_type(item) not in ('hole', 'jump_pad', 'exit'), is_exit=is_exit)
        if dlg.result is None:
            return
        if dlg.result == 'remove':
            links.pop((x, y), None)
        else:
            level, tx, ty, text, way_back = dlg.result
            if isinstance(tx, str):
                links[(x, y)] = (level, tx)                       # to the entry of that name
            elif tx is None:
                links[(x, y)] = (level,)                          # an exit to a level's start
            else:
                links[(x, y)] = (level, tx, ty, text) if text else (level, tx, ty)
            if way_back:
                other = dict(p.constant(level, 'LINKS', {}) or {})
                other[(tx, ty)] = (n, x, y)
                p.set_constant(level, 'LINKS', other, 'square -> (level, x, y) of the other end')
                sq = p.grid(level).get(tx, ty)
                if not sq[FIELD['item']]:
                    sq[FIELD['item']] = item                   # the same stairs at the other end
                p.touch(('map', level))
                self.app.scripts_changed(level)
        if links:
            p.set_constant(n, 'LINKS', links, 'square -> (level, x, y) of the other end')
        else:
            p.remove_constant(n, 'LINKS')
        self.app.changed()
        self.app.scripts_changed(n)
        self.redraw()

    def _screen_tool(self, tool, sx, sy):
        p, n = self.app.project, self.level
        if tool == 'shop':
            shops = dict(p.constant(n, 'SHOPS', {}) or {})
            k = simpledialog.askinteger('Shop', f'Which shop does screen ({sx}, {sy}) have?\n'
                                        f'(its wares: level {n}, shop k; 0 = none)',
                                        initialvalue=shops.get((sx, sy), 1), minvalue=0, maxvalue=9, parent=self)
            if k is None:
                return
            if k:
                shops[(sx, sy)] = k
                if k not in p.shops.setdefault(n, {}):
                    p.shops[n][k] = '1 3\n'                   # a new shop starts with two potions
                    p.touch(('shops', n))
                    self.app.text_tab.load()
            else:
                shops.pop((sx, sy), None)
            p.set_constant(n, 'SHOPS', shops, 'screen (column, row) -> shop number')
        elif tool == 'dark':
            dark = [tuple(v) for v in p.constant(n, 'DARK_SCREENS', []) or []]
            if (sx, sy) in dark:
                dark.remove((sx, sy))
            else:
                dark.append((sx, sy))
            if dark:
                p.set_constant(n, 'DARK_SCREENS', dark, 'screens where only the hero and his light show')
            else:
                p.remove_constant(n, 'DARK_SCREENS')
        else:
            peaceful = [tuple(v) for v in p.constant(n, 'PEACEFUL_SCREENS', []) or []]
            if (sx, sy) in peaceful:
                peaceful.remove((sx, sy))
            else:
                peaceful.append((sx, sy))
            p.set_constant(n, 'PEACEFUL_SCREENS', peaceful, "screens where people and allies don't attack monsters")
        self.app.changed()
        self.app.scripts_changed(n)


class LinkDialog(simpledialog.Dialog):
    """Where a link leads: the level, the square and the words shown; a way back; or remove it."""

    def __init__(self, parent, title, link, levels, two_way=True, is_exit=False):
        self.link, self.levels, self.two_way, self.is_exit = link, levels, two_way, is_exit
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        link = self.link or ((1, '', '') if self.is_exit else (1, 5, 5))
        link = tuple(link) + ('', '') if len(link) == 1 else link
        self.entry_names = self.entries_of(link[0] if isinstance(link[0], int) else 1)
        link = (link[0], '', '') + tuple(link[2:]) if isinstance(link[1], str) else link
        self.vars = {}
        for i, (key, label, value) in enumerate((('level', 'Leads to level', link[0]),
                                                 ('x', 'at x (1-100)' + (' (empty: its start)' if self.is_exit else ''), link[1]),
                                                 ('y', 'and y (1-100)', link[2]),
                                                 ('text', 'Words shown (empty: the default)',
                                                  link[3] if len(link) > 3 else ''))):
            ttk.Label(master, text=label).grid(row=i, column=0, sticky='w', pady=2)
            self.vars[key] = tk.StringVar(value=str(value))
            if key == 'level':
                w = ttk.Combobox(master, textvariable=self.vars[key], state='readonly', width=8,
                                 values=[str(n) for n in range(1, self.levels + 1)])
                self.level_box = w
            else:
                w = ttk.Entry(master, textvariable=self.vars[key], width=30 if key == 'text' else 8)
            w.grid(row=i, column=1, sticky='w')
        row = 4 + (1 if self.two_way else 0)
        ttk.Label(master, text='or at the entry named').grid(row=row, column=0, sticky='w', pady=2)
        self.vars['entry'] = tk.StringVar(value=self.link[1] if self.link and len(self.link) == 2 and isinstance(self.link[1], str) else '')
        self.entry_box = ttk.Combobox(master, textvariable=self.vars['entry'], width=18, values=[''] + self.entry_names)
        self.entry_box.grid(row=row, column=1, sticky='w')
        self.level_box.bind('<<ComboboxSelected>>', lambda e: self.entry_box.config(
            values=[''] + self.entries_of(int(self.vars['level'].get()))))
        self.back = tk.BooleanVar(value=self.two_way and not self.link)
        if self.two_way:
            ttk.Checkbutton(master, text='Also make the way back (the link and the same item at the other end)',
                            variable=self.back).grid(row=4, column=0, columnspan=2, sticky='w', pady=4)
        self.remove = tk.BooleanVar(value=False)
        if self.link:
            ttk.Checkbutton(master, text='Remove this link', variable=self.remove).grid(
                row=5, column=0, columnspan=2, sticky='w')
        return None

    def entries_of(self, level):
        project = getattr(self.master, 'app', None) and self.master.app.project
        return sorted((project.constant(level, 'ENTRIES', {}) or {}).keys()) if project else []

    def validate(self):
        if self.remove.get():
            return True
        if self.vars['entry'].get().strip():
            try:
                assert 1 <= int(self.vars['level'].get()) <= self.levels
            except (ValueError, AssertionError):
                return False
            return True
        try:
            if self.is_exit and not self.vars['x'].get().strip() and not self.vars['y'].get().strip():
                assert 1 <= int(self.vars['level'].get()) <= self.levels
                return True
            level, x, y = (int(self.vars[k].get()) for k in ('level', 'x', 'y'))
            assert 1 <= level <= self.levels and 1 <= x <= SIZE and 1 <= y <= SIZE
        except (ValueError, AssertionError):
            messagebox.showerror('Link', 'A level of this quest, and x and y from 1 to 100.', parent=self)
            return False
        return True

    def apply(self):
        if self.remove.get():
            self.result = 'remove'
            return
        if self.vars['entry'].get().strip():
            self.result = (int(self.vars['level'].get()), self.vars['entry'].get().strip(), None, '', False)
            return
        if self.is_exit and not self.vars['x'].get().strip() and not self.vars['y'].get().strip():
            self.result = (int(self.vars['level'].get()), None, None, '', False)
            return
        self.result = (int(self.vars['level'].get()), int(self.vars['x'].get()), int(self.vars['y'].get()),
                       self.vars['text'].get().strip(), self.back.get())
