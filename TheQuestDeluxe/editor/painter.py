"""The picture painter: 40 x 40 pictures in the game's 16 EGA colours (and transparent, for pictures
drawn over the floor).

Pencil: left button paints, right button
   undoes a pixel (puts back what it was)
Eraser: right button deletes a pixel,
   left button undoes it
Dither: paint a chequer of both colours
Line: drag from one end to the other
Rectangle, Oval: drag a shape (Filled box: solid or outline)
Fill: fill the area of one colour
Swap: change every pixel of one colour
Select: drag a box, then Copy / Cut / Paste
   (Ctrl+C, Ctrl+X, Ctrl+V; Delete clears it)
Pick: take a colour from the picture
   (Alt+click does this with any tool)
Pictures from the palette: drag one onto
   the picture to stamp it, double-click to
   start from it.

Left button paints the left colour (Line,
Rectangle, Oval, Fill ...: the right button
paints the right colour).
Mirror paints both halves at once.
Ctrl+Z / Ctrl+Y undo and redo.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pygame

from .art import EGA, photo
from .uikit import tip

N = 40
ZOOMS = (8, 12, 16)
CLEAR = -1
GRIDS = ['No lines', 'Every 10 pixels', 'Every pixel']
CLIPBOARD: dict = {'cells': None}              # what Copy took, shared by every painter window
# what shows behind the see-through pixels: (label, colour as '#rrggbb' or None for the chequer)
BACKGROUNDS = [('Chequer (see-through)', None), ('Flat grey (no squares)', '#c8c8c8'), ('Grass', '#00a800'), ('Black', '#000000'), ('White', '#ffffff'),
               ('Grey', '#808080'), ('Sand', '#a8a800')]


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
    def __init__(self, master, title: str, surface, on_save, opaque: bool = False, templates=None, project=None, folder=None):
        """opaque: every pixel has a colour (floors, bag cells); otherwise transparent is a colour too.
        templates: [(name, function returning a picture)] the painter can start from."""
        super().__init__(master)
        self.templates = list(templates or [])
        self.project, self.folder = project, folder      # its pictures fill the palette, opening on this folder's kind
        self.selection = None                   # (x0, y0, x1, y1) of the Select tool's box
        self.last_cell = None
        self.title(title)
        self.on_save, self.opaque = on_save, opaque
        self.cells = to_cells(surface, opaque)
        self.left, self.right = 15, (0 if opaque else CLEAR)
        self.tool = tk.StringVar(value='pencil')
        self.zoom = 12
        self.background = tk.StringVar(value=BACKGROUNDS[0][0])     # behind the see-through pixels
        self.grid_mode = tk.StringVar(value=GRIDS[0])
        self.filled = tk.BooleanVar(value=True)
        self.mirror = tk.BooleanVar(value=False)
        self.ghost = tk.BooleanVar(value=False)                     # the picture as it was, faintly, where it is clear
        self.original = [col[:] for col in self.cells]
        self.undo_stack, self.redo_stack = [], []
        self.start = None
        self.before = None
        self.dirty = False
        self._build()
        from .tips import apply as apply_tips
        apply_tips(self)
        tip(self.canvas, 'Pencil: the left button paints, the right button undoes the pixel. Eraser: the right button '
                         'deletes, the left undoes. Other tools: left and right paint the two colours. '
                         'Alt+click picks the colour under the pointer. Ctrl+Z / Ctrl+Y undo and redo.')
        self.redraw()
        self.bind('<Control-z>', lambda e: self.undo())
        self.bind('<Control-y>', lambda e: self.redo())
        self.bind('<Control-c>', lambda e: self.copy())
        self.bind('<Control-x>', lambda e: self.cut())
        self.bind('<Control-v>', lambda e: self.paste())
        self.bind('<Delete>', lambda e: self.delete_selection())
        self.protocol('WM_DELETE_WINDOW', self.close)
        from .uikit import center
        center(self, parent=master.winfo_toplevel())

    # ── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        left = ttk.Frame(self, padding=6)
        left.pack(side='left', fill='y')
        tools = ttk.LabelFrame(left, text='Tool', padding=4)
        tools.pack(fill='x')
        row = [('pencil', 'Pencil'), ('line', 'Line'), ('rect', 'Rectangle'), ('oval', 'Oval'), ('fill', 'Fill'),
               ('swap', 'Swap'), ('dither', 'Dither'), ('select', 'Select'), ('pick', 'Pick')]
        if not self.opaque:
            row.insert(1, ('eraser', 'Eraser'))
        for i, (k, label) in enumerate(row):
            ttk.Radiobutton(tools, text=label, value=k, variable=self.tool).grid(row=i // 2, column=i % 2, sticky='w',
                                                                               padx=(0, 8))
        opts = ttk.Frame(tools)
        opts.grid(row=(len(row) + 1) // 2, column=0, columnspan=2, sticky='w', pady=(4, 0))
        for text, var, words in (
                ('Filled', self.filled, 'Rectangles and ovals are solid (ticked) or just an outline.'),
                ('Mirror', self.mirror, 'Everything you paint is copied to the other side, left to right (faces, '
                                        'shields, swords).')):
            c = ttk.Checkbutton(opts, text=text, variable=var)
            c.pack(side='left', padx=(0, 8))
            tip(c, words)
        pal = ttk.LabelFrame(left, text='Colours', padding=4)
        pal.pack(fill='x', pady=6)
        choices = list(range(16)) + ([] if self.opaque else [CLEAR])
        for i, c in enumerate(choices):
            sw = tk.Canvas(pal, width=26, height=26, highlightthickness=1, highlightbackground='#888')
            self._swatch(sw, c)
            sw.grid(row=i // 8, column=i % 8, padx=1, pady=1)
            sw.bind('<Button-1>', lambda e, c=c: self._choose(c, 'left'))
            sw.bind('<Button-3>', lambda e, c=c: self._choose(c, 'right'))
        ttk.Label(pal, text='left / right click a colour to choose it', foreground='#555').grid(
            row=3, column=0, columnspan=8, pady=2)
        view = ttk.LabelFrame(left, text='View', padding=4)
        view.pack(fill='x', pady=(0, 6))
        ttk.Label(view, text='Background').grid(row=0, column=0, sticky='w')
        bg = ttk.Combobox(view, textvariable=self.background, state='readonly', width=20,
                          values=[name for name, _ in BACKGROUNDS])
        bg.grid(row=0, column=1, sticky='w')
        bg.bind('<<ComboboxSelected>>', lambda e: self.redraw())
        tip(bg, 'What shows behind the see-through pixels while you paint and in the small pictures: the chequer, '
                'or a ground colour to see how it will look standing on it. It is never saved.')
        ttk.Label(view, text='Zoom').grid(row=1, column=0, sticky='w')
        zoom = ttk.Combobox(view, state='readonly', width=6, values=[f'{z * N} px' for z in ZOOMS])
        zoom.set(f'{self.zoom * N} px')
        zoom.grid(row=1, column=1, sticky='w')
        zoom.bind('<<ComboboxSelected>>', lambda e: self.set_zoom(ZOOMS[zoom.current()]))
        tip(zoom, 'How big the picture is while you paint.')
        ttk.Label(view, text='Lines').grid(row=2, column=0, sticky='w')
        lines = ttk.Combobox(view, textvariable=self.grid_mode, state='readonly', width=16, values=GRIDS)
        lines.grid(row=2, column=1, sticky='w')
        lines.bind('<<ComboboxSelected>>', lambda e: self.redraw())
        tip(lines, 'The lines on the picture while you paint: none, every 10 pixels, or round every pixel.')
        marks = ttk.Frame(view)
        marks.grid(row=3, column=0, columnspan=2, sticky='w')
        for text, var, words in (('Compare with the first', self.ghost,
                                  'Every pixel you have changed since you opened this window shows half way to what it '
                                  'was, so you can see what you did; unchanged pixels look as they are.'),):
            c = ttk.Checkbutton(marks, text=text, variable=var, command=self.redraw)
            c.pack(side='left', padx=(0, 8))
            tip(c, words)
        cur = ttk.Frame(left)
        cur.pack(fill='x')
        ttk.Label(cur, text='Left').pack(side='left')
        self.lsw = tk.Canvas(cur, width=26, height=26)
        self.lsw.pack(side='left', padx=4)
        ttk.Label(cur, text='Right').pack(side='left')
        self.rsw = tk.Canvas(cur, width=26, height=26)
        self.rsw.pack(side='left', padx=4)
        moves = ttk.LabelFrame(left, text='Move, flip, turn', padding=4)
        moves.pack(fill='x', pady=6)
        for i, (label, words, fn) in enumerate((
                ('\u25c0', 'Move the picture one pixel left.', lambda: self.shift(-1, 0)),
                ('\u25b2', 'Move the picture one pixel up.', lambda: self.shift(0, -1)),
                ('\u25bc', 'Move the picture one pixel down.', lambda: self.shift(0, 1)),
                ('\u25b6', 'Move the picture one pixel right.', lambda: self.shift(1, 0)),
                ('\u2194', 'Flip left to right.', lambda: self.flip(True)),
                ('\u2195', 'Flip top to bottom.', lambda: self.flip(False)),
                ('\u21bb', 'Turn a quarter clockwise.', lambda: self.turn(True)),
                ('\u21ba', 'Turn a quarter anticlockwise.', lambda: self.turn(False)))):
            b = ttk.Button(moves, text=label, width=4, command=fn)
            b.grid(row=i // 4, column=i % 4, padx=1, pady=1)
            tip(b, words)
        clip = ttk.LabelFrame(left, text='Copy and paste', padding=4)
        clip.pack(fill='x', pady=(0, 6))
        for i, (label, words, fn) in enumerate((
                ('Copy', 'Copy the selected box (the whole picture if none is selected). Other painter windows can paste it.', self.copy),
                ('Cut', 'Copy the selected box and clear it.', self.cut),
                ('Paste', 'Paste what was copied: at the pointer, or the top left. See-through parts leave what is under them.', self.paste))):
            b = ttk.Button(clip, text=label, width=7, command=fn)
            b.grid(row=0, column=i, padx=1)
            tip(b, words)
        ttk.Button(left, text='Clear', command=self.clear).pack(fill='x')
        if self.templates:
            box = ttk.LabelFrame(left, text='Start from another picture', padding=4)
            box.pack(fill='x', pady=6)
            self.template = tk.StringVar()
            ttk.Combobox(box, textvariable=self.template, state='readonly', width=22,
                         values=[name for name, _ in self.templates]).pack(fill='x')
            ttk.Button(box, text='Use it (Undo goes back)', command=self.use_template).pack(fill='x', pady=2)
        ends = ttk.Frame(left)
        ends.pack(fill='x', pady=(8, 0))
        ttk.Button(ends, text='Save', command=self.save).pack(side='left', fill='x', expand=True, padx=(0, 2))
        ttk.Button(ends, text='Close', command=self.close).pack(side='left', fill='x', expand=True)

        mid = ttk.Frame(self, padding=6)
        mid.pack(side='left')
        self.canvas = tk.Canvas(mid, highlightthickness=0, background='#333')
        self.canvas.pack()
        self._make_canvas()
        for b, which in (('1', 'left'), ('3', 'right')):
            self.canvas.bind(f'<ButtonPress-{b}>', lambda e, w=which: self._press(e, w))
            # Alt+click picks a colour. Asked of the event's modifier bits this was wrong on Windows, where
            # bit 0x8 is Num Lock: with it on, every click was a pick and nothing could be painted.
            self.canvas.bind(f'<Alt-ButtonPress-{b}>', lambda e, w=which: self._press(e, w, alt=True))
            self.canvas.bind(f'<B{b}-Motion>', lambda e, w=which: self._drag(e, w))
            self.canvas.bind(f'<ButtonRelease-{b}>', lambda e, w=which: self._release(e, w))
        self.status = ttk.Label(mid, text='')
        self.status.pack(anchor='w')
        self.canvas.bind('<Motion>', self._motion)

        right = ttk.Frame(self, padding=6)
        right.pack(side='left', fill='y')
        ttk.Label(right, text='As it looks').pack(anchor='w')
        self.previews = ttk.Label(right)
        self.previews.pack(anchor='w')
        self.palette = None
        if self.project is not None:
            from .palette import PicturePalette
            self.palette = PicturePalette(right, self.project, self.drop, self.start_from, self.folder)
            self.palette.pack(fill='x', pady=6)
        ttk.Button(right, text='How to paint...', command=self.help).pack(anchor='w')

    def _make_canvas(self):
        z = self.zoom
        self.canvas.delete('all')
        self.canvas.config(width=N * z, height=N * z)
        self.rects = [[self.canvas.create_rectangle(x * z, y * z, x * z + z, y * z + z, width=0)
                       for y in range(N)] for x in range(N)]
        self.fine, self.lines = [], []                  # the lines round every pixel, the ones every 10
        for k in range(N + 1):
            ten = k % 10 == 0
            for coords in ((k * z, 0, k * z, N * z), (0, k * z, N * z, k * z)):
                (self.lines if ten else self.fine).append(
                    self.canvas.create_line(*coords, fill='#555' if ten else '#888'))
        self.sel_box = self.canvas.create_rectangle(0, 0, 0, 0, outline='#ff00ff', width=2, dash=(4, 3), state='hidden')

    def set_zoom(self, z):
        self.zoom = z
        self._make_canvas()
        self.redraw()

    def back_colour(self, x, y):
        """What shows at a see-through pixel: the chosen background, or the chequer."""
        colour = dict(BACKGROUNDS).get(self.background.get())
        if colour:
            return colour
        return '#ffffff' if (x + y) % 2 else '#cccccc'

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
        mode = self.grid_mode.get()
        for line in self.lines:
            self.canvas.itemconfig(line, state='normal' if mode != GRIDS[0] else 'hidden')
        for line in self.fine:
            self.canvas.itemconfig(line, state='normal' if mode == GRIDS[2] else 'hidden')
        self.canvas.tag_raise(self.sel_box)
        self._show_selection()
        self.redraw_swatches()
        self._preview()

    def _paint_rect(self, x, y):
        c = self.cells[x][y]
        fill = self.back_colour(x, y) if c == CLEAR else '#%02x%02x%02x' % EGA[c]
        old = self.original[x][y]
        if self.ghost.get() and c != old:                    # Compare: changed pixels show half way to what they were
            back = tuple(v // 257 for v in self.canvas.winfo_rgb(self.back_colour(x, y)))
            now = back if c == CLEAR else EGA[c]
            was = back if old == CLEAR else EGA[old]
            fill = '#%02x%02x%02x' % tuple((a + b) // 2 for a, b in zip(now, was))
        self.canvas.itemconfig(self.rects[x][y], fill=fill)

    def _preview(self):
        img = to_surface(self.cells)
        s = pygame.Surface((4 + 40 * 3 + 8 + 40 * 2, 4 + 40 * 3))
        s.fill((80, 80, 80))
        back = dict(BACKGROUNDS).get(self.background.get()) or '#00a800'
        shown = tuple(int(back[i:i + 2], 16) for i in (1, 3, 5))
        for n, (bg, scale) in enumerate(((shown, 3), ((0, 0, 0), 2))):
            x = 2 if n == 0 else 4 + 40 * 3 + 6
            tile = pygame.Surface((40, 40))
            tile.fill(bg)
            tile.blit(img, (0, 0))
            s.blit(pygame.transform.scale(tile, (40 * scale, 40 * scale)), (x, 2))
        self._pimg = photo(s)
        self.previews.config(image=self._pimg)

    # ── editing ─────────────────────────────────────────────────────────────
    def _cell(self, e):
        x, y = e.x // self.zoom, e.y // self.zoom
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
        for px in ({x, N - 1 - x} if self.mirror.get() else {x}):          # Mirror: the other side too
            if self.cells[px][y] != c:
                self.cells[px][y] = c
                self._paint_rect(px, y)

    def _ink(self, tool, x, y, colour, which='left'):
        """The colour a freehand tool puts on pixel (x, y). The pencil: the left button paints, the right button
        undoes the pixel (puts back what the picture had when this window opened). The eraser: the right button
        deletes the pixel, the left button undoes it."""
        if tool == 'eraser':
            return CLEAR if which == 'right' else self.original[x][y]
        if tool == 'pencil' and which == 'right':
            return self.original[x][y]
        if tool == 'dither':
            return self.left if (x + y) % 2 == 0 else self.right
        return colour

    def _pen(self, tool, x, y, colour, which):
        """A freehand tool on pixel (x, y), and on the mirrored one (with its own undo)."""
        for px in ({x, N - 1 - x} if self.mirror.get() else {x}):
            c = self._ink(tool, px, y, colour, which)
            if self.cells[px][y] != c:
                self.cells[px][y] = c
                self._paint_rect(px, y)

    def _press(self, e, which, alt=False):
        p = self._cell(e)
        if p is None:
            return
        colour = getattr(self, which)
        tool = 'pick' if alt else self.tool.get()
        if tool == 'pick':
            setattr(self, which, self.cells[p[0]][p[1]])
            self.redraw_swatches()
            return
        if tool == 'select':
            self.start, self.selection = p, (*p, *p)
            self._show_selection()
            return
        self._remember()
        self.start = p
        if tool in ('pencil', 'eraser', 'dither'):
            self._pen(tool, p[0], p[1], colour, which)
        elif tool == 'fill':
            self._flood(*p, colour)
            self._commit()
        elif tool == 'swap':
            old = self.cells[p[0]][p[1]]
            for x in range(N):
                for y in range(N):
                    if self.cells[x][y] == old:
                        self._set(x, y, colour)
            self._commit()

    def _drag(self, e, which):
        p = self._cell(e)
        if p is None or self.start is None:
            return
        tool, colour = self.tool.get(), getattr(self, which)
        if tool == 'select':
            self.selection = (*self.start, *p)
            self._show_selection()
            return
        if tool in ('pencil', 'eraser', 'dither'):
            for q in _line(self.start, p):
                self._pen(tool, q[0], q[1], colour, which)
            self.start = p
        elif tool in ('line', 'rect', 'oval'):
            self.cells = [col[:] for col in self.before]
            filled = self.filled.get()
            shape = (_line(self.start, p) if tool == 'line' else _rect(self.start, p, filled) if tool == 'rect'
                     else _oval(self.start, p, filled))
            mirror = self.mirror.get()
            for q in shape:
                for x in ({q[0], N - 1 - q[0]} if mirror else {q[0]}):
                    self.cells[x][q[1]] = colour
            self.redraw()

    def _release(self, e, which):
        if self.start is None:
            return
        tool = self.tool.get()
        if tool == 'select':
            self.start = None
            return
        if tool in ('line', 'rect', 'oval'):
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

    def help(self):
        from tkinter import messagebox
        messagebox.showinfo('Painting', __doc__.split('\n\n', 1)[1].strip(), parent=self)

    # ── select, copy and paste, pictures from the palette ──────────────────
    def _motion(self, e):
        self.last_cell = self._cell(e)
        self.status.config(text=f'({e.x // self.zoom}, {e.y // self.zoom})')

    def _box(self):
        """The Select tool's box as (x0, y0, x1, y1) with x0 <= x1, y0 <= y1, or None."""
        if self.selection is None:
            return None
        x0, y0, x1, y1 = self.selection
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    def _show_selection(self):
        box = self._box()
        if box is None:
            self.canvas.itemconfig(self.sel_box, state='hidden')
            return
        z = self.zoom
        self.canvas.coords(self.sel_box, box[0] * z, box[1] * z, (box[2] + 1) * z, (box[3] + 1) * z)
        self.canvas.itemconfig(self.sel_box, state='normal')
        self.canvas.tag_raise(self.sel_box)

    def copy(self):
        """Copy the selected box, or the whole picture when nothing is selected."""
        x0, y0, x1, y1 = self._box() or (0, 0, N - 1, N - 1)
        CLIPBOARD['cells'] = [[self.cells[x][y] for y in range(y0, y1 + 1)] for x in range(x0, x1 + 1)]
        self.status.config(text=f'Copied {x1 - x0 + 1} x {y1 - y0 + 1} pixels')

    def cut(self):
        self.copy()
        self.delete_selection(whole=True)

    def delete_selection(self, whole=False):
        """Clear the selected box (to see-through, or black where nothing can be see-through)."""
        box = self._box() or ((0, 0, N - 1, N - 1) if whole else None)
        if box is None:
            return
        self._remember()
        empty = 0 if self.opaque else CLEAR
        for x in range(box[0], box[2] + 1):
            for y in range(box[1], box[3] + 1):
                self.cells[x][y] = empty
        self._commit()
        self.redraw()

    def paste(self):
        """Paste what was copied, its top left at the pointer (or at the selection, or the corner)."""
        cells = CLIPBOARD['cells']
        if not cells:
            self.status.config(text='Nothing copied yet')
            return
        at = (self._box() or (0, 0))[:2] if self.selection is not None else (self.last_cell or (0, 0))
        self._stamp(cells, *at)

    def _stamp(self, cells, x0, y0):
        """Lay a block of colours (-1: see-through, leaves what is there) on the picture, its corner at (x0, y0)."""
        self._remember()
        for i, col in enumerate(cells):
            for j, c in enumerate(col):
                x, y = x0 + i, y0 + j
                if c != CLEAR and 0 <= x < N and 0 <= y < N:
                    self.cells[x][y] = c
        self._commit()
        self.redraw()

    def drop(self, surface, root_x, root_y):
        """A palette picture let go at a point of the screen: stamped on the picture, centred there."""
        x = (root_x - self.canvas.winfo_rootx()) // self.zoom
        y = (root_y - self.canvas.winfo_rooty()) // self.zoom
        if not (-N // 2 <= x < N + N // 2 and -N // 2 <= y < N + N // 2) or \
                not (0 <= root_x - self.canvas.winfo_rootx() < N * self.zoom and
                     0 <= root_y - self.canvas.winfo_rooty() < N * self.zoom):
            return                                   # let go somewhere else: nothing happens
        cells = to_cells(surface, False)
        self._stamp(cells, x - N // 2, y - N // 2)

    def start_from(self, surface):
        """Start the picture as a copy of a palette picture (Undo goes back)."""
        self._remember()
        self.cells = to_cells(surface, self.opaque)
        self._commit()
        self.redraw()

    def turn(self, clockwise):
        """A quarter turn (the picture is square)."""
        self._remember()
        if clockwise:
            self.cells = [[self.cells[y][N - 1 - x] for y in range(N)] for x in range(N)]
        else:
            self.cells = [[self.cells[N - 1 - y][x] for y in range(N)] for x in range(N)]
        self._commit()
        self.redraw()

    def use_template(self):
        """Replace what is painted with another picture, to change it into this one."""
        name = self.template.get()
        make = next((m for n, m in self.templates if n == name), None)
        picture = make() if make else None
        if picture is None:
            return
        self._remember()
        self.cells = to_cells(picture, self.opaque)
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


def _rect(a, b, filled=True):
    (x0, y0), (x1, y1) = a, b
    lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    return [(x, y) for x in range(lo_x, hi_x + 1) for y in range(lo_y, hi_y + 1)
            if filled or x in (lo_x, hi_x) or y in (lo_y, hi_y)]


def _oval(a, b, filled=True):
    """The pixels of the oval that fills the box from a to b: all of them, or just its outline."""
    (x0, y0), (x1, y1) = a, b
    lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    cx, cy = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
    rx, ry = (hi_x - lo_x) / 2 + 0.5, (hi_y - lo_y) / 2 + 0.5

    def inside(x, y):
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
    solid = {(x, y) for x in range(lo_x, hi_x + 1) for y in range(lo_y, hi_y + 1) if inside(x, y)}
    if filled:
        return sorted(solid)
    return sorted(q for q in solid if any((q[0] + dx, q[1] + dy) not in solid
                                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
