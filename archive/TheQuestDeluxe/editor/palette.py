"""The picture palette: every small picture of the pack on one shelf, inside the painter. Drag one onto the picture being
painted to stamp it there (its see-through parts leave what is under them), or double-click it to start the picture as a
copy of it. Items, creatures, heroes, floors, walls, decorations and spell icons are all here."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pygame

from .art import photo
from .uikit import tip

COLS = 6
CELL = 44
# (label, sprite folder, where the names are)
KINDS = [('Items on the map', 'items', 'items'), ('Items in the bag', 'bag', 'items'),
         ('Creatures', 'creatures', 'creatures'), ('Heroes', 'heroes', 'classes'), ('Floors', 'floors', 'floors'),
         ('Walls and doors', 'walls', 'walls'), ('Decorations', 'decos', 'decos'), ('Spell icons', 'spells', 'spells')]


class PicturePalette(ttk.LabelFrame):
    def __init__(self, master, project, on_drop, on_start, folder=None):
        """on_drop(surface, root_x, root_y): a picture was let go there; on_start(surface): double-clicked."""
        super().__init__(master, text='Pictures to start from', padding=4)
        self.project, self.on_drop, self.on_start = project, on_drop, on_start
        # it opens on the kind of picture being painted: creatures on creatures, floors on floors ...
        self.kind = tk.StringVar(value=next((k[0] for k in KINDS if k[1] == folder), KINDS[0][0]))
        self.find = tk.StringVar()
        self._shown: list = []          # [(name, surface)] in the grid
        self._photos: list = []
        self._ghost = None
        top = ttk.Frame(self)
        top.pack(fill='x')
        box = ttk.Combobox(top, textvariable=self.kind, state='readonly', width=18, values=[k[0] for k in KINDS])
        box.pack(side='left')
        box.bind('<<ComboboxSelected>>', lambda e: self.fill())
        ttk.Entry(top, textvariable=self.find, width=8).pack(side='left', padx=4, fill='x', expand=True)
        self.find.trace_add('write', lambda *a: self.fill())
        tip(box, 'Which pictures to show.')
        body = ttk.Frame(self)
        body.pack(fill='both', expand=True, pady=4)
        self.canvas = tk.Canvas(body, width=COLS * CELL, height=230, highlightthickness=0, background='#404040')
        bar = ttk.Scrollbar(body, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        bar.pack(side='left', fill='y')
        self.name = ttk.Label(self, text='Drag one onto the picture, or double-click to start from it.',
                              foreground='#555', wraplength=COLS * CELL + 14, justify='left')
        self.name.pack(anchor='w')
        c = self.canvas
        c.bind('<ButtonPress-1>', self._press)
        c.bind('<B1-Motion>', self._drag)
        c.bind('<ButtonRelease-1>', self._release)
        c.bind('<Double-Button-1>', self._double)
        c.bind('<Motion>', self._hover)
        c.bind('<MouseWheel>', lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        c.bind('<Button-4>', lambda e: c.yview_scroll(-1, 'units'))
        c.bind('<Button-5>', lambda e: c.yview_scroll(1, 'units'))
        tip(c, 'Every picture of the pack: drag one onto the picture you are painting (it is stamped in the middle '
               'of it, wherever you let go), or double-click to start the picture as a copy of it. Undo takes it back.')
        self.cache: dict = {}
        self.fill()

    # ── what is on the shelf ────────────────────────────────────────────────
    def names(self, table: str) -> dict:
        p = self.project
        rows = p.tiles.get(table, []) if table in ('floors', 'walls', 'decos') else p.tables.get(table, [])
        return {r['id']: r.get('name', '') for r in rows}

    def pictures(self, label: str):
        if label not in self.cache:
            _, folder, table = next(k for k in KINDS if k[0] == label)
            names, out = self.names(table), []
            for v in self.project.picture_ids(folder):
                img = self.project.picture(folder, v)
                if img is not None:
                    out.append((f'{v}  {names.get(v, "")}'.strip(), img.convert_alpha() if img.get_bitsize() == 32 or
                                img.get_flags() & pygame.SRCALPHA else img))
            self.cache[label] = out
        return self.cache[label]

    def fill(self):
        want = self.find.get().strip().lower()
        c = self.canvas
        c.delete('all')
        self._shown, self._photos = [], []
        for name, img in self.pictures(self.kind.get()):
            if want and want not in name.lower():
                continue
            i = len(self._shown)
            tile = pygame.Surface((40, 40))
            tile.fill((70, 70, 70))
            tile.blit(pygame.transform.scale(img, (40, 40)) if img.get_size() != (40, 40) else img, (0, 0))
            ph = photo(tile)
            self._photos.append(ph)
            self._shown.append((name, img))
            c.create_image((i % COLS) * CELL + 2, (i // COLS) * CELL + 2, image=ph, anchor='nw')
        rows = (len(self._shown) + COLS - 1) // COLS
        c.configure(scrollregion=(0, 0, COLS * CELL, max(1, rows) * CELL))
        c.yview_moveto(0)

    def refresh(self):
        """The pack's pictures changed: read them again."""
        self.cache.clear()
        self.fill()

    # ── the mouse ───────────────────────────────────────────────────────────
    def _index(self, e):
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        i = int(y // CELL) * COLS + int(x // CELL)
        return i if 0 <= x < COLS * CELL and 0 <= i < len(self._shown) else None

    def _hover(self, e):
        i = self._index(e)
        if i is not None:
            self.name.config(text=self._shown[i][0])

    def _press(self, e):
        self._held, self._moved = self._index(e), False

    def _drag(self, e):
        if self._held is None:
            return
        self._moved = True
        if self._ghost is None:
            g = tk.Toplevel(self)
            g.overrideredirect(True)
            g.attributes('-topmost', True)
            self._ghost_img = photo(self._thumb(self._held))
            tk.Label(g, image=self._ghost_img, borderwidth=1, relief='solid').pack()
            self._ghost = g
        self._ghost.geometry(f'+{e.x_root + 6}+{e.y_root + 6}')
        self.canvas.configure(cursor='hand2')

    def _thumb(self, i):
        tile = pygame.Surface((40, 40))
        tile.fill((70, 70, 70))
        img = self._shown[i][1]
        tile.blit(pygame.transform.scale(img, (40, 40)) if img.get_size() != (40, 40) else img, (0, 0))
        return tile

    def _release(self, e):
        if self._ghost is not None:
            self._ghost.destroy()
            self._ghost = None
        self.canvas.configure(cursor='')
        if self._held is not None and self._moved:
            self.on_drop(self._shown[self._held][1], e.x_root, e.y_root)
        self._held = None

    def _double(self, e):
        i = self._index(e)
        if i is not None:
            self.on_start(self._shown[i][1])
