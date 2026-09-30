"""The picture painter: 40 x 40 pictures in the game's 16 EGA colours (and transparent, for pictures
drawn over the floor).

Pencil: paint pixels (drag to draw)
Line: drag from one end to the other
Fill: fill the area of one colour
Rectangle: drag a filled rectangle
Pick: take a colour from the picture
   (Alt+click does this with any tool)

Left button paints the left colour,
right button the right colour.
Ctrl+Z / Ctrl+Y undo and redo.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pygame

from .art import EGA, photo

N = 40
ZOOM = 12
CLEAR = -1


def to_cells(surface, opaque: bool) -> list[list[int]]:
    """A picture as colour numbers (-1 = transparent), each pixel the nearest EGA colour."""
    cells = [[CLEAR] * N for _ in range(N)]
    if surface is None:
        return [[0] * N for _ in range(N)] if opaque else cells
    if surface.get_size() != (N, N):
        surface = pygame.transform.scale(surface, (N, N))
    has_alpha = bool(surface.get_flags() & pygame.SRCALPHA)
    for x in range(N):
        for y in range(N):
            c = surface.get_at((x, y))
            if has_alpha and c.a < 128 and not opaque:
                continue
            cells[x][y] = min(range(16), key=lambda i: sum((a - b) ** 2 for a, b in zip(EGA[i], c[:3])))
    return cells


def to_surface(cells) -> pygame.Surface:
    s = pygame.Surface((N, N), pygame.SRCALPHA)
    for x in range(N):
        for y in range(N):
            if cells[x][y] != CLEAR:
                s.set_at((x, y), (*EGA[cells[x][y]], 255))
    return s


class Painter(tk.Toplevel):
    def __init__(self, master, title: str, surface, on_save, opaque: bool = False):
        """opaque: every pixel has a colour (floors, bag cells); otherwise transparent is a colour too."""
        super().__init__(master)
        self.title(title)
        self.on_save, self.opaque = on_save, opaque
        self.cells = to_cells(surface, opaque)
        self.left, self.right = 15, (0 if opaque else CLEAR)
        self.tool = tk.StringVar(value='pencil')
        self.undo_stack, self.redo_stack = [], []
        self.start = None
        self.before = None
        self.dirty = False
        self._build()
        self.redraw()
        self.bind('<Control-z>', lambda e: self.undo())
        self.bind('<Control-y>', lambda e: self.redo())
        self.protocol('WM_DELETE_WINDOW', self.close)

    # ── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        left = ttk.Frame(self, padding=6)
        left.pack(side='left', fill='y')
        tools = ttk.LabelFrame(left, text='Tool', padding=4)
        tools.pack(fill='x')
        for k, label in (('pencil', 'Pencil'), ('line', 'Line'), ('fill', 'Fill'), ('rect', 'Rectangle'),
                         ('pick', 'Pick')):
            ttk.Radiobutton(tools, text=label, value=k, variable=self.tool).pack(anchor='w')
        pal = ttk.LabelFrame(left, text='Colours', padding=4)
        pal.pack(fill='x', pady=6)
        choices = list(range(16)) + ([] if self.opaque else [CLEAR])
        for i, c in enumerate(choices):
            sw = tk.Canvas(pal, width=26, height=26, highlightthickness=1, highlightbackground='#888')
            self._swatch(sw, c)
            sw.grid(row=i // 4, column=i % 4, padx=1, pady=1)
            sw.bind('<Button-1>', lambda e, c=c: self._choose(c, 'left'))
            sw.bind('<Button-3>', lambda e, c=c: self._choose(c, 'right'))
        ttk.Label(pal, text='left / right click\na colour to choose it', foreground='#555').grid(
            row=5, column=0, columnspan=4, pady=4)
        cur = ttk.Frame(left)
        cur.pack(fill='x')
        ttk.Label(cur, text='Left').pack(side='left')
        self.lsw = tk.Canvas(cur, width=26, height=26)
        self.lsw.pack(side='left', padx=4)
        ttk.Label(cur, text='Right').pack(side='left')
        self.rsw = tk.Canvas(cur, width=26, height=26)
        self.rsw.pack(side='left', padx=4)
        moves = ttk.LabelFrame(left, text='Move', padding=4)
        moves.pack(fill='x', pady=6)
        for i, (label, fn) in enumerate((('Left', lambda: self.shift(-1, 0)), ('Right', lambda: self.shift(1, 0)),
                                         ('Up', lambda: self.shift(0, -1)), ('Down', lambda: self.shift(0, 1)),
                                         ('Flip ↔', lambda: self.flip(True)), ('Flip ↕', lambda: self.flip(False)))):
            ttk.Button(moves, text=label, width=7, command=fn).grid(row=i // 2, column=i % 2, padx=1, pady=1)
        ttk.Button(left, text='Clear', command=self.clear).pack(fill='x')
        ttk.Button(left, text='Save', command=self.save).pack(fill='x', pady=(12, 2))
        ttk.Button(left, text='Close', command=self.close).pack(fill='x')

        mid = ttk.Frame(self, padding=6)
        mid.pack(side='left')
        self.canvas = tk.Canvas(mid, width=N * ZOOM, height=N * ZOOM, highlightthickness=0, background='#333')
        self.canvas.pack()
        self.rects = [[self.canvas.create_rectangle(x * ZOOM, y * ZOOM, x * ZOOM + ZOOM, y * ZOOM + ZOOM, width=0)
                       for y in range(N)] for x in range(N)]
        for k in range(0, N + 1, 10):
            self.canvas.create_line(k * ZOOM, 0, k * ZOOM, N * ZOOM, fill='#555')
            self.canvas.create_line(0, k * ZOOM, N * ZOOM, k * ZOOM, fill='#555')
        for b, which in (('1', 'left'), ('3', 'right')):
            self.canvas.bind(f'<ButtonPress-{b}>', lambda e, w=which: self._press(e, w))
            self.canvas.bind(f'<B{b}-Motion>', lambda e, w=which: self._drag(e, w))
            self.canvas.bind(f'<ButtonRelease-{b}>', lambda e, w=which: self._release(e, w))
        self.status = ttk.Label(mid, text='')
        self.status.pack(anchor='w')
        self.canvas.bind('<Motion>', lambda e: self.status.config(text=f'({e.x // ZOOM}, {e.y // ZOOM})'))

        right = ttk.Frame(self, padding=6)
        right.pack(side='left', fill='y')
        ttk.Label(right, text='As it looks').pack(anchor='w')
        self.previews = ttk.Label(right)
        self.previews.pack(anchor='w')
        ttk.Label(right, text=__doc__.split('\n\n', 1)[1], foreground='#555', justify='left').pack(anchor='w', pady=8)

    def _swatch(self, canvas, c):
        canvas.delete('all')
        if c == CLEAR:
            canvas.create_rectangle(0, 0, 28, 28, fill='#bbb', width=0)
            canvas.create_rectangle(0, 0, 13, 13, fill='#fff', width=0)
            canvas.create_rectangle(13, 13, 28, 28, fill='#fff', width=0)
        else:
            canvas.create_rectangle(0, 0, 28, 28, fill='#%02x%02x%02x' % EGA[c], width=0)

    def _choose(self, c, which):
        setattr(self, which, c)
        self.redraw_swatches()

    def redraw_swatches(self):
        self._swatch(self.lsw, self.left)
        self._swatch(self.rsw, self.right)

    # ── drawing ─────────────────────────────────────────────────────────────
    def redraw(self):
        for x in range(N):
            for y in range(N):
                self._paint_rect(x, y)
        self.redraw_swatches()
        self._preview()

    def _paint_rect(self, x, y):
        c = self.cells[x][y]
        if c == CLEAR:
            fill = '#ffffff' if (x + y) % 2 else '#cccccc'
        else:
            fill = '#%02x%02x%02x' % EGA[c]
        self.canvas.itemconfig(self.rects[x][y], fill=fill)

    def _preview(self):
        img = to_surface(self.cells)
        s = pygame.Surface((4 + 40 * 3 + 8 + 40 * 2, 4 + 40 * 3))
        s.fill((80, 80, 80))
        for n, (bg, scale) in enumerate((((0, 168, 0), 3), ((0, 0, 0), 2))):
            x = 2 if n == 0 else 4 + 40 * 3 + 6
            tile = pygame.Surface((40, 40))
            tile.fill(bg)
            tile.blit(img, (0, 0))
            s.blit(pygame.transform.scale(tile, (40 * scale, 40 * scale)), (x, 2))
        self._pimg = photo(s)
        self.previews.config(image=self._pimg)

    # ── editing ─────────────────────────────────────────────────────────────
    def _cell(self, e):
        x, y = e.x // ZOOM, e.y // ZOOM
        return (x, y) if 0 <= x < N and 0 <= y < N else None

    def _remember(self):
        self.before = [col[:] for col in self.cells]

    def _commit(self):
        if self.before is not None and self.before != self.cells:
            self.undo_stack.append(self.before)
            self.redo_stack.clear()
            self.dirty = True
        self.before = None
        self._preview()

    def _set(self, x, y, c):
        if self.cells[x][y] != c:
            self.cells[x][y] = c
            self._paint_rect(x, y)

    def _press(self, e, which):
        p = self._cell(e)
        if p is None:
            return
        colour = getattr(self, which)
        tool = 'pick' if e.state & 0x0008 else self.tool.get()     # Alt: pick
        if tool == 'pick':
            setattr(self, which, self.cells[p[0]][p[1]])
            self.redraw_swatches()
            return
        self._remember()
        self.start = p
        if tool == 'pencil':
            self._set(*p, colour)
        elif tool == 'fill':
            self._flood(*p, colour)
            self._commit()

    def _drag(self, e, which):
        p = self._cell(e)
        if p is None or self.start is None:
            return
        tool, colour = self.tool.get(), getattr(self, which)
        if tool == 'pencil':
            for q in _line(self.start, p):
                self._set(*q, colour)
            self.start = p
        elif tool in ('line', 'rect'):
            self.cells = [col[:] for col in self.before]
            shape = _line(self.start, p) if tool == 'line' else _rect(self.start, p)
            for q in shape:
                self.cells[q[0]][q[1]] = colour
            self.redraw()

    def _release(self, e, which):
        if self.start is None:
            return
        tool = self.tool.get()
        if tool in ('line', 'rect'):
            self._drag(e, which)
        self.start = None
        self._commit()

    def _flood(self, x, y, c):
        old = self.cells[x][y]
        if old == c:
            return
        todo = [(x, y)]
        while todo:
            px, py = todo.pop()
            if 0 <= px < N and 0 <= py < N and self.cells[px][py] == old:
                self._set(px, py, c)
                todo += [(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)]

    def shift(self, dx, dy):
        self._remember()
        empty = 0 if self.opaque else CLEAR
        self.cells = [[self.cells[x - dx][y - dy] if 0 <= x - dx < N and 0 <= y - dy < N else empty
                       for y in range(N)] for x in range(N)]
        self._commit()
        self.redraw()

    def flip(self, horizontal):
        self._remember()
        self.cells = self.cells[::-1] if horizontal else [col[::-1] for col in self.cells]
        self._commit()
        self.redraw()

    def clear(self):
        self._remember()
        empty = 0 if self.opaque else CLEAR
        self.cells = [[empty] * N for _ in range(N)]
        self._commit()
        self.redraw()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append([col[:] for col in self.cells])
            self.cells = self.undo_stack.pop()
            self.dirty = True
            self.redraw()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append([col[:] for col in self.cells])
            self.cells = self.redo_stack.pop()
            self.dirty = True
            self.redraw()

    # ── saving ──────────────────────────────────────────────────────────────
    def picture(self) -> pygame.Surface:
        s = to_surface(self.cells)
        if self.opaque:
            out = pygame.Surface((N, N))
            out.blit(s, (0, 0))
            return out
        return s

    def save(self):
        self.on_save(self.picture())
        self.dirty = False

    def close(self):
        if self.dirty:
            from tkinter import messagebox
            ans = messagebox.askyesnocancel('Picture', 'Keep the changes to this picture?', parent=self)
            if ans is None:
                return
            if ans:
                self.save()
        self.destroy()


def _line(a, b):
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0))
    return [(x0 + round((x1 - x0) * k / n), y0 + round((y1 - y0) * k / n)) for k in range(n + 1)] if n else [a]


def _rect(a, b):
    (x0, y0), (x1, y1) = a, b
    return [(x, y) for x in range(min(x0, x1), max(x0, x1) + 1) for y in range(min(y0, y1), max(y0, y1) + 1)]
