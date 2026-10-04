"""The "Death and respawn..." window of the Map tab: what happens on this level when the hero dies. He can respawn on the
level (at a square set with the map's Respawn tool, with part of his life, some gold lost, perhaps a kit of items), and
the level can be the Underworld he wakes in when he dies elsewhere, from which he fights back to his body."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .uikit import center, tip

RETURNS = [('exit', 'at the level exit'), ('clear', 'when every monster is dead'),
           ('script', 'when an event calls revive()')]


def parse_kit(text: str) -> list:
    return [int(v) for v in text.replace(',', ' ').split()]


class DeathWindow(tk.Toplevel):
    def __init__(self, map_tab):
        super().__init__(map_tab)
        self.tab, self.p, self.n = map_tab, map_tab.app.project, map_tab.level
        self.title(f'Death and respawn - level {self.n}')
        top = ttk.Frame(self, padding=10)
        top.pack(fill='both', expand=True)
        p, n = self.p, self.n
        self.items = [(r['id'], r.get('name', '')) for r in sorted(p.tables['items'], key=lambda r: r['id'])]

        box = ttk.LabelFrame(top, text='Respawn on this level', padding=6)
        box.pack(fill='x')
        self.respawn = tk.BooleanVar(value=bool(p.constant(n, 'RESPAWN')))
        c = ttk.Checkbutton(box, text='When he dies here he wakes again here', variable=self.respawn)
        c.grid(row=0, column=0, columnspan=3, sticky='w')
        tip(c, 'He wakes at the Respawn square (the map tool Respawn; the start square if none is set), his body left '
               'where he fell. Without this, death here sends him to the Underworld (if the pack has one) or ends the game.')
        self.where = ttk.Label(box, foreground='#555')
        self.where.grid(row=1, column=0, columnspan=3, sticky='w')
        self.life = self.entry(box, 2, 'Life on waking %', 'RESPAWN_LIFE', 'Percent of his life (empty: 50).')
        self.lost = self.entry(box, 3, 'Gold lost %', 'RESPAWN_GOLD_LOSS', 'Percent of his gold he loses each time (empty: none).')
        self.limit = self.entry(box, 4, 'Times allowed', 'RESPAWN_LIMIT', 'How many times he can wake here on this level; then the '
                                'Underworld or the real death (empty: always).')
        self.kit = self.kit_row(box, 5, 'Starts with', 'RESPAWN_KIT')
        self.show_where()

        uw = ttk.LabelFrame(top, text='This level is the Underworld', padding=6)
        uw.pack(fill='x', pady=8)
        self.underworld = tk.BooleanVar(value=bool(p.constant(n, 'UNDERWORLD', False)))
        c = ttk.Checkbutton(uw, text='The dead wake on this level (and fight back to their body)', variable=self.underworld)
        c.grid(row=0, column=0, columnspan=3, sticky='w')
        tip(c, 'When the hero dies on another level he wakes here at the start square; his body stays where it fell. Dying '
               'here is the real death (or a respawn, if this level has one).')
        ttk.Label(uw, text='He returns').grid(row=1, column=0, sticky='w')
        self.way = ttk.Combobox(uw, values=[label for _, label in RETURNS], state='readonly', width=26)
        self.way.set(dict(RETURNS).get(p.constant(n, 'UNDERWORLD_RETURN', 'exit'), RETURNS[0][1]))
        self.way.grid(row=1, column=1, columnspan=2, sticky='w')
        tip(self.way, 'How he gets back: stepping on the level exit, killing every monster of the level, or when an event '
                      'calls revive().')
        self.uw_life = self.entry(uw, 2, 'Life on waking %', 'UNDERWORLD_LIFE', 'Percent of his life when he wakes here (empty: 50).')
        self.uw_back = self.entry(uw, 3, 'Life on return %', 'REVIVE_LIFE', 'The least life he has back in his body (empty: 50).')
        self.uw_kit = self.kit_row(uw, 4, 'Starts with', 'UNDERWORLD_KIT')
        self.strip = tk.BooleanVar(value=bool(p.constant(n, 'UNDERWORLD_STRIP', False)))
        c = ttk.Checkbutton(uw, text='The Underworld takes his things (he gets them back with his body)', variable=self.strip)
        c.grid(row=5, column=0, columnspan=3, sticky='w')
        tip(c, "His bag and potions are set aside while he is here, so he fights with only what 'Starts with' gives him. "
               'What he finds here is lost when he returns.')
        row = ttk.Frame(top)
        row.pack(fill='x')
        ttk.Button(row, text='Apply', command=self.apply).pack(side='left')
        ttk.Button(row, text='Close', command=self.destroy).pack(side='left', padx=6)
        center(self, parent=map_tab.winfo_toplevel())

    def entry(self, box, row, label, name, words):
        ttk.Label(box, text=label).grid(row=row, column=0, sticky='w')
        e = ttk.Entry(box, width=10)
        v = self.p.constant(self.n, name)
        e.insert(0, '' if v is None else str(v))
        e.grid(row=row, column=1, sticky='w')
        tip(e, words)
        return e

    def kit_row(self, box, row, label, name):
        ttk.Label(box, text=label).grid(row=row, column=0, sticky='w')
        e = ttk.Entry(box, width=26)
        e.insert(0, ', '.join(str(v) for v in self.p.constant(self.n, name, []) or []))
        e.grid(row=row, column=1, sticky='w')
        ttk.Button(box, text='Add...', width=6, command=lambda: self.add_item(e)).grid(row=row, column=2, padx=3)
        tip(e, 'Item numbers he is given, e.g. 101, 201: wearable ones go on if nothing is worn there, potions on the belt, the '
               'rest in the backpack.')
        return e

    def add_item(self, entry):
        from .event_wizard import Picker
        got = Picker(self, 'An item to start with', [(i, name) for i, name in self.items], ('Number', 'Name')).result
        if got is not None:
            now = [v for v in entry.get().replace(',', ' ').split() if v]
            entry.delete(0, 'end')
            entry.insert(0, ', '.join(now + [str(got)]))

    def show_where(self):
        spot = self.p.constant(self.n, 'RESPAWN') or self.p.constant(self.n, 'START', (5, 5))
        self.where.config(text=f'Respawn square: {spot[0]}, {spot[1]}   (move it with the Respawn tool on the map)')

    def apply(self):
        p, n = self.p, self.n
        try:
            numbers = {name: (int(e.get()) if e.get().strip() else None) for name, e in (
                ('RESPAWN_LIFE', self.life), ('RESPAWN_GOLD_LOSS', self.lost), ('RESPAWN_LIMIT', self.limit),
                ('UNDERWORLD_LIFE', self.uw_life), ('REVIVE_LIFE', self.uw_back))}
            assert all(v is None or 0 <= v <= 100 for k, v in numbers.items() if k != 'RESPAWN_LIMIT')
            assert numbers['RESPAWN_LIMIT'] is None or numbers['RESPAWN_LIMIT'] >= 0
            kits = {'RESPAWN_KIT': parse_kit(self.kit.get()), 'UNDERWORLD_KIT': parse_kit(self.uw_kit.get())}
        except (ValueError, AssertionError):
            messagebox.showerror('Death and respawn', 'Lives and gold lost are percents (0-100), times is a number, and '
                                 'a kit is item numbers like 101, 201.')
            return
        known = {i for i, _ in self.items}
        unknown = [v for kit in kits.values() for v in kit if v not in known]
        if unknown:
            messagebox.showerror('Death and respawn', f'No such item: {", ".join(map(str, unknown))}.')
            return

        def keep(name, value, why, default=None):
            if value is None or value == default or value == []:
                p.remove_constant(n, name)
            elif value != p.constant(n, name):
                p.set_constant(n, name, value, why)
        for name, v in numbers.items():
            keep(name, v, 'percent of his life or gold, or a count (see docs/EVENTS.md)')
        for name, v in kits.items():
            keep(name, v, 'item numbers he is handed')
        if self.respawn.get():
            if not p.constant(n, 'RESPAWN'):
                p.set_constant(n, 'RESPAWN', tuple(p.constant(n, 'START', (5, 5))), 'where he wakes after dying here')
        else:
            p.remove_constant(n, 'RESPAWN')
        keep('UNDERWORLD', True if self.underworld.get() else None, 'the dead wake on this level and fight their way back')
        keep('UNDERWORLD_STRIP', True if self.strip.get() else None, 'the Underworld takes his things')
        way = next((k for k, label in RETURNS if label == self.way.get()), 'exit')
        keep('UNDERWORLD_RETURN', way, 'how he gets back to his body', default='exit')
        self.show_where()
        self.tab.app.changed()
        self.tab.app.scripts_changed(n)
        self.tab.redraw()
