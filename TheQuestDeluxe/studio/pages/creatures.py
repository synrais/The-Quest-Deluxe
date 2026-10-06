"""The Creatures page: monsters, people and allies, with a fight check against any hero and a wizard for making new ones."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import filedialog, ttk

import pygame

from editor.art import bag_cell, to_ega

from .. import archetypes, fightcalc, icons, levelmeta, theme, ui
from ..gallery import Entry, Gallery
from ..inspector import Inspector
from ..schema import Schema
from ..theme import C, px
from .tablepage import TablePage

VERDICT_COLOURS = {'Pushover': 'ok', 'Easy': 'ok', 'Fair': 'info', 'Tough': 'warn', 'Deadly': 'bad', 'Cannot be hurt': 'bad'}
ROLES = [('all', 'All'), ('mon', 'Monsters'), ('person', 'People'), ('ally', 'Allies')]


def role_of(v: int) -> str:
    return 'mon' if v > 0 else 'person' if v > -100 else 'ally'


ROLE_TITLE = {'mon': 'Monsters', 'person': 'People', 'ally': 'Summoned allies'}


class CreaturesPage(TablePage):
    key = 'creatures'
    title = 'Creatures'
    icon = 'skull'
    table = 'creatures'
    layer = 'mon'
    noun = 'creature'
    nouns = 'creatures'
    skip = ('id', '_role', 'name')
    filters = ROLES
    card = (94, 104)

    def build(self):
        super().build()
        self.s.on('classes', lambda sc, src: self.fight.refresh())
        self.s.on('items', lambda sc, src: self.fight.refresh())

    def category(self, row):
        return role_of(row['id'])

    def group(self, row):
        return ROLE_TITLE[role_of(row['id'])]

    def order(self, row):
        return (0 if row['id'] > 0 else 1 if row['id'] > -100 else 2, row['id'] if row['id'] > 0 else -row['id'])

    def badges(self, row):
        from editor.creatures_tab import role
        out = [(f'#{row["id"]}', 'dim'), (role(row['id']), 'accent' if row['id'] > 0 else 'info')]
        size = int(row.get('size') or 1)
        if size > 1:
            out.append((f'{size} × {size} squares', 'warn'))
        return out

    def extra_cards(self, parent):
        self.fight = FightCard(parent, self)
        self.fight.pack(fill='x', padx=px(20), pady=(px(10), px(4)))

    def shown(self, row):
        self.fight.refresh()

    def edited(self, row, key):
        self.fight.refresh()

    def first_id(self):
        rows = sorted((c for c in self.rows() if c['id'] > 0), key=lambda c: c['id']) or sorted(self.rows(), key=lambda c: c['id'])
        return rows[0]['id'] if rows else None

    def new(self):
        wiz = CreatureWizard(self)
        rid = wiz.run()
        if rid is not None:
            self.cat = 'all'
            self.seg.choose('all', run=False)
            self.fill()
            self.select(rid)
            if wiz.paint_now.get():
                self.after(200, lambda: self.paint('creatures', False, 'Picture'))


class FightCard(ui.Card):
    """How this creature fares against a hero: the numbers in words, and a strip showing every hero level from 1 to 20."""

    def __init__(self, master, page):
        super().__init__(master, pad=14)
        self.page, self.s = page, page.s
        f = self.inner
        head = ttk.Frame(f, style='Raised.TFrame')
        head.pack(fill='x')
        ttk.Label(head, text='Fight check', style='H3.TLabel', background=C['raised']).pack(side='left')
        ttk.Label(head, text='against', style='Raised.Dim.TLabel').pack(side='left', padx=px(10))
        self.cls = ttk.Combobox(head, state='readonly', width=12)
        self.cls.pack(side='left')
        ttk.Label(head, text='at level', style='Raised.Dim.TLabel').pack(side='left', padx=px(10))
        self.level = ui.Number(head, 1, 60, int(page.app.settings.get('calc_level', 5)), commit=self._level, soft_max=30, width=3,
                               raised=True)
        self.level.pack(side='left')
        self.cls.bind('<<ComboboxSelected>>', lambda e: self._class())
        row = ttk.Frame(f, style='Raised.TFrame')
        row.pack(fill='x', pady=(px(10), 0))
        self.badge = tk.Label(row, text='', font=(theme.FONT, 12, 'bold'), padx=px(12), pady=px(4), bd=0)
        self.badge.pack(side='left', anchor='n')
        self.text = ttk.Label(row, text='', style='Raised.TLabel', wraplength=px(520), justify='left')
        self.text.pack(side='left', padx=px(14), anchor='n')
        self.strip = tk.Canvas(f, height=px(30), highlightthickness=0, bg=C['raised'])
        self.strip.pack(fill='x', pady=(px(10), 0))
        self.strip.bind('<Motion>', self._hover)
        self.strip.bind('<Leave>', lambda e: self.tip.configure(text=''))
        self.tip = ttk.Label(f, text='', style='Raised.Dim.TLabel')
        self.tip.pack(anchor='w')
        bal = ttk.Frame(f, style='Raised.TFrame')
        bal.pack(fill='x', pady=(px(6), 0))
        ttk.Label(bal, text='Balance it so this hero loses about', style='Raised.TLabel').pack(side='left')
        self.target = ui.Number(bal, 5, 95, 30, slider=False, width=3, raised=True)
        self.target.pack(side='left', padx=px(6))
        ttk.Label(bal, text='% of his life per fight', style='Raised.TLabel').pack(side='left')
        ui.button(bal, 'Balance', self.balance, 'dice', 'TButton', 'Set its life and power for you, keeping their proportion').pack(side='left', padx=px(10))
        self._cells = []
        self._fill_classes()

    def _fill_classes(self):
        classes = self.s.rows('classes')
        names = [f'{c["id"]} {c["name"]}' for c in classes]
        self.cls.configure(values=names)
        want = self.page.app.settings.get('calc_class', self.page.app.settings.get('hero'))
        self.cls.set(next((n for n in names if n.split()[0] == str(want)), names[0] if names else ''))

    def class_id(self):
        v = self.cls.get()
        return int(v.split()[0]) if v else None

    def _class(self):
        self.page.app.settings['calc_class'] = self.class_id()
        self.refresh()

    def _level(self, v):
        self.page.app.settings['calc_level'] = v
        self.refresh()

    def hero(self):
        cid = self.class_id()
        if cid is None:
            return None
        lv = self.level.get()
        return fightcalc.hero_at(self.s.project, cid, lv, fightcalc.gear_for_level(self.s.project, cid, lv))

    def refresh(self):
        if not self.winfo_exists():
            return
        classes = [f'{c["id"]} {c["name"]}' for c in self.s.rows('classes')]
        if list(self.cls.cget('values')) != classes:
            self._fill_classes()
        mon, h = self.page.row(), self.hero()
        if mon is None or h is None or not h.life:
            return
        d = fightcalc.duel(h, mon)
        colour = C[VERDICT_COLOURS.get(d.verdict, 'info')]
        self.badge.configure(text=d.verdict, bg=colour, fg='#101114')
        lines = fightcalc.describe(d, h, mon)
        if d.note:
            lines.append(d.note)
        self.text.configure(text='\n'.join(lines))
        self._heat(mon)

    def _heat(self, mon):
        c = self.strip
        c.delete('all')
        cid = self.class_id()
        data = fightcalc.heat(self.s.project, mon, cid, range(1, 21), runs=120)
        self._cells = data
        w = max(px(300), c.winfo_width() or px(600))
        cw = w / 20
        for i, (lv, d) in enumerate(data):
            colour = C[VERDICT_COLOURS.get(d.verdict, 'info')]
            c.create_rectangle(i * cw + 1, 0, (i + 1) * cw - 1, px(18), fill=colour, outline='')
            if lv in (1, 5, 10, 15, 20) or lv == self.level.get():
                c.create_text(i * cw + cw / 2, px(25), text=str(lv), fill=C['dim'], font=(theme.FONT, 8))
        cur = self.level.get()
        if 1 <= cur <= 20:
            c.create_rectangle((cur - 1) * cw, 0, cur * cw, px(18), outline=C['text'], width=2)

    def _hover(self, e):
        if not self._cells:
            return
        w = max(px(300), self.strip.winfo_width())
        i = max(0, min(19, int(e.x / (w / 20))))
        lv, d = self._cells[i]
        self.tip.configure(text=f'Level {lv}: {d.verdict}. He loses about {d.life_lost_pct * 100:.0f}% of his life and wins {d.win * 100:.0f}% of fights.')

    def balance(self):
        mon, h = self.page.row(), self.hero()
        if mon is None or h is None:
            return
        res = fightcalc.tune(h, mon, self.target.get() / 100)
        if res is None:
            ui.inform(self, 'Balance', 'This hero cannot hurt it at all (its armour or defence is too high for his weapon). '
                      'Lower its armour or defence first, or pick another hero.')
            return
        life, power = res
        name = mon.get('name') or mon['id']
        with self.s.edit(f'Balance {name}', 'creatures', merge=None):
            mon['life'], mon['power'] = life, power
        self.page.inspector.refresh()
        self.refresh()
        self.page.app.say(f'{name} now has life {life} and power {power}.', 'ok')


class CreatureWizard(ui.Dialog):
    """Make a creature from a kind (brute, archer, mage, boss ...), give it a name and a toughness, and it exists."""

    def __init__(self, page):
        super().__init__(page, 'A new creature', width=px(760))
        self.page, self.s = page, page.s
        self.kinds = archetypes.available(self.s.project)
        self.kind = self.kinds[0] if self.kinds else None
        self.tier = 3
        ttk.Label(self.body, text='What kind of creature is it?', style='H2.TLabel').pack(anchor='w')
        ttk.Label(self.body, text='It starts as a copy of one that is already in the quest, so everything it needs is there. '
                  'Then make it your own.', style='Dim.TLabel', wraplength=px(700)).pack(anchor='w', pady=(0, px(8)))
        options = [(k.key, k.title, k.text, k.icon) for k in self.kinds]
        self.cards = ui.ChoiceCards(self.body, options, self._kind, options[0][0], columns=3, width=210)
        self.cards.pack(fill='x')
        row = ttk.Frame(self.body)
        row.pack(fill='x', pady=(px(12), 0))
        ttk.Label(row, text='Name').pack(side='left')
        self.name = tk.StringVar(value='New ' + self.kind.title.lower() if self.kind else 'New creature')
        e = ttk.Entry(row, textvariable=self.name, width=28)
        e.pack(side='left', padx=px(10))
        e.focus_set()
        e.select_range(0, 'end')
        ttk.Label(row, text='How tough').pack(side='left', padx=(px(16), px(6)))
        self.tier_box = ui.Number(row, 1, 10, 3, commit=self._tier, live=self._tier, width=3)
        self.tier_box.pack(side='left')
        self.preview = ttk.Label(self.body, text='', style='Dim.TLabel', wraplength=px(700))
        self.preview.pack(anchor='w', pady=(px(10), 0))
        self.paint_now = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.body, text='Open the painter afterwards, to draw its picture', variable=self.paint_now).pack(anchor='w', pady=(px(8), 0))
        self.add_buttons([('Cancel', None, 'TButton'), ('Make it', 'make', 'Accent.TButton')], default='make')
        self._preview()

    def _kind(self, key):
        self.kind = next(k for k in self.kinds if k.key == key)
        if self.name.get().startswith('New '):
            self.name.set('New ' + self.kind.title.lower())
        self._preview()

    def _tier(self, v):
        self.tier = v
        self._preview()

    def _preview(self):
        if not self.kind:
            return
        row, base = archetypes.make(self.s.project, self.kind, self.name.get(), self.tier)
        self.preview.configure(text=f'Starts as {base.get("name")}: life {row["life"]}, power {row["power"]}, attack {row["atk"]}, '
                                    f'defence {row["def"]}.   You can fine tune everything afterwards, and Balance sets it for a hero.')

    def close(self, value):
        if value == 'make' and self.kind:
            p = self.s.project
            row, base = archetypes.make(p, self.kind, self.name.get().strip() or 'New creature', self.tier)
            rid = row['id']
            with self.s.edit(f'New creature: {row["name"]}', 'creatures', ('pic', 'creatures', rid)):
                self.s.rows('creatures').append(row)
                self.s.rows('creatures').sort(key=lambda c: c['id'])
                img = p.picture('creatures', base['id'])
                if img is not None:
                    p.set_picture('creatures', rid, img)
            super().close(rid)
            return
        super().close(None)
