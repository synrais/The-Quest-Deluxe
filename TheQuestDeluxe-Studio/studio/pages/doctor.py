"""The Quest Doctor page: everything the Doctor found, with a button to go and look at it and, where it can, to fix it."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import doctor, theme, ui
from ..model import save_settings
from ..theme import C, px
from .base import Page

SEV = {'error': ('Must fix', 'bad', 'warn'), 'warn': ('Probably a mistake', 'warn', 'warn'), 'info': ('Good to know', 'info', 'info')}


class DoctorPage(Page):
    key = 'doctor'
    intro = 'The Quest Doctor reads the whole quest and lists what would go wrong when it is played. Show me takes you to the place, and Fix does what it can. Ignore keeps one quiet.'
    title = 'Quest Doctor'
    icon = 'check'

    def build(self):
        self.filter = 'all'
        self.show_ignored = False
        self.card = ui.Card(self, pad=16)
        self.card.pack(fill='x', padx=px(20), pady=(px(16), px(8)))
        f = self.card.inner
        row = ttk.Frame(f, style='Raised.TFrame')
        row.pack(fill='x')
        self.icon_label = tk.Label(row, bg=C['raised'], bd=0)
        self.icon_label.pack(side='left')
        col = ttk.Frame(row, style='Raised.TFrame')
        col.pack(side='left', padx=px(14), fill='x', expand=True)
        self.headline = ttk.Label(col, text='', style='H1.TLabel', background=C['raised'])
        self.headline.pack(anchor='w')
        self.subline = ttk.Label(col, text='', style='Raised.Dim.TLabel')
        self.subline.pack(anchor='w')
        ui.button(row, 'Check again', self.app.run_doctor, 'refresh', 'TButton', 'Read the whole quest again').pack(side='right')
        bar = ttk.Frame(self)
        bar.pack(fill='x', padx=px(20), pady=(px(4), px(4)))
        self.seg = ui.Segmented(bar, [('all', 'Everything'), ('error', 'Must fix'), ('warn', 'Probably mistakes'), ('info', 'Good to know')], self._filter, 'all')
        self.seg.pack(side='left')
        self.ign_btn = ttk.Button(bar, text='', style='Flat.TButton', command=self._toggle_ignored)
        self.ign_btn.pack(side='right')
        self.scroll = ui.Scrolled(self)
        self.scroll.pack(fill='both', expand=True)
        self.list = self.scroll.body

    def _filter(self, key):
        self.filter = key
        self.render()

    def _toggle_ignored(self):
        self.show_ignored = not self.show_ignored
        self.render()

    def ignored(self) -> set:
        return set(self.app.settings.get('ignored', {}).get(self.s.project.root, []))

    def schedule(self):
        pass

    def on_show(self, **where):
        self.render()

    def render(self):
        if not self.built:
            return
        problems = self.app.problems
        ign = self.ignored()
        shown = [p for p in problems if (p.key in ign) == self.show_ignored and (self.filter == 'all' or p.severity == self.filter)]
        live = [p for p in problems if p.key not in ign]
        c = doctor.counts(live)
        if not live:
            self.headline.configure(text='Your quest looks healthy')
            self.subline.configure(text='The Doctor read every level, creature, item, shop and story and found nothing wrong.')
            self.icon_label.configure(image=ui.icons.icon('check', C['ok'], px(44)))
        else:
            bits = []
            if c['error']:
                bits.append(f'{c["error"]} to fix')
            if c['warn']:
                bits.append(f'{c["warn"]} probable mistake{"s" if c["warn"] != 1 else ""}')
            if c['info']:
                bits.append(f'{c["info"]} to know')
            self.headline.configure(text=' · '.join(bits))
            self.subline.configure(text='Each one says what it is and takes you to the place to put it right.')
            self.icon_label.configure(image=ui.icons.icon('warn' if c['error'] or c['warn'] else 'info', C['bad'] if c['error'] else C['warn'] if c['warn'] else C['info'], px(44)))
        n_ign = len(problems) - len(live)
        self.ign_btn.configure(text=(f'Hide the {n_ign} ignored' if self.show_ignored else f'Show {n_ign} ignored') if n_ign else '')
        for w in self.list.winfo_children():
            w.destroy()
        if not shown:
            ttk.Label(self.list, text='Nothing here.', style='Dim.TLabel', padding=px(20)).pack(anchor='w', padx=px(20))
        last = None
        for p in shown:
            if p.severity != last:
                last = p.severity
                ttk.Label(self.list, text=SEV[p.severity][0].upper(), style='Faint.TLabel', font=(theme.FONT, 8, 'bold')).pack(anchor='w', padx=px(24), pady=(px(12), px(2)))
            self._row(p)
        ttk.Frame(self.list, height=px(20)).pack()

    def _row(self, p):
        colour = C[{'error': 'bad', 'warn': 'warn', 'info': 'info'}[p.severity]]
        row = tk.Frame(self.list, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
        row.pack(fill='x', padx=px(20), pady=2)
        tk.Frame(row, bg=colour, width=4).pack(side='left', fill='y')
        col = tk.Frame(row, bg=C['raised'])
        col.pack(side='left', fill='x', expand=True, padx=px(12), pady=px(8))
        tk.Label(col, text=p.title, bg=C['raised'], fg=C['text'], anchor='w', justify='left', wraplength=px(760), font=(theme.FONT, 10, 'bold')).pack(fill='x')
        if p.detail:
            tk.Label(col, text=p.detail, bg=C['raised'], fg=C['dim'], anchor='w', justify='left', wraplength=px(760), font=(theme.FONT, 9)).pack(fill='x')
        tk.Label(col, text=p.area, bg=C['raised'], fg=C['faint'], anchor='w', font=(theme.FONT, 8)).pack(fill='x')
        btns = tk.Frame(row, bg=C['raised'])
        btns.pack(side='right', padx=px(10))
        if p.go:
            ttk.Button(btns, text='Show me', style='TButton', command=lambda p=p: self.app.go(p.go[0], **p.go[1])).pack(side='left', padx=2)
        if p.fixer:
            ttk.Button(btns, text=p.fix or 'Fix it', style='Accent.TButton', command=lambda p=p: self._fix(p)).pack(side='left', padx=2)
        ign = p.key in self.ignored()
        ttk.Button(btns, text='Stop ignoring' if ign else 'Ignore', style='Flat.TButton', command=lambda p=p: self._ignore(p)).pack(side='left', padx=2)

    def _fix(self, p):
        p.fixer(self.s)
        self.app.say('Done.', 'ok')
        self.app.run_doctor()

    def _ignore(self, p):
        d = self.app.settings.setdefault('ignored', {})
        mine = set(d.get(self.s.project.root, []))
        if p.key in mine:
            mine.discard(p.key)
        else:
            mine.add(p.key)
        d[self.s.project.root] = sorted(mine)
        save_settings(self.app.settings)
        self.app.update_badges()
        self.render()

    def reload(self):
        self.render()
