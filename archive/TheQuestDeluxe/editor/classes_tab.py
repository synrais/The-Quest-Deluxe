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


def drawn_hero(row) -> pygame.Surface:
    """The hero as the original's guy2() draws him for this class, on a transparent background."""
    from engine.anim import draw_guy2
    from engine.bgi import BGI
    key = (255, 0, 255)
    s = pygame.Surface((40, 40))
    s.fill(key)
    draw_guy2(BGI(s), 1, 1, row['id'], -1, 0, 0, 0, 0, 0, look=row.get('look') or {})
    out = pygame.Surface((40, 40), pygame.SRCALPHA)
    for x in range(40):
        for y in range(40):
            c = s.get_at((x, y))
            if tuple(c)[:3] != key:
                out.set_at((x, y), (*tuple(c)[:3], 255))
    return out


class ClassesTab(TableTab):
    TABLE = 'classes'
    GROUPS = [
        ('Starting numbers', True, 'what a new hero of this class starts with', ['life', 'mana', 'str', 'int', 'dex', 'acc']),
        ('Growing and skills', True, 'how he gains levels and what he can do',
         ['growth', 'skill', 'no_skill', 'no_fault', 'reclass']),
        ('Kit and spells', False, 'what he carries and knows at the start', ['bag', 'spells']),
        ('How he looks', False, 'colour and equipment shown', ['look.colour', 'look.shield_and_sword']),
    ]
    PICTURES = [('Painted hero', 'heroes', False)]
    INTRO = ('The classes a new hero can choose. Character creation lists them in this order, then the '
             "questionnaire (which picks between Quest I's four). The hero is drawn by the original's guy2() "
             'in the class colour; the Knight also carries a shield and sword. Or paint the hero: a painted picture '
             'takes the place of the drawn one (Paint starts from the drawn hero, or from another class).')

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
        painted = self.app.project.picture('heroes', row['id'])
        if painted is not None:
            s.blit(painted, (0, 0))
        else:
            draw_guy2(BGI(s), 1, 1, row['id'], -1, 0, 0, 0, 0, 0, look=row.get('look') or {})
        return s

    def start_picture(self, folder, row):
        return super().start_picture(folder, row) or drawn_hero(row)

    def templates(self, folder, row):
        """The drawn heroes of the classes, and the painted ones."""
        out = [(f'{r["id"]} {r.get("name", "")} (drawn)', lambda r=r: drawn_hero(r))
               for r in sorted(self.rows, key=lambda r: r['id'])]
        return out + super().templates(folder, row)

    def only_free_skills(self) -> list:
        """The skills that only come free with a class (Marksmanship): the game lists them for that class alone."""
        return [s['id'] for s in self.app.project.tables['skills'] if s['kind'] == 'skill' and s.get('only_free')]

    def _show(self, row):
        """Clicking a class shows what the game really does: a skill that only comes free with a class is not offered
        to the others, so it is ticked under "Not offered the skills" (and written there, which changes nothing in
        the game: it hides them already)."""
        if row is not None:
            have = row.get('no_skill')
            have = [have] if isinstance(have, str) else list(have or [])
            for sid in self.only_free_skills():
                if sid != row.get('skill') and sid not in have:
                    have.append(sid)
            if have != (row.get('no_skill') if isinstance(row.get('no_skill'), list) else
                        [row['no_skill']] if row.get('no_skill') else []):
                row['no_skill'] = have[0] if len(have) == 1 else have
        super()._show(row)

    def new_row(self):
        v = self.app.project.next_id('classes', 5)
        row = {'id': v, 'name': 'New class', 'life': 30, 'mana': 10, 'str': 12, 'int': 12, 'dex': 12, 'acc': 12,
               'growth': [4, 3], 'skill': 'bar', 'look': {'colour': 2}, 'bag': {'12,4': 201}, 'spells': []}
        free = self.only_free_skills()                      # a new class is not offered Marksmanship, as in the game
        if free:
            row['no_skill'] = free[0] if len(free) == 1 else free
        return row

    def uses(self, row):
        return []

    def set_picture(self, folder, surface, is_bag=False):
        super().set_picture(folder, surface, is_bag)
        self.app.map_tab.art.forget('mon', self.row['id'])
