"""The Mods page: everything The Quest Deluxe adds to the original, each with a switch for this quest."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from engine import mods

from .. import theme, ui
from ..theme import C, px
from .base import Page

GROUP_ICONS = {'Seeing the game': 'eye', 'Building': 'tiles', 'Items': 'sword', 'Creatures': 'skull', 'Always on': 'lock'}
INTRO = ('What The Quest Deluxe adds to the original, one by one. Switch one off and this quest plays as if it never used it: its '
         'items, creatures, tiles and level settings stay in the editor, but the game ignores them. Switch it on again and they all '
         'work again. The original quest uses none of them, so it plays the same with every mod off.')


class ModsPage(Page):
    key = 'mods'
    title = 'Mods'
    icon = 'gear'

    def build(self):
        self.header(self)
        self.scroll = ui.Scrolled(self)
        self.scroll.pack(fill='both', expand=True)
        self.switches, self.used = {}, {}
        b = self.scroll.body
        ttk.Label(b, text=INTRO, style='Dim.TLabel', wraplength=px(900), justify='left').pack(anchor='w', padx=px(24), pady=(0, px(8)))
        group = None
        for m in mods.MODS:
            if m.group != group:
                group = m.group
                f = ttk.Frame(b)
                f.pack(fill='x', padx=px(24), pady=(px(18), px(4)))
                ttk.Label(f, text=group, style='H2.TLabel').pack(side='left')
                if group == 'Always on':
                    ttk.Label(f, text='part of the engine: no switch', style='Dim.TLabel').pack(side='left', padx=px(12), pady=(px(6), 0))
            card = ui.Card(b, pad=12)
            card.pack(fill='x', padx=px(24), pady=px(4))
            inner = card.inner
            top = ttk.Frame(inner, style='Raised.TFrame')
            top.pack(fill='x')
            sw = ui.Switch(top, True, lambda v, m=m: self._set(m, v), bg=C['raised'])
            sw.pack(side='left')
            if not m.switch:
                sw.configure(state='disabled', cursor='arrow')
                sw.unbind('<Button-1>')
            ttk.Label(top, text=m.title, style='H3.TLabel', background=C['raised']).pack(side='left', padx=px(12))
            used = ttk.Label(top, text='', style='Raised.Dim.TLabel')
            used.pack(side='right')
            ttk.Label(inner, text=m.about, style='Raised.Dim.TLabel', wraplength=px(860), justify='left').pack(anchor='w', pady=(px(6), 0))
            self.switches[m.key], self.used[m.key] = sw, used
        ttk.Frame(b, height=px(30)).pack()
        self.s.on('quest', lambda sc, src: self._load())
        for t in ('items', 'creatures', 'spells', 'tiles', 'script'):
            self.s.on(t, lambda sc, src: self._load())

    def _load(self):
        if not self.built:
            return
        p = self.s.project
        off = mods.off(p.quest)
        tables = {'items': p.tables['items'], 'creatures': p.tables['creatures'], 'spells': p.tables['spells'],
                  'walls': p.tiles.get('walls', []), 'floors': p.tiles.get('floors', []), 'decos': p.tiles.get('decos', [])}

        def levels_with(name):
            return sum(1 for n in range(1, p.levels + 1) if p.constant(n, name) is not None)
        for m in mods.MODS:
            self.switches[m.key].set(m.key not in off)
            if m.switch:
                found = mods.uses(tables, p.quest, levels_with, m)
                self.used[m.key].configure(text=('used here: ' + ', '.join(found)) if found else ('built in' if m.engine else 'not used by this quest yet'))
            else:
                self.used[m.key].configure(text='always on')

    def _set(self, m, on):
        p = self.s.project
        with self.s.edit(f'Switch {m.title} {"on" if on else "off"}', 'quest', source=self):
            given = dict(p.quest.get('mods') or {})
            if on:
                given.pop(m.key, None)
            else:
                given[m.key] = False
            if given:
                p.quest['mods'] = given
            else:
                p.quest.pop('mods', None)
        self.app.say(f'{m.title}: {"on" if on else "off"} for this quest.')

    def on_show(self, **where):
        self._load()

    def reload(self):
        self._load()
