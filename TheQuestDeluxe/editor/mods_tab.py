"""The Mods tab: everything The Quest Deluxe adds to the original game, each with a check box. A pack plays without a mod
that is unticked (quest.json `mods`); nothing is deleted, so ticking it again brings it all back. engine/mods.py is the list."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from engine import mods

from .uikit import on_wheel, scroll_canvas, tip


class ModsTab(ttk.Frame):
    INTRO = ('What The Quest Deluxe adds to the original, one by one. Untick a mod and this pack plays as if it never used '
             'it: its items, creatures, tiles and level settings stay in the editor, but the game ignores them. Tick it '
             'again and they all work again. The original quest uses none of them, so it plays the same with every mod off.')

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        canvas = tk.Canvas(self, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        self.body = ttk.Frame(canvas, padding=12)
        self._win = canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: (canvas.itemconfigure(self._win, width=e.width),
                                              [w.configure(wraplength=max(300, e.width - 60)) for w in self.wrapped]))
        on_wheel(self, scroll_canvas(canvas))
        self.vars, self.wrapped, self.used_labels = {}, [], {}
        intro = ttk.Label(self.body, text=self.INTRO, wraplength=760, justify='left')
        intro.grid(row=0, column=0, sticky='w', pady=(0, 8))
        self.wrapped.append(intro)
        row, group = 1, None
        for m in mods.MODS:
            if m.group != group:
                group = m.group
                ttk.Label(self.body, text=group, font=('TkDefaultFont', 11, 'bold')).grid(row=row, column=0, sticky='w',
                                                                                         pady=(12, 2))
                row += 1
            box = ttk.Frame(self.body)
            box.grid(row=row, column=0, sticky='ew', pady=2)
            box.columnconfigure(0, minsize=360)
            var = tk.BooleanVar(value=True)
            self.vars[m.key] = var
            check = ttk.Checkbutton(box, text=m.title, variable=var, command=lambda m=m: self._set(m))
            check.grid(row=0, column=0, sticky='w')
            if not m.switch:
                check.state(['disabled'])
            used = ttk.Label(box, text='', foreground='#555')
            used.grid(row=0, column=1, sticky='w', padx=12)
            self.used_labels[m.key] = used
            about = ttk.Label(box, text=m.about, wraplength=760, justify='left', foreground='#333')
            about.grid(row=1, column=0, columnspan=2, sticky='w', padx=(24, 0))
            self.wrapped.append(about)
            tip(check, m.about if m.switch else 'Part of The Quest Deluxe: always on (settings.ini and the Quest tab have the choices).')
            row += 1

    def load(self):
        p = self.app.project
        off = mods.off(p.quest)
        tables = {'items': p.tables['items'], 'creatures': p.tables['creatures'], 'spells': p.tables['spells'],
                  'walls': p.tiles.get('walls', []), 'floors': p.tiles.get('floors', []), 'decos': p.tiles.get('decos', [])}

        def levels_with(name):
            return sum(1 for n in range(1, p.levels + 1) if p.constant(n, name) is not None)
        for m in mods.MODS:
            self.vars[m.key].set(m.key not in off)
            if m.switch:
                found = mods.uses(tables, p.quest, levels_with, m)
                self.used_labels[m.key].config(text=('used here: ' + ', '.join(found)) if found else
                                               ('built in' if m.engine else 'not used by this pack yet'))
            else:
                self.used_labels[m.key].config(text='always on')

    def _set(self, m):
        p = self.app.project
        given = dict(p.quest.get('mods') or {})
        if self.vars[m.key].get():
            given.pop(m.key, None)
        else:
            given[m.key] = False
        if given:
            p.quest['mods'] = given
        else:
            p.quest.pop('mods', None)
        p.touch('quest')
        self.app.changed()
        self.app.status(f'{m.title}: {"on" if self.vars[m.key].get() else "off"} for this pack.')
