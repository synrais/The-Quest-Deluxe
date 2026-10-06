"""The Spells page: what each spell costs, how far it reaches and what it does."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import ui
from ..theme import px
from .tablepage import TablePage

FILTERS = [('all', 'All'), ('attack', 'Attack'), ('heal', 'Healing'), ('summon', 'Summons'), ('other', 'Other')]
BY_EFFECT = {'bolt': 'attack', 'ward': 'attack', 'dark_hour': 'attack', 'earthquake': 'attack', 'freeze': 'attack', 'drain': 'attack',
             'fire_shield': 'attack', 'heal': 'heal', 'heal_target': 'heal', 'resurrect': 'summon', 'summon': 'summon',
             'shadow_clones': 'summon'}
GROUPS = {'attack': 'Attack spells', 'heal': 'Healing', 'summon': 'Summoning and raising', 'other': 'Other'}
KIND_ICONS = {'A bolt': 'bolt', 'Frost': 'water', 'Shadow clones': 'people', 'Disguise': 'eye', 'Resurrection': 'heart',
              'Mend': 'heart', 'A blank': 'wand'}


class SpellsPage(TablePage):
    key = 'spells'
    intro = 'Pick a spell, or press New. A spell has a picture, a cost in mana and an effect, and the effect decides which of the other fields matter.'
    title = 'Spells'
    icon = 'wand'
    table = 'spells'
    layer = 'spell'
    noun = 'spell'
    nouns = 'spells'
    filters = FILTERS

    def category(self, row):
        return BY_EFFECT.get(row.get('effect'), 'other')

    def group(self, row):
        return GROUPS[self.category(row)]

    def order(self, row):
        return (list(GROUPS).index(self.category(row)), row['id'])

    def entry_sub(self, row):
        return f'{row.get("mana", 0)} mana' if row.get('mana') else f'#{row["id"]}'

    def badges(self, row):
        out = [(f'#{row["id"]}', 'dim')]
        if row.get('effect'):
            out.append((row['effect'].replace('_', ' '), 'accent'))
        if row.get('mana'):
            out.append((f'{row["mana"]} mana', 'info'))
        return out

    def new(self):
        templates = self.schema.t.TEMPLATES
        d = ui.Dialog(self, 'A new spell', width=px(720))
        ttk.Label(d.body, text='What kind of spell?', style='H2.TLabel').pack(anchor='w')
        opts = []
        for i, (title, vals) in enumerate(templates):
            short, _, rest = title.partition(' (')
            icon = next((v for k, v in KIND_ICONS.items() if short.startswith(k)), 'wand')
            opts.append((str(i), short, rest.rstrip(')') or 'Start from nothing and set everything yourself.', icon))
        cards = ui.ChoiceCards(d.body, opts, lambda k: None, opts[0][0], columns=2, width=310)
        cards.pack(fill='x', pady=(px(8), 0))
        r = ttk.Frame(d.body)
        r.pack(fill='x', pady=(px(10), 0))
        ttk.Label(r, text='Name').pack(side='left')
        name = tk.StringVar(value='New spell')
        ttk.Entry(r, textvariable=name, width=30).pack(side='left', padx=px(10))
        d.add_buttons([('Cancel', None, 'TButton'), ('Make it', 'make', 'Accent.TButton')], default='make')
        if d.run() != 'make':
            return
        title, vals = templates[int(cards.value)]
        used = {r['id'] for r in self.rows()}
        rid = next(n for n in range(1, len(used) + 2) if n not in used)
        row = {'id': rid, 'name': name.get().strip() or 'New spell', 'req_int': 10, 'mana': 5, 'range': 3, 'power': 10, 'duration': 0}
        row.update({k: (list(v) if isinstance(v, list) else v) for k, v in vals.items()})
        if row['effect'] == 'shadow_clones':
            allies = [c['id'] for c in self.s.rows('creatures') if c['id'] <= -100]
            if allies:
                row['creature'] = allies[0]
        self.add_row(row, f'New spell: {row["name"]}')
