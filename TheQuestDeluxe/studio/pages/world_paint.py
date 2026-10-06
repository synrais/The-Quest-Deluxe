"""The Paint panel of the World page: which layer, what to put on it, how big the brush is."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import icons, theme, ui
from ..gallery import Entry, Gallery
from ..theme import C, px

LAYERS = [('floor', 'Ground', 'grid', 'Grass, paths, water, floors: every square has one.'),
          ('wall', 'Walls', 'tiles', 'Walls, trees, doors and rocks: what blocks the way.'),
          ('deco', 'Decoration', 'tree', 'Flat details on the ground: blood, bones, flowers.'),
          ('item', 'Items', 'key', 'Things to pick up, chests, stairs, exits and ladders.'),
          ('mon', 'Creatures', 'skull', 'Monsters and people.'),
          ('gold', 'Gold', 'coin', 'A heap of gold coins.')]
GOLD_PRESETS = (5, 10, 25, 50, 100, 250, 500)
LAYER_PAGE = {'floor': 'tiles', 'wall': 'tiles', 'deco': 'tiles', 'item': 'items', 'mon': 'creatures'}


class PalettePanel(ttk.Frame):
    def __init__(self, master, host):
        super().__init__(master)
        self.host, self.s = host, host.s
        self.layer = 'floor'
        self.picks = {l: [1] for l, *_ in LAYERS}          # what each layer paints
        self.picks['wall'] = [1]
        self.gold = 25
        self.rows = {}
        self._build()

    # ── build ───────────────────────────────────────────────────────────────
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=px(10), pady=(px(10), px(4)))
        ttk.Label(top, text='Layers', style='H3.TLabel').pack(side='left')
        ttk.Label(top, text='click one to paint on it', style='Faint.TLabel').pack(side='left', padx=px(8))
        box = tk.Frame(self, bg=C['panel'])
        box.pack(fill='x', padx=px(10))
        for layer, title, icon, about in LAYERS:
            row = tk.Frame(box, bg=C['panel'], cursor='hand2', highlightthickness=1, highlightbackground=C['panel'])
            row.pack(fill='x', pady=1)
            pic = tk.Label(row, bg=C['panel'], bd=0)
            pic.pack(side='left', padx=(px(6), px(6)), pady=px(3))
            name = tk.Label(row, text=title, bg=C['panel'], fg=C['text'], anchor='w', font=(theme.FONT, 10))
            name.pack(side='left', fill='x', expand=True)
            lock = tk.Label(row, bg=C['panel'], bd=0, cursor='hand2')
            lock.pack(side='right', padx=(0, px(6)))
            eye = tk.Label(row, bg=C['panel'], bd=0, cursor='hand2')
            eye.pack(side='right', padx=px(2))
            for w in (row, pic, name):
                w.bind('<Button-1>', lambda e, l=layer: self.choose_layer(l))
            eye.bind('<Button-1>', lambda e, l=layer: self.toggle_hidden(l))
            lock.bind('<Button-1>', lambda e, l=layer: self.toggle_locked(l))
            ui.tip(row, about)
            ui.tip(eye, 'Show or hide this layer on the map.')
            ui.tip(lock, 'Lock this layer so painting cannot change it.')
            self.rows[layer] = (row, pic, name, eye, lock, icon)
        self._paint_rows()

        opts = ttk.Frame(self)
        opts.pack(fill='x', padx=px(10), pady=(px(10), 0))
        ttk.Label(opts, text='Brush size').pack(side='left')
        self.size = ui.Number(opts, 1, 9, 1, live=self._size, width=3)
        self.size.pack(side='right')
        hollow = ttk.Frame(self)
        hollow.pack(fill='x', padx=px(10), pady=(px(4), 0))
        ttk.Label(hollow, text='Rectangles are hollow (outline only)').pack(side='left')
        self.hollow = ui.Switch(hollow, False, self._hollow)
        self.hollow.pack(side='right')

        self.title = ttk.Frame(self)
        self.title.pack(fill='x', padx=px(10), pady=(px(12), px(4)))
        self.what = ttk.Label(self.title, text='', style='H3.TLabel')
        self.what.pack(side='left')
        self.mix_label = ttk.Label(self.title, text='', style='Accent.TLabel')
        self.mix_label.pack(side='left', padx=px(8))
        self.edit_btn = ttk.Button(self.title, text='Edit ▸', style='Flat.TButton', command=self._edit_this)
        self.edit_btn.pack(side='right')
        self.search = ui.SearchBox(self, lambda t: self.gallery.filter(t), 'Search', width=18)
        self.search.pack(fill='x', padx=px(10), pady=(0, px(6)))
        self.stack = ttk.Frame(self)
        self.stack.pack(fill='both', expand=True, padx=px(6), pady=(0, px(6)))
        self.gallery = Gallery(self.stack, on_picks=self._picked, card=(84, 84), multi=True)
        self.goldbox = ttk.Frame(self.stack)
        self._build_gold()
        self.fill()

    def _build_gold(self):
        g = self.goldbox
        ttk.Label(g, text='How much gold in a heap?', style='Dim.TLabel').pack(anchor='w', padx=px(6), pady=(px(6), px(4)))
        row = ttk.Frame(g)
        row.pack(fill='x', padx=px(6))
        for n in GOLD_PRESETS:
            ttk.Button(row, text=str(n), width=4, style='TButton', command=lambda n=n: self._set_gold(n)).pack(side='left', padx=1)
        self.gold_num = ui.Number(g, 1, 9999, self.gold, commit=self._set_gold, soft_max=500)
        self.gold_num.pack(anchor='w', padx=px(6), pady=px(10))
        ttk.Label(g, text='Put a heap of gold on the map with the brush.\nThe eraser takes it away.', style='Faint.TLabel',
                  justify='left').pack(anchor='w', padx=px(6))

    # ── layers ──────────────────────────────────────────────────────────────
    def _paint_rows(self):
        m = self.host.map
        for layer, (row, pic, name, eye, lock, icon) in self.rows.items():
            on = layer == self.layer
            bg = C['select'] if on else C['panel']
            hidden, locked = layer in m.hidden, layer in m.locked
            row.configure(bg=bg, highlightbackground=C['accent'] if on else C['panel'])
            for w in (pic, name, eye, lock):
                w.configure(bg=bg)
            pic.configure(image=icons.icon(icon, C['accent'] if on else C['dim'], px(18)))
            name.configure(fg=C['text'] if on and not hidden else C['faint'] if hidden else C['dim'],
                           font=(theme.FONT, 10, 'bold' if on else 'normal'))
            eye.configure(image=icons.icon('eye', C['faint'] if hidden else C['dim'], px(16)))
            lock.configure(image=icons.icon('lock', C['warn'] if locked else C['faint'], px(15)))

    def choose_layer(self, layer, switch_tool=True):
        self.layer = layer
        self._paint_rows()
        self.search.clear()
        self.fill()
        if switch_tool and self.host.map.tool in ('pick', 'select', 'eraser') and self.host.map.tool != 'eraser':
            self.host.choose_tool('brush')
        self._apply()

    def toggle_hidden(self, layer):
        m = self.host.map
        m.hidden ^= {layer}
        self._paint_rows()
        m.refresh()

    def toggle_locked(self, layer):
        self.host.map.locked ^= {layer}
        self._paint_rows()

    # ── what to paint ───────────────────────────────────────────────────────
    def entries(self, layer):
        pic, p = self.s.pictures, self.s.project
        out = []
        if layer in ('floor', 'wall', 'deco'):
            for r in p.entries(layer):
                tags = []
                if layer == 'wall':
                    if r.get('door'):
                        tags.append('door')
                    elif r.get('solid') is False:
                        tags.append('walk-through')
                out.append(Entry(r['id'], r.get('name') or f'#{r["id"]}', ' · '.join(tags), pic.thumb(layer, r['id'], 48, 'raised'),
                                 search=f'{r.get("name", "")} {r["id"]} {" ".join(tags)}'.lower()))
        elif layer == 'item':
            for r in p.entries('item'):
                kind = r.get('type', '')
                out.append(Entry(r['id'], r.get('name') or f'#{r["id"]}', kind, pic.thumb('item', r['id'], 48, 'raised'),
                                 search=f'{r.get("name", "")} {kind} {r["id"]}'.lower()))
        elif layer == 'mon':
            for r in p.entries('mon'):
                out.append(Entry(r['id'], r.get('name') or f'#{r["id"]}', '', pic.thumb('mon', r['id'], 48, 'raised'),
                                 search=f'{r.get("name", "")} {r["id"]}'.lower()))
        return out

    def fill(self):
        """Show the palette of the chosen layer."""
        layer = self.layer
        title = dict((l, t) for l, t, *_ in LAYERS)[layer]
        self.what.configure(text=title)
        if layer == 'gold':
            self.gallery.pack_forget()
            self.search.pack_forget()
            self.goldbox.pack(fill='both', expand=True)
            self.edit_btn.pack_forget()
        else:
            self.goldbox.pack_forget()
            if not self.search.winfo_ismapped():
                self.search.pack(fill='x', padx=px(10), pady=(0, px(6)), before=self.stack)
            self.gallery.pack(fill='both', expand=True)
            self.gallery.set_items(self.entries(layer))
            keys = [k for k in self.picks[layer] if any(e.key == k for e in self.gallery.items)] or \
                   ([self.gallery.items[0].key] if self.gallery.items else [])
            self.picks[layer] = keys
            self.gallery.set_picks(keys)
            self.edit_btn.pack(side='right')
        self._label()

    def _label(self):
        layer = self.layer
        keys = self.picks[layer]
        self.mix_label.configure(text=f'mixing {len(keys)} kinds' if len(keys) > 1 else '')
        if layer == 'gold':
            return
        if keys:
            v = keys[0]
            self.what.configure(text=f'{dict((l, t) for l, t, *_ in LAYERS)[layer]}: {self.s.project.name_of(layer, v)}')
        self.edit_btn.configure(state='normal' if layer in LAYER_PAGE else 'disabled')
        if layer in ('floor', 'wall', 'deco', 'item', 'mon'):
            ui.tip(self.edit_btn, 'Change this one on its own page.')

    def _picked(self, keys):
        self.picks[self.layer] = list(keys)
        self._label()
        if self.host.map.tool in ('eraser', 'pick', 'select') and self.host.map.tool != 'eraser':
            self.host.choose_tool('brush')
        self._apply()

    def _set_gold(self, n):
        self.gold = int(n)
        self.gold_num.set(self.gold)
        self._apply()

    def _size(self, n):
        self.host.map.brush.size = int(n)
        self.host.map._refresh_cursor()

    def _hollow(self, on):
        self.host.map.hollow = bool(on)

    def _apply(self):
        b = self.host.map.brush
        b.layer = self.layer
        b.values = [self.gold] if self.layer == 'gold' else (list(self.picks[self.layer]) or [1])

    def _edit_this(self):
        keys = self.picks[self.layer]
        page = LAYER_PAGE.get(self.layer)
        if keys and page:
            self.host.app.go(page, select=keys[0], layer=self.layer)

    # ── from outside ────────────────────────────────────────────────────────
    def pick(self, layer, value):
        """The pick tool took this from the map."""
        if layer == 'gold':
            self.layer = 'gold'
            self.gold = int(value)
            self.gold_num.set(self.gold)
            self._paint_rows()
            self.fill()
            self._apply()
            return
        if not value:
            return
        self.picks[layer] = [value]
        self.layer = layer
        self._paint_rows()
        self.search.clear()
        self.fill()
        self._apply()

    def refresh(self):
        self._paint_rows()
        self.fill()
        self._apply()
