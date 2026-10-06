"""The Studio's widgets: cards, sections, switches, number sliders, galleries, pickers, toasts and themed dialogs."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from studio.uikit import install as install_wheel, on_wheel, scroll_canvas     # noqa: F401  (the shared mouse wheel)

from . import icons, theme
from .theme import C, px


# ── small helpers ────────────────────────────────────────────────────────────
def button(parent, text='', command=None, icon=None, style='TButton', tip_text='', **kw):
    """A button, with an icon if given."""
    if not text:
        kw.setdefault('width', 3)
    b = ttk.Button(parent, text=text, command=command, style=style, **kw)
    if icon:
        colour = C['accent_text'] if style == 'Accent.TButton' else C['bad'] if style == 'Danger.TButton' else C['text']
        b.configure(image=icons.icon(icon, colour, px(16)), compound='left' if text else 'center')
        b._icon = icon
    if tip_text:
        tip(b, tip_text)
    return b


def label(parent, text='', style='TLabel', **kw):
    return ttk.Label(parent, text=text, style=style, **kw)


def hsep(parent, **kw):
    return ttk.Separator(parent, orient='horizontal', **kw)


def vsep(parent, **kw):
    return ttk.Separator(parent, orient='vertical', **kw)


class Tooltip:
    """The little box that explains a widget while the pointer rests on it."""
    DELAY = 450

    def __init__(self, widget, text):
        self.widget, self.text, self.box, self.job = widget, text, None, None
        widget.bind('<Enter>', self._enter, add='+')
        widget.bind('<Leave>', self._leave, add='+')
        widget.bind('<ButtonPress>', self._leave, add='+')

    def _enter(self, e=None):
        self._leave()
        self.job = self.widget.after(self.DELAY, self._show)

    def _leave(self, e=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.box is not None:
            self.box.destroy()
            self.box = None

    def _show(self):
        self.job = None
        if not self.text:
            return
        try:
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 18
        except tk.TclError:
            return
        self.box = tk.Toplevel(self.widget)
        self.box.wm_overrideredirect(True)
        self.box.configure(bg=C['line'])
        tk.Label(self.box, text=self.text, bg=C['raised'], fg=C['text'], justify='left', wraplength=px(340),
                 padx=px(10), pady=px(6), font=(theme.FONT, 9)).pack(padx=1, pady=1)
        self.box.update_idletasks()
        sw, sh = self.widget.winfo_screenwidth(), self.widget.winfo_screenheight()
        w, h = self.box.winfo_reqwidth(), self.box.winfo_reqheight()
        self.box.wm_geometry(f'+{min(x, sw - w - 8)}+{min(y, sh - h - 8)}')


def tip(widget, text):
    """Explain a widget when the pointer rests on it. A second call changes the words."""
    if not text:
        return widget
    old = getattr(widget, '_tooltip', None)
    if old is not None:
        old.text = text
    else:
        widget._tooltip = Tooltip(widget, text)
    return widget


# ── scrolling ────────────────────────────────────────────────────────────────
class Scrolled(ttk.Frame):
    """A frame that scrolls: put things in .body. The mouse wheel works anywhere over it."""

    def __init__(self, master, bg='panel', horizontal=False, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=C[bg], bd=0)
        self.bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._yset)
        self.bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        style = {'panel': 'TFrame', 'bg': 'Bg.TFrame', 'raised': 'Raised.TFrame'}[bg]
        self.body = ttk.Frame(self.canvas, style=style)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda e: self._fit())
        self.canvas.bind('<Configure>', lambda e: self._width(e.width))
        on_wheel(self, scroll_canvas(self.canvas, 2))
        self._barred = True

    def _width(self, w):
        self.canvas.itemconfigure(self._win, width=w)
        self._fit()

    def _fit(self):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        need = self.body.winfo_reqheight() > self.canvas.winfo_height()
        if need != self._barred and self.canvas.winfo_height() > 1:
            self._barred = need
            if need:
                self.bar.pack(side='right', fill='y', before=self.canvas)
            else:
                self.bar.pack_forget()
                self.canvas.yview_moveto(0)

    def _yset(self, a, b):
        self.bar.set(a, b)

    def to_top(self):
        self.canvas.yview_moveto(0)

    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()


# ── cards and sections ───────────────────────────────────────────────────────
class Card(tk.Frame):
    """A raised panel with a thin border."""

    def __init__(self, master, pad=12, **kw):
        super().__init__(master, bg=C['raised'], highlightbackground=C['line'], highlightthickness=1, bd=0, **kw)
        self.inner = ttk.Frame(self, style='Raised.TFrame', padding=pad)
        self.inner.pack(fill='both', expand=True)


class Section(ttk.Frame):
    """A collapsible group of settings: a header you click, and a body under it."""

    def __init__(self, master, title, subtitle='', open_=True, on_toggle=None, raised=False):
        super().__init__(master, style='Raised.TFrame' if raised else 'TFrame')
        self._raised = raised
        self.open = open_
        self.on_toggle = on_toggle
        st = 'Raised.' if raised else ''
        self.head = ttk.Frame(self, style=f'{st}TFrame', cursor='hand2')
        self.head.pack(fill='x')
        self.arrow = ttk.Label(self.head, style=f'{st}TLabel')
        self.arrow.pack(side='left', padx=(0, px(6)))
        self.title = ttk.Label(self.head, text=title, style='H3.TLabel' if not raised else 'H3.TLabel')
        if raised:
            self.title.configure(background=C['raised'])
        self.title.pack(side='left')
        self.sub = ttk.Label(self.head, text=subtitle, style='Raised.Dim.TLabel' if raised else 'Dim.TLabel')
        self.sub.pack(side='left', padx=px(10))
        for w in (self.head, self.arrow, self.title, self.sub):
            w.bind('<Button-1>', lambda e: self.toggle())
        self.body = ttk.Frame(self, style=f'{st}TFrame', padding=(px(20), px(6), 0, px(6)))
        self._draw()

    def _draw(self):
        self.arrow.configure(image=icons.icon('down' if self.open else 'right', C['dim'], px(12)))
        if self.open:
            self.body.pack(fill='x')
        else:
            self.body.pack_forget()

    def toggle(self):
        self.open = not self.open
        self._draw()
        if self.on_toggle:
            self.on_toggle(self)


# ── controls ─────────────────────────────────────────────────────────────────
class Switch(tk.Canvas):
    """An on/off switch."""

    def __init__(self, master, value=False, command=None, bg=None):
        w, h = px(36), px(20)
        super().__init__(master, width=w, height=h, highlightthickness=0, bd=0, bg=bg or C['panel'], cursor='hand2')
        self.value, self.command, self.w, self.h = bool(value), command, w, h
        self.bind('<Button-1>', lambda e: self.flip())
        self.bind('<space>', lambda e: self.flip())
        self.configure(takefocus=1)
        self._draw()

    def _draw(self):
        self.delete('all')
        w, h = self.w, self.h
        fill = C['accent'] if self.value else C['line']
        r = h // 2
        self.create_oval(0, 0, h, h, fill=fill, outline=fill)
        self.create_oval(w - h, 0, w, h, fill=fill, outline=fill)
        self.create_rectangle(r, 0, w - r, h, fill=fill, outline=fill)
        k = h - 6
        x = w - h + 3 if self.value else 3
        self.create_oval(x, 3, x + k, 3 + k, fill=C['accent_text'] if self.value else C['dim'], outline='')

    def set(self, value):
        self.value = bool(value)
        self._draw()

    def get(self):
        return self.value

    def flip(self):
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)


class Number(ttk.Frame):
    """A whole number: a slider and a box. live(value) while dragging, commit(value) when let go or typed.

    lo and hi are the real limits (huge when there is none). The slider only covers a handy stretch of them, soft_min to soft_max,
    and stretches by itself: to hold a value typed beyond its ends, and further each time it is dragged to an end, so it never
    stops anyone; the box takes any number between lo and hi."""

    def __init__(self, master, lo=0, hi=100, value=0, live=None, commit=None, width=5, slider=True, raised=False,
                 soft_max=None, soft_min=None):
        super().__init__(master, style='Raised.TFrame' if raised else 'TFrame')
        self.lo, self.hi, self.live, self.commit = lo, hi, live, commit
        self.soft = soft_max or hi
        self.soft_lo = soft_min if soft_min is not None else (lo if lo > -1000 else min(0, int(value)))
        self.var = tk.StringVar(value=str(value))
        self.scale = None
        if slider:
            self.scale = ttk.Scale(self, from_=self.soft_lo, to=self.soft, orient='horizontal', length=px(170),
                                   style='Raised.Horizontal.TScale' if raised else 'Horizontal.TScale',
                                   command=self._slid)
            self.scale.pack(side='left', padx=(0, px(8)))
            self.scale.bind('<ButtonRelease-1>', lambda e: self._release())
        self.entry = ttk.Entry(self, textvariable=self.var, width=width, justify='right')
        self.entry.pack(side='left')
        self.entry.bind('<Return>', lambda e: self._typed())
        self.entry.bind('<FocusOut>', lambda e: self._typed())
        self.entry.bind('<Up>', lambda e: self._step(1))
        self.entry.bind('<Down>', lambda e: self._step(-1))
        self._last = value
        self.set(value)

    def set(self, v):
        v = self._clamp(v)
        self._last = v
        self.var.set(str(v))
        if self.scale:
            self._fit(v)
            self.scale.set(v)

    def _fit(self, v, grow=False):
        """Stretch the slider's ends to hold v (and, when dragged to an end, to go on past it)."""
        hi, lo = self.soft, self.soft_lo
        if v >= hi:
            hi = max(v + max(10, abs(v) // 4), hi * 3 // 2 if grow else hi)
        if v <= lo and lo < 0 or (v < lo):
            lo = min(v - max(10, abs(v) // 4), lo * 3 // 2 if grow else lo)
        hi, lo = min(hi, self.hi), max(lo, self.lo)
        if (hi, lo) != (self.soft, self.soft_lo) and lo < hi:
            self.soft, self.soft_lo = hi, lo
            self.scale.configure(from_=lo, to=hi)

    def get(self) -> int:
        return self._last

    def _clamp(self, v):
        return max(self.lo, min(self.hi, int(v)))

    def _slid(self, raw):
        v = self._clamp(round(float(raw)))
        if v != self._last:
            self._last = v
            self.var.set(str(v))
            if self.live:
                self.live(v)

    def _release(self):
        if self.scale and (self._last >= self.soft or self._last <= self.soft_lo):
            self._fit(self._last, grow=True)                 # dragged to an end: the slider reaches further for the next time
            self.scale.set(self._last)
        if self.commit:
            self.commit(self._last)

    def _typed(self):
        try:
            v = self._clamp(int(self.var.get().strip() or 0))
        except ValueError:
            self.var.set(str(self._last))
            return
        changed = v != self._last
        self.set(v)
        if changed and self.commit:
            self.commit(v)

    def _step(self, d):
        self.set(self._last + d)
        if self.live:
            self.live(self._last)
        if self.commit:
            self.commit(self._last)
        return 'break'


class SearchBox(ttk.Frame):
    """A text box with a magnifier that calls command(text) as you type."""

    def __init__(self, master, command, placeholder='Search', width=22):
        super().__init__(master)
        self.var = tk.StringVar()
        self.command = command
        self.placeholder = placeholder
        ttk.Label(self, image=icons.icon('search', C['dim'], px(14))).pack(side='left', padx=(0, px(4)))
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side='left', fill='x', expand=True)
        self.var.trace_add('write', lambda *a: self.command(self.var.get()))
        self.entry.bind('<Escape>', lambda e: self.clear())

    def clear(self):
        self.var.set('')

    def text(self) -> str:
        return self.var.get().strip()

    def focus(self):
        self.entry.focus_set()


class Segmented(ttk.Frame):
    """A row of buttons of which one is chosen (a tab bar for a page)."""

    def __init__(self, master, options, command, value=None, raised=False):
        super().__init__(master, style='Raised.TFrame' if raised else 'TFrame')
        self.command, self.buttons, self.value = command, {}, None
        for key, text in options:
            b = tk.Label(self, text=text, padx=px(10), pady=px(5), cursor="hand2", font=(theme.FONT, 10))
            b.bind('<Button-1>', lambda e, k=key: self.choose(k))
            self.buttons[key] = b
        self._flowed = None
        self.bind('<Configure>', lambda e: self._flow(e.width))
        self._flow(0)
        self.choose(value if value is not None else options[0][0], run=False)

    def _flow(self, width):
        """Lay the tabs out in as many rows as the width needs (a long row of tabs is never cut off)."""
        if self._flowed == width:
            return
        self._flowed = width
        gap, x, y, rows_w, row_h = 2, 0, 0, 0, 0
        for b in self.buttons.values():
            w, h = b.winfo_reqwidth(), b.winfo_reqheight()
            if x and width > 1 and x + w > width:
                x, y = 0, y + row_h + gap
            b.place(x=x, y=y)
            x += w + gap
            rows_w, row_h = max(rows_w, x - gap), h
        self.configure(width=max(rows_w, 1), height=y + row_h)

    def choose(self, key, run=True):
        self.value = key
        for k, b in self.buttons.items():
            on = k == key
            b.configure(bg=C['accent'] if on else C['raised'], fg=C['accent_text'] if on else C['dim'])
        if run:
            self.command(key)


class Flow(ttk.Frame):
    """A row of things that goes on to a second row when the width is short (buttons beside a name, say). Make each thing a child of the
    flow, then `add` it."""

    def __init__(self, master, gap=6, **kw):
        super().__init__(master, **kw)
        self.items, self.gap, self._width = [], px(gap), None
        self.bind('<Configure>', lambda e: self._layout(e.width))

    def add(self, widget):
        self.items.append(widget)
        self._layout(self.winfo_width(), force=True)
        return widget

    def _layout(self, width, force=False):
        if self._width == width and not force:
            return
        self._width = width
        x = y = row_h = natural = 0
        for w in self.items:
            ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
            if x and width > 1 and x + ww > width:
                x, y, row_h = 0, y + row_h + self.gap, 0
            w.place(x=x, y=y)
            x += ww + self.gap
            natural = max(natural, x - self.gap)
            row_h = max(row_h, wh)
        self.configure(height=max(1, y + row_h), width=max(1, natural) if width <= 1 else width)


class ChoiceCards(ttk.Frame):
    """Big cards to choose one from: options [(key, title, text, icon)]."""

    def __init__(self, master, options, command, value=None, columns=3, width=200):
        super().__init__(master)
        self.command, self.cards, self.value, self.options = command, {}, None, {o[0]: o for o in options}
        for i, (key, title, text, icon) in enumerate(options):
            card = tk.Frame(self, bg=C['raised'], highlightthickness=2, highlightbackground=C['line'], cursor='hand2', width=px(width))
            card.grid(row=i // columns, column=i % columns, padx=px(5), pady=px(5), sticky='nsew')
            head = tk.Frame(card, bg=C['raised'])
            head.pack(fill='x', padx=px(10), pady=(px(10), 0))
            im = tk.Label(head, bg=C['raised'], bd=0)
            im.pack(side='left')
            tt = tk.Label(head, text=title, bg=C['raised'], fg=C['text'], font=(theme.FONT, 11, 'bold'))
            tt.pack(side='left', padx=px(8))
            tx = tk.Label(card, text=text, bg=C['raised'], fg=C['dim'], font=(theme.FONT, 9), wraplength=px(width - 24),
                          justify='left', anchor='w')
            tx.pack(fill='x', padx=px(10), pady=(px(4), px(10)))
            kids = [card, head, im, tt, tx]
            for w in kids:
                w.bind('<Button-1>', lambda e, k=key: self.choose(k))
            self.cards[key] = (card, kids, im, tt, icon)
        for c in range(columns):
            self.columnconfigure(c, weight=1, uniform='cc')
        self.choose(value if value is not None else options[0][0], run=False)

    def choose(self, key, run=True):
        self.value = key
        for k, (card, kids, im, tt, icon) in self.cards.items():
            on = k == key
            bg = C['select'] if on else C['raised']
            card.configure(highlightbackground=C['accent'] if on else C['line'])
            for w in kids:
                w.configure(bg=bg)
            im.configure(image=icons.icon(icon, C['accent'] if on else C['dim'], px(22)))
        if run:
            self.command(key)


class ToolStrip(ttk.Frame):
    """A row of icon buttons of which one is chosen (the map's tools). tools: [(key, icon, tip)]."""

    def __init__(self, master, tools, command, value=None, raised=False):
        super().__init__(master, style='Raised.TFrame' if raised else 'TFrame')
        self.command, self.buttons, self.tools, self.value = command, {}, {k: i for k, i, _ in tools}, None
        for key, icon, text in tools:
            b = ttk.Button(self, style='Tool.TButton', command=lambda k=key: self.choose(k), takefocus=0, width=3)
            b.pack(side='left', padx=1)
            tip(b, text)
            self.buttons[key] = b
        self.choose(value if value is not None else tools[0][0], run=False)

    def choose(self, key, run=True):
        self.value = key
        for k, b in self.buttons.items():
            on = k == key
            b.configure(style='ToolOn.TButton' if on else 'Tool.TButton',
                        image=icons.icon(self.tools[k], C['accent_text'] if on else C['text'], px(18)))
        if run:
            self.command(key)

    def repaint(self):
        self.choose(self.value, run=False)


class CodeText(ttk.Frame):
    """A monospaced text box with line numbers, a scroll bar and red lines for errors. `.text` is the Text widget."""

    def __init__(self, master, height=20, width=80):
        super().__init__(master)
        self.text = tk.Text(self, height=height, width=width, wrap='none', undo=False, bg=C['input'], fg=C['text'], insertbackground=C['text'],
                            relief='flat', highlightthickness=1, highlightbackground=C['line'], highlightcolor=C['accent'],
                            font=('Courier', 11), padx=8, pady=6, tabs=(px(32),), selectbackground=C['accent'],
                            selectforeground=C['accent_text'])
        self.gutter = tk.Canvas(self, width=px(46), bg=C['panel'], highlightthickness=0)
        self.ybar = ttk.Scrollbar(self, orient='vertical', command=self._yview)
        self.xbar = ttk.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=self._yset, xscrollcommand=self.xbar.set)
        self.gutter.grid(row=0, column=0, sticky='ns')
        self.text.grid(row=0, column=1, sticky='nsew')
        self.ybar.grid(row=0, column=2, sticky='ns')
        self.xbar.grid(row=1, column=1, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.text.tag_configure('error', background='#5a2328')
        self.text.bind('<KeyRelease>', lambda e: self._numbers(), add='+')
        self.text.bind('<Configure>', lambda e: self._numbers(), add='+')
        self.text.bind('<MouseWheel>', lambda e: self.after(10, self._numbers), add='+')
        self.text.bind('<Button-4>', lambda e: self.after(10, self._numbers), add='+')
        self.text.bind('<Button-5>', lambda e: self.after(10, self._numbers), add='+')
        self.text.bind('<Tab>', self._tab)
        self.text.bind('<Return>', self._enter)

    def _yview(self, *a):
        self.text.yview(*a)
        self._numbers()

    def _yset(self, a, b):
        self.ybar.set(a, b)
        self._numbers()

    def _tab(self, e):
        self.text.insert('insert', '    ')
        return 'break'

    def _enter(self, e):
        """A new line starts as indented as the one above (one more after a colon)."""
        line = self.text.get('insert linestart', 'insert')
        indent = line[:len(line) - len(line.lstrip(' '))]
        if line.rstrip().endswith(':'):
            indent += '    '
        self.text.insert('insert', '\n' + indent)
        self.text.see('insert')
        self._numbers()
        return 'break'

    def _numbers(self):
        g = self.gutter
        g.delete('all')
        i = self.text.index('@0,0')
        while True:
            d = self.text.dlineinfo(i)
            if d is None:
                break
            g.create_text(px(40), d[1] + d[3] // 2, text=i.split('.')[0], anchor='e', fill=C['faint'], font=('Courier', 10))
            nxt = self.text.index(f'{i}+1line')
            if nxt == i:
                break
            i = nxt

    def set(self, value):
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', value)
        self.text.edit_reset()
        self.after(10, self._numbers)

    def get(self):
        return self.text.get('1.0', 'end-1c')

    def mark_errors(self, lines):
        self.text.tag_remove('error', '1.0', 'end')
        for n in lines:
            if n:
                self.text.tag_add('error', f'{n}.0', f'{n}.end')
        if lines and lines[0]:
            self.text.see(f'{lines[0]}.0')


class Badge(tk.Label):
    """A little coloured pill of text."""

    def __init__(self, master, text, colour='info', **kw):
        fg = C.get(colour, colour)
        super().__init__(master, text=text, bg=C['raised'], fg=fg, padx=px(6), pady=px(1), font=(theme.FONT, 8, 'bold'),
                         highlightbackground=fg, highlightthickness=1, bd=0, **kw)


class EmptyState(ttk.Frame):
    """What a list shows when it is empty: an icon, a sentence, a button."""

    def __init__(self, master, icon, text, button_text='', command=None):
        super().__init__(master)
        ttk.Label(self, image=icons.icon(icon, C['faint'], px(48))).pack(pady=(px(40), px(10)))
        ttk.Label(self, text=text, style='Dim.TLabel', wraplength=px(320), justify='center').pack()
        if button_text:
            button(self, button_text, command, style='Accent.TButton').pack(pady=px(14))


# ── toasts ───────────────────────────────────────────────────────────────────
class Toasts:
    """Short messages that fade after a moment, at the bottom right of the window."""

    def __init__(self, root):
        self.root = root
        self.box = None
        self.job = None

    def show(self, text, kind='info', ms=2600, action=None):
        self.hide()
        colour = {'ok': C['ok'], 'bad': C['bad'], 'warn': C['warn']}.get(kind, C['info'])
        f = tk.Frame(self.root, bg=colour, bd=0)
        inner = tk.Frame(f, bg=C['raised'])
        inner.pack(padx=(4, 1), pady=1)
        tk.Label(inner, text=text, bg=C['raised'], fg=C['text'], padx=px(14), pady=px(8), justify='left',
                 wraplength=px(420), font=(theme.FONT, 10)).pack(side='left')
        if action:
            a = tk.Label(inner, text=action[0], bg=C['raised'], fg=C['accent'], padx=px(10), cursor='hand2',
                         font=(theme.FONT, 10, 'bold'))
            a.pack(side='left')
            a.bind('<Button-1>', lambda e: (self.hide(), action[1]()))
        f.place(relx=1.0, rely=1.0, anchor='se', x=-px(18), y=-px(40))
        f.lift()
        self.box = f
        self.job = self.root.after(ms, self.hide)

    def hide(self):
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        if self.box is not None:
            self.box.destroy()
            self.box = None


# ── dialogs ──────────────────────────────────────────────────────────────────
class Dialog(tk.Toplevel):
    """A themed modal window: build in .body, buttons come from the `buttons` list [(text, value, style)]."""

    def __init__(self, parent, title, width=None, height=None):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=C['bg'])
        self.transient(parent.winfo_toplevel())
        self.result = None
        self.frame = ttk.Frame(self, padding=px(18))
        self.frame.pack(fill='both', expand=True)
        self.foot = ttk.Frame(self.frame)                       # the buttons are packed first: on a small screen it is the body that is squeezed
        self.foot.pack(side='bottom', fill='x', pady=(px(14), 0))
        self.body = ttk.Frame(self.frame)
        self.body.pack(fill='both', expand=True)
        self.bind('<Escape>', lambda e: self.close(None))
        self._size = (width, height)
        self.parent = parent
        # width and height are minimums, kept by empty spacers: the window is never given a fixed size, so it grows with its contents
        # (a warning or a longer text appearing in it) instead of cutting the text and the buttons off
        if height:                                              # (packed first: the packer then asks for the larger of this and the rest)
            ttk.Frame(self.frame, width=1, height=height).pack(side='left', before=self.body)
        if width:
            ttk.Frame(self.frame, width=width, height=1).pack(side='top', before=self.body)

    def add_buttons(self, buttons, default=None):
        for text, value, style in reversed(buttons):
            b = ttk.Button(self.foot, text=text, style=style, command=lambda v=value: self.close(v))
            b.pack(side='right', padx=(px(8), 0))
            if value == default:
                b.focus_set()
                self.bind('<Return>', lambda e, v=value: self.close(v))

    def close(self, value):
        self.result = value
        self.destroy()

    def run(self):
        self.update_idletasks()
        top = self.parent.winfo_toplevel()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(self.winfo_reqwidth(), sw - 40), min(self.winfo_reqheight(), sh - 100)
        x = top.winfo_rootx() + (top.winfo_width() - w) // 2
        y = top.winfo_rooty() + (top.winfo_height() - h) // 3
        self.geometry(f'+{max(0, min(x, sw - w - 20))}+{max(0, min(y, sh - h - 60))}')       # only where it goes: its size follows its contents
        self.deiconify()
        self.grab_set()
        self.wait_window()
        return self.result


def confirm(parent, title, message, yes='OK', no='Cancel', danger=False) -> bool:
    d = Dialog(parent, title)
    ttk.Label(d.body, text=message, wraplength=px(420), justify='left').pack(anchor='w')
    d.add_buttons([(no, False, 'TButton'), (yes, True, 'Danger.TButton' if danger else 'Accent.TButton')], default=True)
    return bool(d.run())


def inform(parent, title, message):
    d = Dialog(parent, title)
    ttk.Label(d.body, text=message, wraplength=px(440), justify='left').pack(anchor='w')
    d.add_buttons([('OK', True, 'Accent.TButton')], default=True)
    d.run()


def ask_text(parent, title, prompt, value='', ok='OK', width=36):
    d = Dialog(parent, title)
    ttk.Label(d.body, text=prompt, wraplength=px(420), justify='left').pack(anchor='w')
    var = tk.StringVar(value=value)
    e = ttk.Entry(d.body, textvariable=var, width=width)
    e.pack(fill='x', pady=(px(8), 0))
    e.focus_set()
    e.select_range(0, 'end')
    d.add_buttons([('Cancel', None, 'TButton'), (ok, 'ok', 'Accent.TButton')], default='ok')
    return var.get().strip() if d.run() == 'ok' else None


def ask_choice(parent, title, prompt, options, ok='OK'):
    """options: [(value, title, description)]; the chosen value or None."""
    d = Dialog(parent, title)
    ttk.Label(d.body, text=prompt, wraplength=px(460), justify='left').pack(anchor='w', pady=(0, px(8)))
    var = tk.StringVar(value=str(options[0][0]))
    keys = {str(o[0]): o[0] for o in options}
    for value, name, about in options:
        row = ttk.Frame(d.body)
        row.pack(fill='x', pady=2)
        ttk.Radiobutton(row, text=name, value=str(value), variable=var).pack(anchor='w')
        if about:
            ttk.Label(row, text=about, style='Dim.TLabel', wraplength=px(440), justify='left').pack(anchor='w', padx=px(22))
    d.add_buttons([('Cancel', None, 'TButton'), (ok, 'ok', 'Accent.TButton')], default='ok')
    return keys[var.get()] if d.run() == 'ok' else None


def position_popup(win, widget, w, h):
    """Put a pop-up window under a widget, kept on the screen."""
    widget.update_idletasks()
    x, y = widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height() + 2
    sw, sh = widget.winfo_screenwidth(), widget.winfo_screenheight()
    if y + h > sh - 40:
        y = max(8, widget.winfo_rooty() - h - 2)
    win.geometry(f'{w}x{h}+{min(x, sw - w - 8)}+{y}')
