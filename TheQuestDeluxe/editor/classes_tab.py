"""The Classes tab: the hero classes new games can choose, their starting stats, growth, skills,
starting kit and how the hero is drawn."""
from __future__ import annotations

import pygame

from engine.state import BACKPACK
from .table_tab import TableTab, Field

EGA_NAMES = ['black', 'blue', 'green', 'cyan', 'red', 'magenta', 'brown', 'light grey', 'dark grey', 'light blue',
             'light green', 'light cyan', 'light red', 'light magenta', 'yellow', 'white']
SLOTS = {'weapon': (12, 4), 'off hand': (16, 4), 'helmet': (14, 2), 'armour': (14, 4), 'amulet': (14, 6)}


def fmt_bag(row) -> str:
    bag = {tuple(int(v) for v in k.split(',')): it for k, it in (row.get('bag') or {}).items()}
    parts = [f'{name}: {bag[cell]}' for name, cell in SLOTS.items() if bag.get(cell)]
    pack = [str(bag[c]) for c in BACKPACK if bag.get(c)]
    if pack:
        parts.append('backpack: ' + ' '.join(pack))
    return '; '.join(parts)


def parse_bag(text: str) -> dict:
    out = {}
    for part in text.split(';'):
        if not part.strip():
            continue
        name, items = part.split(':')
        name = name.strip().lower()
        if name == 'backpack':
            for cell, it in zip(BACKPACK, items.split()):
                out[f'{cell[0]},{cell[1]}'] = int(it)
        elif name in SLOTS:
            c = SLOTS[name]
            out[f'{c[0]},{c[1]}'] = int(items)
        else:
            raise ValueError(f'the places are {", ".join(SLOTS)} and backpack')
    return out


def fmt_growth(row) -> str:
    g = row.get('growth') or (0, 0)
    return f'{g[0]}, {g[1]}'


def parse_growth(text: str) -> list:
    a, b = (int(v) for v in text.replace(',', ' ').split())
    return [a, b]


def one_as_name(f: Field) -> Field:
    """A list field that keeps a single choice as the plain name, as Quest I's classes.json has it."""
    f.one_as_name = True
    return f


class ClassesTab(TableTab):
    TABLE = 'classes'
    INTRO = ('The classes a new hero can choose. Character creation lists them in this order, then the '
             "questionnaire (which picks between Quest I's four). The hero is drawn by the original's guy2() "
             'in the class colour; the Knight also carries a shield and sword.')

    def fields(self):
        p = self.app.project
        skills = [(s['id'], s['name']) for s in p.tables['skills'] if s['kind'] == 'skill']
        faults = [(s['id'], s['name']) for s in p.tables['skills'] if s['kind'] == 'fault']
        spells = [(s['id'], f'{s["id"]} {s["name"]}') for s in sorted(p.tables['spells'], key=lambda s: s['id'])]
        return [
            Field('id', 'Number', 'readonly'),
            Field('name', 'Name', 'str'),
            Field('life', 'Life', 'int', default=0),
            Field('mana', 'Mana', 'int', default=0),
            Field('str', 'Strength', 'int', default=0),
            Field('int', 'Intelligence', 'int', default=0),
            Field('dex', 'Dexterity', 'int', default=0),
            Field('acc', 'Accuracy', 'int', default=0),
            Field('growth', 'Gains per level', 'custom', fmt=fmt_growth, parse=parse_growth,
                  hint='life, mana (the Knight: 7, 3)'),
            Field('skill', 'Free skill', 'choice', skills),
            one_as_name(Field('no_skill', 'Not offered the skills', 'multi', skills,
                              hint='hidden from this class at creation (as Marksmanship is from all but Rogues)')),
            one_as_name(Field('no_fault', 'Not offered the faults', 'multi', faults,
                              hint="hidden from this class at creation (a Knight can't be a coward)")),
            Field('look.colour', 'Colour', 'choice', list(enumerate(EGA_NAMES)), default=0),
            Field('look.shield_and_sword', 'Shield and sword', 'bool'),
            Field('bag', 'Starts with', 'custom', fmt=fmt_bag, parse=parse_bag,
                  hint='item numbers, e.g. weapon: 201; off hand: 301; backpack: 230 620'),
            Field('spells', 'Knows the spells', 'multi', spells),
            Field('reclass', 'Class changes', 'choice', [(None, 'can be left and become at level-ups'),
                                                         (False, 'never: kept, and never become')],
                  hint="the Quest tab says whether classes change at level-ups"),
        ]

    def preview(self, row):
        from engine.anim import draw_guy2
        from engine.bgi import BGI
        s = pygame.Surface((40, 40))
        s.fill((0, 168, 0))                                  # on grass, as in the game
        draw_guy2(BGI(s), 1, 1, row['id'], -1, 0, 0, 0, 0, 0, look=row.get('look') or {})
        return s

    def new_row(self):
        v = self.app.project.next_id('classes', 5)
        return {'id': v, 'name': 'New class', 'life': 30, 'mana': 10, 'str': 12, 'int': 12, 'dex': 12, 'acc': 12,
                'growth': [4, 3], 'skill': 'bar', 'look': {'colour': 2}, 'bag': {'12,4': 201}, 'spells': []}

    def uses(self, row):
        return []
