"""The frame the wizards share: the steps down the left, one page in the middle, a picture of the result on the right."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme, ui
from .theme import C, px


class StepDialog(ui.Dialog):
    """A wizard window. A subclass sets STEPS [(key, title, icon)], HEADING and MAKE_LABEL, and writes a `_step_<key>` method for each
    step, `preview_pane(right)`, `create()`, `refresh()` and `_set(key, value)`. `self.p` holds the settings the switches and
    numbers change."""
    STEPS: list = []
    HEADING = 'Make it'
    MAKE_LABEL = 'Make it'
    PREVIEW_WIDTH = 440

    def __init__(self, app, title, width, height):
        self.app = app
        self.s = app.session
        super().__init__(app.root, title, width=width, height=height)
        self.step = 0
        self.guard = False
        self.p = None

    # ── frame ───────────────────────────────────────────────────────────────
    def build_frame(self):
        self.frame.configure(padding=0)
        top = ttk.Frame(self.body)
        top.pack(fill='both', expand=True)
        left = ttk.Frame(top, width=px(190))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ttk.Label(left, text=self.HEADING, style='H2.TLabel').pack(anchor='w', padx=px(16), pady=(px(16), px(10)))
        self.step_labels = []
        for i, (key, title, icon) in enumerate(self.STEPS):
            row = tk.Frame(left, bg=C['panel'], cursor='hand2')
            row.pack(fill='x', padx=px(8), pady=1)
            num = tk.Label(row, text=str(i + 1), width=2, bg=C['panel'], fg=C['dim'], font=(theme.FONT, 10, 'bold'))
            num.pack(side='left', padx=(px(8), px(4)), pady=px(7))
            txt = tk.Label(row, text=title, bg=C['panel'], fg=C['dim'], anchor='w', font=(theme.FONT, 10))
            txt.pack(side='left', fill='x', expand=True)
            for w in (row, num, txt):
                w.bind('<Button-1>', lambda e, i=i: self.go(i))
            self.step_labels.append((row, num, txt))
        ui.vsep(top).pack(side='left', fill='y')
        right = ttk.Frame(top, width=px(self.PREVIEW_WIDTH))
        right.pack(side='right', fill='y')
        right.pack_propagate(False)
        ui.vsep(top).pack(side='right', fill='y')
        self.preview_pane(right)
        mid = ttk.Frame(top)
        mid.pack(side='left', fill='both', expand=True)
        self.title_label = ttk.Label(mid, text='', style='H1.TLabel')
        self.title_label.pack(anchor='w', padx=px(22), pady=(px(14), 0))
        self.sub_label = ttk.Label(mid, text='', style='Dim.TLabel', wraplength=px(480), justify='left')
        self.sub_label.pack(anchor='w', padx=px(22), pady=(px(2), px(6)))
        self.scroll = ui.Scrolled(mid)
        self.scroll.pack(fill='both', expand=True)
        self.page = self.scroll.body
        foot = self.foot
        foot.pack_configure(padx=px(18), pady=px(12))
        self.back_btn = ttk.Button(foot, text='Back', command=lambda: self.go(self.step - 1))
        self.back_btn.pack(side='left')
        self.make_btn = ttk.Button(foot, text=self.MAKE_LABEL, style='Accent.TButton', command=self.create)
        self.make_btn.pack(side='right')
        self.next_btn = ttk.Button(foot, text='Next', style='Accent.TButton', command=lambda: self.go(self.step + 1))
        self.next_btn.pack(side='right', padx=px(8))
        ttk.Button(foot, text='Cancel', command=lambda: self.close(None)).pack(side='right')

    def preview_pane(self, right):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def refresh(self):
        raise NotImplementedError

    def _set(self, key, v):
        raise NotImplementedError

    # ── steps ───────────────────────────────────────────────────────────────
    def go(self, i):
        i = max(0, min(len(self.STEPS) - 1, i))
        self.step = i
        for k, (row, num, txt) in enumerate(self.step_labels):
            on = k == i
            bg = C['select'] if on else C['panel']
            for w in (row, num, txt):
                w.configure(bg=bg)
            num.configure(fg=C['accent'] if on else C['dim'])
            txt.configure(fg=C['text'] if on else C['dim'], font=(theme.FONT, 10, 'bold' if on else 'normal'))
        self.scroll.clear()
        getattr(self, f'_step_{self.STEPS[i][0]}')()
        self.scroll.to_top()
        self.back_btn.state(['!disabled'] if i else ['disabled'])
        if i == len(self.STEPS) - 1:
            self.next_btn.pack_forget()
            self.make_btn.pack(side='right')
        else:
            self.make_btn.pack_forget()
            self.next_btn.pack(side='right', padx=px(8))

    def head(self, title, sub=''):
        self.title_label.configure(text=title)
        self.sub_label.configure(text=sub)

    def h(self, text, sub=''):
        f = ttk.Frame(self.page)
        f.pack(fill='x', padx=px(22), pady=(px(16), px(4)))
        ttk.Label(f, text=text, style='H3.TLabel').pack(anchor='w')
        if sub:
            ttk.Label(f, text=sub, style='Faint.TLabel', wraplength=px(470), justify='left').pack(anchor='w')
        return f

    def line(self, label, tip=''):
        r = ttk.Frame(self.page)
        r.pack(fill='x', padx=px(22), pady=3)
        lab = ttk.Label(r, text=label)
        lab.pack(side='left')
        if tip:
            ui.tip(lab, tip)
        return r

    def switch(self, label, key, tip='', store=None, refresh=True):
        r = self.line(label, tip)
        d = store if store is not None else self.p

        def flip(v):
            if isinstance(d, dict):
                d[key] = v
            else:
                setattr(d, key, v)
            if refresh:
                self.refresh()
        sw = ui.Switch(r, d[key] if isinstance(d, dict) else getattr(d, key), flip)
        sw.pack(side='right')
        return sw

    def number(self, label, key, lo, hi, tip='', scale=1, slider=True):
        r = self.line(label, tip)
        cur = getattr(self.p, key)
        num = ui.Number(r, lo, hi, int(round(cur * scale)), live=lambda v: self._set(key, v / scale),
                        commit=lambda v: self._set(key, v / scale), width=4, slider=slider)
        num.pack(side='right')
        return num
