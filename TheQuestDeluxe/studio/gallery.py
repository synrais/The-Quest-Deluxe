"""Galleries of pictures with names (what you pick a creature, an item or a tile from), and the drop-down that uses one."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import icons, theme
from .theme import C, px
from .ui import Scrolled, SearchBox, on_wheel, scroll_canvas, tip


class Entry:
    """One thing in a gallery."""
    __slots__ = ('key', 'title', 'sub', 'image', 'badge', 'group', 'search')

    def __init__(self, key, title, sub='', image=None, badge=None, group='', search=''):
        self.key, self.title, self.sub, self.image, self.badge, self.group = key, title, sub, image, badge, group
        self.search = (search or f'{title} {sub} {key}').lower()


class Gallery(ttk.Frame):
    """A scrolling grid of cards. Click one to select it; double-click to open it. `items` are Entry objects."""

    def __init__(self, master, on_select=None, on_open=None, card=(112, 96), list_mode=False, bg='panel', multi=False,
                 on_picks=None, toggle=False):
        super().__init__(master, style={'panel': 'TFrame', 'bg': 'Bg.TFrame'}[bg])
        self.on_select, self.on_open = on_select, on_open
        self.multi, self.on_picks, self.toggle = multi or toggle, on_picks, toggle
        self.picked: list = []                  # with multi: Ctrl+click adds and removes (a brush that mixes several)
        self.card_w, self.card_h = px(card[0]), px(card[1])
        self.list_mode = list_mode
        self.scroller = Scrolled(self, bg=bg)
        self.scroller.pack(fill='both', expand=True)
        self.items: list[Entry] = []
        self.shown: list[Entry] = []
        self.cards: dict = {}
        self.selected = None
        self.filter_text = ''
        self.bg = bg
        self._cols = 0
        self.scroller.canvas.bind('<Configure>', self._resized, add='+')
        self.empty = None

    # ── contents ────────────────────────────────────────────────────────────
    def set_items(self, items):
        self.items = list(items)
        self._rebuild()

    def filter(self, text):
        self.filter_text = (text or '').strip().lower()
        self._rebuild(keep_scroll=False)

    def select(self, key, scroll=True):
        self.selected = key
        self.picked = [key] if key is not None else []
        self._paint_all()
        if scroll and key in self.cards:
            self._reveal(self.cards[key])

    def set_picks(self, keys):
        self.picked = list(keys)
        self.selected = self.picked[0] if self.picked else None
        self._paint_all()

    def _paint_all(self):
        for k, w in self.cards.items():
            self._paint(w, k in self.picked)

    def _reveal(self, w):
        c = self.scroller.canvas
        c.update_idletasks()
        y0, y1 = w.winfo_y(), w.winfo_y() + w.winfo_height()
        top, bottom = c.canvasy(0), c.canvasy(c.winfo_height())
        total = max(1, self.scroller.body.winfo_height())
        if y0 < top:
            c.yview_moveto(max(0, y0 - 8) / total)
        elif y1 > bottom:
            c.yview_moveto(max(0, y1 - c.winfo_height() + 8) / total)

    def _visible(self):
        t = self.filter_text
        return [e for e in self.items if not t or t in e.search]

    def _resized(self, e):
        cols = 1 if self.list_mode else max(1, (e.width - px(8)) // (self.card_w + px(8)))
        if cols != self._cols:
            self._rebuild()

    def _rebuild(self, keep_scroll=True):
        body = self.scroller.body
        y = self.scroller.canvas.yview()[0]
        for w in body.winfo_children():
            w.destroy()
        self.cards = {}
        self.shown = self._visible()
        width = max(self.scroller.canvas.winfo_width(), px(200))
        self._cols = 1 if self.list_mode else max(1, (width - px(8)) // (self.card_w + px(8)))
        if not self.shown:
            ttk.Label(body, text='Nothing matches.' if self.items else 'Nothing here yet.', style='Dim.TLabel',
                      padding=px(20)).grid(row=0, column=0)
            return
        row, col, group = 0, 0, None
        for e in self.shown:
            if e.group != group:
                group = e.group
                if col:
                    row, col = row + 1, 0
                if group:
                    h = ttk.Label(body, text=group.upper(), style='Faint.TLabel', font=(theme.FONT, 8, 'bold'),
                                  padding=(px(4), px(10) if row else px(2), 0, px(2)))
                    h.grid(row=row, column=0, columnspan=self._cols, sticky='w')
                    if self.bg == 'bg':
                        h.configure(background=C['bg'])
                    row += 1
            w = self._make(body, e)
            w.grid(row=row, column=col, padx=px(4), pady=px(4), sticky='nsew' if self.list_mode else 'n')
            self.cards[e.key] = w
            col += 1
            if col >= self._cols:
                row, col = row + 1, 0
        for c in range(self._cols):
            body.columnconfigure(c, weight=1 if self.list_mode else 0)
        self._paint_all()
        if keep_scroll:
            self.scroller.canvas.update_idletasks()
            self.scroller.canvas.yview_moveto(y)

    def _make(self, parent, e: Entry):
        card = tk.Frame(parent, bg=C['panel'], highlightthickness=1, highlightbackground=C['panel'], cursor='hand2')
        if self.list_mode:
            card.configure(width=0)
            img = tk.Label(card, image=e.image, bg=C['panel'], bd=0) if e.image is not None else None
            if img:
                img.pack(side='left', padx=px(6), pady=px(3))
            col = tk.Frame(card, bg=C['panel'])
            col.pack(side='left', fill='x', expand=True)
            t = tk.Label(col, text=e.title, bg=C['panel'], fg=C['text'], anchor='w', font=(theme.FONT, 10))
            t.pack(fill='x')
            kids = [x for x in (img, col, t) if x]
            if e.sub:
                s = tk.Label(col, text=e.sub, bg=C['panel'], fg=C['faint'], anchor='w', font=(theme.FONT, 8))
                s.pack(fill='x')
                kids.append(s)
            if e.badge:
                b = tk.Label(card, text=e.badge, bg=C['panel'], fg=C['dim'], font=(theme.FONT, 8, 'bold'))
                b.pack(side='right', padx=px(8))
                kids.append(b)
        else:
            card.configure(width=self.card_w, height=self.card_h)
            card.pack_propagate(False)
            img = tk.Label(card, image=e.image, bg=C['panel'], bd=0) if e.image is not None else tk.Label(card, bg=C['panel'])
            img.pack(pady=(px(8), px(2)))
            t = tk.Label(card, text=e.title, bg=C['panel'], fg=C['text'], font=(theme.FONT, 9), wraplength=self.card_w - px(10))
            t.pack()
            kids = [img, t]
            if e.sub:
                s = tk.Label(card, text=e.sub, bg=C['panel'], fg=C['faint'], font=(theme.FONT, 8))
                s.pack()
                kids.append(s)
            if e.badge:
                b = tk.Label(card, text=e.badge, bg=C['accent'], fg=C['accent_text'], font=(theme.FONT, 7, 'bold'), padx=3)
                b.place(relx=1.0, x=-4, y=4, anchor='ne')
                kids.append(b)
        card._kids = kids
        for w in [card] + kids:
            w.bind('<Button-1>', lambda ev, k=e.key: self._click(k, ev))
            w.bind('<Double-Button-1>', lambda ev, k=e.key: self._open(k))
            w.bind('<Enter>', lambda ev, c=card, k=e.key: self._hover(c, True, k))
            w.bind('<Leave>', lambda ev, c=card, k=e.key: self._hover(c, False, k))
        return card

    def _paint(self, card, on, hover=False):
        bg = C['select'] if on else C['hover'] if hover else (C['bg'] if self.bg == 'bg' else C['panel'])
        card.configure(bg=bg, highlightbackground=C['accent'] if on else bg)
        for k in card._kids:
            try:
                if k.cget('bg') != C['accent']:
                    k.configure(bg=bg)
            except tk.TclError:
                pass

    def _hover(self, card, inside, key):
        if key not in self.picked:
            self._paint(card, False, inside)

    def _click(self, key, ev=None):
        if self.multi and ev is not None and (self.toggle or ev.state & 0x4) and key is not None:
            if key in self.picked:
                if len(self.picked) > 1 or self.toggle:
                    self.picked.remove(key)
            else:
                self.picked.append(key)
            self.selected = self.picked[0] if self.picked else None
            self._paint_all()
            if self.on_picks:
                self.on_picks(list(self.picked))
            return
        self.select(key, scroll=False)
        if self.on_select:
            self.on_select(key)
        if self.on_picks:
            self.on_picks(list(self.picked))

    def _open(self, key):
        if self.on_open:
            self.on_open(key)


class Picker(ttk.Frame):
    """A button that shows the current choice (picture and name) and opens a searchable list of pictures to choose from.

    options() -> [Entry]; the value is an Entry key (or None for 'nothing')."""

    def __init__(self, master, options, value=None, command=None, none_label='(nothing)', width=26, raised=False):
        super().__init__(master, style='Raised.TFrame' if raised else 'TFrame')
        self.options, self.command, self.none_label, self.value, self.width = options, command, none_label, value, width
        self.btn = ttk.Button(self, command=self._open, style='TButton', compound='left')
        self.btn.pack(side='left')
        self._pop = None
        self.set(value)

    def _entry(self, value):
        return next((e for e in self.options() if e.key == value), None)

    def set(self, value):
        self.value = value
        e = self._entry(value) if value is not None else None
        text = e.title if e else (self.none_label if value is None else f'#{value}')
        if len(text) > self.width:
            text = text[:self.width - 1] + '…'
        self.btn.configure(text=text + '  ▾', image=e.image if e and e.image is not None else '')

    def _open(self):
        if self._pop is not None:
            self._close()
            return
        pop = tk.Toplevel(self)
        pop.wm_overrideredirect(True)
        pop.configure(bg=C['line'])
        inner = ttk.Frame(pop, padding=px(6))
        inner.pack(padx=1, pady=1, fill='both', expand=True)
        box = SearchBox(inner, lambda t: gal.filter(t), 'Search', width=26)
        box.pack(fill='x', pady=(0, px(6)))
        entries = list(self.options())
        if self.none_label:
            entries = [Entry(None, self.none_label)] + entries
        gal = Gallery(inner, on_select=self._chosen, list_mode=True)
        gal.pack(fill='both', expand=True)
        pop.update_idletasks()
        from .ui import position_popup
        position_popup(pop, self.btn, px(300), px(380))
        gal.set_items(entries)
        gal.select(self.value, scroll=False)
        self._pop = pop
        pop.bind('<Escape>', lambda e: self._close())
        pop.bind('<FocusOut>', lambda e: self.after(120, self._maybe_close))
        box.focus()
        pop.grab_set()
        pop.bind('<Button-1>', self._outside)

    def _outside(self, e):
        if self._pop is not None and not str(e.widget).startswith(str(self._pop)):
            self._close()

    def _maybe_close(self):
        if self._pop is not None:
            try:
                if self.focus_get() is None or not str(self.focus_get()).startswith(str(self._pop)):
                    self._close()
            except (KeyError, tk.TclError):
                self._close()

    def _chosen(self, key):
        self._close()
        self.set(key)
        if self.command:
            self.command(key)

    def _close(self):
        if self._pop is not None:
            try:
                self._pop.grab_release()
            except tk.TclError:
                pass
            self._pop.destroy()
            self._pop = None


def choose(parent, title, entries, value=None, none_label=None, ok='Choose'):
    """A window with a searchable gallery to choose one thing from. Returns its key, or the string '' for none_label's
    choice (key None), or False if cancelled."""
    from .ui import Dialog, SearchBox
    d = Dialog(parent, title, width=px(420), height=px(520))
    box = SearchBox(d.body, lambda t: gal.filter(t), 'Search', width=30)
    box.pack(fill='x', pady=(0, px(8)))
    items = list(entries)
    if none_label:
        items = [Entry(None, none_label)] + items
    chosen = {'key': value}

    def pick(key):
        chosen['key'] = key

    def done(key):
        chosen['key'] = key
        d.close('ok')
    gal = Gallery(d.body, on_select=pick, on_open=done, list_mode=True)
    gal.pack(fill='both', expand=True)
    gal.set_items(items)
    gal.select(value, scroll=True)
    d.add_buttons([('Cancel', None, 'TButton'), (ok, 'ok', 'Accent.TButton')], default='ok')
    box.focus()
    return chosen['key'] if d.run() == 'ok' else False
