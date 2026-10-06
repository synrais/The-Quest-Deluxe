"""The picture painter in the Studio's own look: the painting itself is done by studio/paintbase.py, laid
out with icon tools, big colour swatches, the picture standing on the pack's floors beside it, and the pack's other pictures
to start from.

    B pencil   E eraser   L line   R rectangle   O oval   G fill   D dither   W swap colour   S select   I pick   X swap left and right
    Ctrl+Z / Ctrl+Y undo and redo     Ctrl+C / Ctrl+X / Ctrl+V copy, cut and paste
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from studio.art import EGA
from studio.paintbase import BACKGROUNDS, CLEAR, GRIDS, N, SLOTS, Painter

from . import icons, theme, ui
from .theme import C, px

TOOLS = [('pencil', 'brush', 'B', 'Pencil: the left button paints, the right button undoes the pixel (puts back what was there).'),
         ('eraser', 'eraser', 'E', 'Eraser: the right button deletes a pixel, the left button undoes it.'),
         ('line', 'line', 'L', 'Line: drag from one end to the other.'),
         ('rect', 'rect', 'R', 'Rectangle: drag a box (solid, or just the outline if Filled is off).'),
         ('oval', 'oval', 'O', 'Oval: drag a box for it to fill (solid, or an outline).'),
         ('fill', 'bucket', 'G', 'Fill: colour the whole area of one colour.'),
         ('dither', 'dither', 'D', 'Dither: paint a chequer of both colours, for shading.'),
         ('swap', 'swap', 'W', 'Swap: change every pixel of one colour to the painting colour.'),
         ('select', 'select', 'S', 'Select: drag a box, then Copy or Cut. Delete clears it.'),
         ('pick', 'picker', 'I', 'Pick: take a colour from the picture. (Alt+click does this with any tool.)')]
COLOUR_NAMES = ['Black', 'Blue', 'Green', 'Cyan', 'Red', 'Magenta', 'Brown', 'Light grey', 'Dark grey', 'Light blue', 'Light green',
                'Light cyan', 'Light red', 'Light magenta', 'Yellow', 'White']
SIZES = [(8, 'Small'), (12, 'Medium'), (16, 'Large')]


class StudioPainter(Painter):
    """Everything the old painter does, in the Studio's look. Same arguments, same results."""

    def __init__(self, master, title, surface, on_save, opaque=False, templates=None, project=None, folder=None):
        self.tool_buttons = {}
        self.swatches = {}
        super().__init__(master, title, surface, on_save, opaque, templates, project, folder)
        self._tool_chosen(self.tool.get())

    # ── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        self.configure(bg=C['bg'])
        self.zoom = px(12)
        self.minsize(px(980), px(620))
        foot = ttk.Frame(self, padding=(px(14), px(8)))
        foot.pack(side='bottom', fill='x')
        ui.hsep(self).pack(side='bottom', fill='x')
        self.status = ttk.Label(foot, text='', style='Dim.TLabel')
        self.status.pack(side='left')
        ui.button(foot, 'Save', self.save, 'save', 'Accent.TButton', 'Keep the picture (Ctrl+S)').pack(side='right')
        ttk.Button(foot, text='Close', command=self.close).pack(side='right', padx=px(8))
        ttk.Button(foot, text='How to paint…', command=self.help, style='Small.TButton').pack(side='right', padx=(0, px(8)))
        self.bind('<Control-s>', lambda e: self.save())
        top = ttk.Frame(self)
        top.pack(fill='both', expand=True)
        left = ttk.Frame(top, width=px(252))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        self._tools_panel(left)
        ui.vsep(top).pack(side='left', fill='y')
        right = ttk.Frame(top)
        right.pack(side='right', fill='y')
        self.mid = ttk.Frame(top)
        ui.vsep(top).pack(side='right', fill='y')
        self.mid.pack(side='left', fill='both', expand=True, padx=px(14), pady=px(10))
        self._picture_panel(self.mid)
        self._right_panel(right)
        for ch, tool in [(k[2].lower(), k[0]) for k in TOOLS]:
            self.bind(f'<KeyPress-{ch}>', lambda e, t=tool: self._key_tool(t))
        self.bind('<KeyPress-x>', lambda e: self._swap_sides() if self._not_typing() else None)

    def _not_typing(self):
        try:
            return not isinstance(self.focus_get(), (ttk.Entry, tk.Entry, ttk.Combobox))
        except KeyError:                                           # Tk names a combobox's pop-up list oddly
            return False

    def _key_tool(self, tool):
        if self._not_typing() and (tool != 'eraser' or not self.opaque):
            self._tool_chosen(tool)

    def _head(self, parent, text, first=False):
        ttk.Label(parent, text=text, style='Faint.TLabel', font=(theme.FONT, 8, 'bold')).pack(anchor='w', padx=px(14),
                                                                                              pady=(px(6) if first else px(12), px(3)))

    def _tools_panel(self, left):
        self._head(left, 'TOOLS', first=True)
        grid = ttk.Frame(left)
        grid.pack(anchor='w', padx=px(12))
        tools = [t for t in TOOLS if not (self.opaque and t[0] == 'eraser')]
        for i, (key, icon, letter, words) in enumerate(tools):
            b = ttk.Button(grid, style='Tool.TButton', takefocus=0, width=3, command=lambda k=key: self._tool_chosen(k))
            b.grid(row=i // 5, column=i % 5, padx=1, pady=1)
            ui.tip(b, f'{words}  ({letter})')
            self.tool_buttons[key] = (b, icon)
        opts = ttk.Frame(left)
        opts.pack(fill='x', padx=px(14), pady=(px(8), 0))
        for text, var, words in (('Filled', self.filled, 'Rectangles and ovals are solid (on) or just an outline (off).'),
                                 ('Mirror', self.mirror, 'Everything you paint is copied to the other side, left to right: faces, shields, swords.')):
            row = ttk.Frame(opts)
            row.pack(fill='x', pady=1)
            lab = ttk.Label(row, text=text)
            lab.pack(side='left')
            ui.tip(lab, words)
            ui.Switch(row, var.get(), lambda v, var=var: var.set(v)).pack(side='right')
        self._head(left, 'COLOURS')
        cur = ttk.Frame(left)
        cur.pack(anchor='w', padx=px(14))
        self.cur = tk.Canvas(cur, width=px(60), height=px(52), bg=C['panel'], highlightthickness=0, cursor='hand2')
        self.cur.pack(side='left')
        self.cur.bind('<Button-1>', lambda e: self._swap_sides())
        ui.tip(self.cur, 'The two painting colours: left button (front) and right button (behind). Click to swap them (X).')
        ttk.Label(cur, text='left button\nright button', style='Faint.TLabel', justify='left').pack(side='left', padx=px(10))
        pal = ttk.Frame(left)
        pal.pack(anchor='w', padx=px(12), pady=(px(6), 0))
        choices = list(range(16)) + ([] if self.opaque else [CLEAR])
        size = px(28)
        for i, c in enumerate(choices):
            sw = tk.Canvas(pal, width=size, height=size, highlightthickness=2, bd=0, cursor='hand2', highlightbackground=C['line'])
            self._swatch(sw, c)
            sw.grid(row=i // 6, column=i % 6, padx=1, pady=1)
            sw.bind('<Button-1>', lambda e, c=c: self._choose(c, 'left'))
            sw.bind('<Button-3>', lambda e, c=c: self._choose(c, 'right'))
            ui.tip(sw, ('See-through' if c == CLEAR else COLOUR_NAMES[c]) + ': left click paints with it, right click sets the other colour.')
            self.swatches[c] = sw
        self._head(left, 'MOVE, FLIP AND TURN')
        row = ttk.Frame(left)
        row.pack(anchor='w', padx=px(12))
        for i, (icon, words, fn) in enumerate((
                ('left', 'Move the picture one pixel left.', lambda: self.shift(-1, 0)),
                ('up', 'Move the picture one pixel up.', lambda: self.shift(0, -1)),
                ('down', 'Move the picture one pixel down.', lambda: self.shift(0, 1)),
                ('right', 'Move the picture one pixel right.', lambda: self.shift(1, 0)),
                ('flip_h', 'Flip left to right.', lambda: self.flip(True)),
                ('flip_v', 'Flip top to bottom.', lambda: self.flip(False)),
                ('turn_cw', 'Turn a quarter clockwise.', lambda: self.turn(True)),
                ('turn_ccw', 'Turn a quarter anticlockwise.', lambda: self.turn(False)))):
            b = ui.button(row, '', fn, icon, 'Tool.TButton', words)
            b.grid(row=i // 4, column=i % 4, padx=1, pady=1)
        self._head(left, 'EDIT')
        row = ttk.Frame(left)
        row.pack(anchor='w', padx=px(12))
        for i, (icon, words, fn) in enumerate((
                ('undo', 'Undo (Ctrl+Z).', self.undo), ('redo', 'Redo (Ctrl+Y).', self.redo),
                ('copy', 'Copy the selected box (the whole picture if none is selected). Other painter windows can paste it.', self.copy),
                ('cut', 'Copy the selected box and clear it.', self.cut),
                ('paste', 'Paste what was copied: at the pointer, or the top left. See-through parts leave what is under them.', self.paste),
                ('trash', 'Clear the whole picture. Undo brings it back.', self.clear))):
            ui.button(row, '', fn, icon, 'Tool.TButton', words).grid(row=0, column=i, padx=1)

    def _picture_panel(self, mid):
        stage = ttk.Frame(mid)
        stage.pack(anchor='n')
        self.canvas = tk.Canvas(stage, highlightthickness=1, highlightbackground=C['line'], background=C['canvas'], cursor='crosshair')
        self.canvas.pack(side='left', anchor='n')
        self._make_canvas()
        for b, which in (('1', 'left'), ('3', 'right')):
            self.canvas.bind(f'<ButtonPress-{b}>', lambda e, w=which: self._press(e, w))
            # Alt+click picks a colour (asked by name: bit 0x8 of the event state is Num Lock on Windows)
            self.canvas.bind(f'<Alt-ButtonPress-{b}>', lambda e, w=which: self._press(e, w, alt=True))
            self.canvas.bind(f'<B{b}-Motion>', lambda e, w=which: self._drag(e, w))
            self.canvas.bind(f'<ButtonRelease-{b}>', lambda e, w=which: self._release(e, w))
        self.canvas.bind('<Motion>', self._motion)
        self.small, self.big = [], []
        words = ('How the picture looks standing on each floor, as you paint. Click one to choose which floor it stands on (or black). '
                 'A picture with no see-through pixels is shown tiled instead, to check that its edges meet.')
        side = ttk.Frame(stage)
        side.pack(side='left', anchor='n', padx=(px(14), 0))
        if self.opaque:
            ttk.Label(side, text='TILED AND ON ITS OWN', style='Faint.TLabel', font=(theme.FONT, 8, 'bold')).pack(anchor='w')
            self.previews = ttk.Label(side)
            self.previews.pack(anchor='w', pady=(px(4), 0))
            ui.tip(self.previews, words)
        else:
            ttk.Label(side, text='ON THE FLOORS  (click to change)', style='Faint.TLabel', font=(theme.FONT, 8, 'bold')).pack(anchor='w')
            grid = ttk.Frame(side)
            grid.pack(anchor='w', pady=(px(4), 0))
            hidden = ttk.Frame(self)                                  # the small previews the old painter draws: not shown here
            for i in range(SLOTS):
                small = ttk.Label(hidden)
                self.small.append(small)
                lab = ttk.Label(grid, cursor='hand2')
                lab.grid(row=i // 2, column=i % 2, padx=1, pady=1)
                lab.bind('<Button-1>', lambda e, i=i: self._slot_menu(i, e))
                ui.tip(lab, words)
                self.big.append(lab)
        view = ttk.Frame(mid)
        view.pack(anchor='w', fill='x', pady=(px(10), 0))
        ttk.Label(view, text='Size').pack(side='left')
        sizes = ui.Segmented(view, [(str(z), name) for z, name in SIZES], lambda k: self.set_zoom(px(int(k))), '12')
        sizes.pack(side='left', padx=(px(8), px(18)))
        ttk.Label(view, text='Behind').pack(side='left')
        bg = ttk.Combobox(view, textvariable=self.background, state='readonly', width=20, values=[n for n, _ in BACKGROUNDS])
        bg.pack(side='left', padx=(px(8), px(14)))
        bg.bind('<<ComboboxSelected>>', lambda e: self.redraw())
        ui.tip(bg, 'What shows behind the see-through pixels while you paint and in the small pictures: the chequer, or a ground colour to see '
                   'how it will look standing on it. It is never saved.')
        view2 = ttk.Frame(mid)
        view2.pack(anchor='w', fill='x', pady=(px(8), 0))
        ttk.Label(view2, text='Lines').pack(side='left')
        lines = ttk.Combobox(view2, textvariable=self.grid_mode, state='readonly', width=16, values=GRIDS)
        lines.pack(side='left', padx=(px(8), px(18)))
        lines.bind('<<ComboboxSelected>>', lambda e: self.redraw())
        ui.tip(lines, 'The lines on the picture while you paint: none, every 10 pixels, or round every pixel.')
        cmp_ = ttk.Label(view2, text='Show what I changed')
        cmp_.pack(side='left')
        ui.tip(cmp_, 'Every pixel you have changed since you opened this window shows half way to what it was, so you can see what you did.')
        ui.Switch(view2, self.ghost.get(), lambda v: (self.ghost.set(v), self.redraw())).pack(side='left', padx=px(8))

    def _right_panel(self, right):
        self.palette = None
        if self.templates:
            box = ttk.Frame(right)
            box.pack(fill='x', padx=px(12), pady=(px(10), 0))
            ttk.Label(box, text='CHANGE IT INTO', style='Faint.TLabel', font=(theme.FONT, 8, 'bold')).pack(anchor='w')
            self.template = tk.StringVar()
            row = ttk.Frame(box)
            row.pack(fill='x', pady=(px(4), 0))
            ttk.Combobox(row, textvariable=self.template, state='readonly', width=18, values=[n for n, _ in self.templates]).pack(side='left')
            ttk.Button(row, text='Use it', command=self.use_template, style='Small.TButton').pack(side='left', padx=px(6))
            ui.tip(row, 'Replace what is painted with another picture to change it into this one. Undo goes back.')
        if self.project is not None:
            from studio.palette import PicturePalette
            self.palette = PicturePalette(right, self.project, self.drop, self.start_from, self.folder)
            self.palette.pack(fill='both', expand=True, padx=px(8), pady=px(8))
            self.palette.canvas.configure(background=C['canvas'])
            self.palette.name.configure(foreground=C['faint'])

    def _align_palette(self):
        pass

    # ── tools and colours ───────────────────────────────────────────────────
    def _tool_chosen(self, key):
        if key not in self.tool_buttons:
            key = 'pencil'
        self.tool.set(key)
        for k, (b, icon) in self.tool_buttons.items():
            on = k == key
            b.configure(style='ToolOn.TButton' if on else 'Tool.TButton',
                        image=icons.icon(icon, C['accent_text'] if on else C['text'], px(18)))

    def _swap_sides(self):
        self.left, self.right = self.right, self.left
        self.redraw_swatches()

    def _swatch(self, canvas, c):
        canvas.delete('all')
        w = int(canvas.cget('width')) or px(28)
        h = int(canvas.cget('height')) or px(28)
        if c == CLEAR:
            canvas.create_rectangle(0, 0, w, h, fill='#bbbbbb', width=0)
            for i in range(4):
                for j in range(4):
                    if (i + j) % 2 == 0:
                        canvas.create_rectangle(i * w / 4, j * h / 4, (i + 1) * w / 4, (j + 1) * h / 4, fill='#ffffff', width=0)
        else:
            canvas.create_rectangle(0, 0, w, h, fill='#%02x%02x%02x' % EGA[c], width=0)

    def redraw_swatches(self):
        for c, sw in self.swatches.items():
            sw.configure(highlightbackground=C['accent'] if c == self.left else '#ffffff' if c == self.right else C['line'])
        if not hasattr(self, 'cur'):
            return
        cur = self.cur
        cur.delete('all')
        s = px(34)
        for c, x, y in ((self.right, px(24), px(16)), (self.left, px(2), px(2))):
            if c == CLEAR:
                cur.create_rectangle(x, y, x + s, y + s, fill='#bbbbbb', outline=C['line'])
                cur.create_rectangle(x, y, x + s // 2, y + s // 2, fill='#ffffff', width=0)
                cur.create_rectangle(x + s // 2, y + s // 2, x + s, y + s, fill='#ffffff', width=0)
            else:
                cur.create_rectangle(x, y, x + s, y + s, fill='#%02x%02x%02x' % EGA[c], outline='#ffffff' if (x, y) != (px(2), px(2)) else C['accent'],
                                     width=2)

    # ── the grid of pixels ──────────────────────────────────────────────────
    def _make_canvas(self):
        super()._make_canvas()
        self.canvas.configure(highlightthickness=1)

    def close(self):
        if self.dirty:
            d = ui.Dialog(self, 'Keep the changes?')
            ttk.Label(d.body, text='Keep the changes to this picture?', wraplength=px(380)).pack(anchor='w')
            d.add_buttons([('Cancel', None, 'TButton'), ("Don't keep", 'no', 'TButton'), ('Keep', 'yes', 'Accent.TButton')], default='yes')
            ans = d.run()
            if ans is None:
                return
            if ans == 'yes':
                self.save()
        self.destroy()

    def save(self):
        super().save()
        self.status.configure(text='Saved')
