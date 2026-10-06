"""The Heroes page: the classes a new hero can choose, with their starting stats, growth, skills, kit and look."""
from __future__ import annotations

import pygame

from editor.art import photo

from .. import ui
from ..theme import C, px
from .tablepage import TablePage


def _surface(project, row, size):
    """The hero as the game draws him for this class (or the painted picture), on grass, scaled."""
    from engine.anim import draw_guy2
    from engine.bgi import BGI
    s = pygame.Surface((40, 40))
    s.fill((0, 168, 0))
    painted = project.picture('heroes', row['id'])
    if painted is not None:
        s.blit(painted, (0, 0))
    else:
        draw_guy2(BGI(s), 1, 1, row['id'], -1, 0, 0, 0, 0, 0, look=row.get('look') or {})
    return pygame.transform.scale(s, (size, size))


class HeroesPage(TablePage):
    key = 'heroes'
    intro = 'These are the classes a player can be. Change what each starts with and how it grows, or make a new one.'
    title = 'Heroes'
    icon = 'helmet'
    table = 'classes'
    layer = 'mon'
    noun = 'class'
    nouns = 'classes'
    card = (94, 104)

    def thumb_image(self, row, size, bg='raised', frame=False):
        return photo(_surface(self.s.project, row, size))

    def picture_image(self, folder, row):
        return photo(_surface(self.s.project, row, px(96)))

    def entry_sub(self, row):
        return f'#{row["id"]}'

    def badges(self, row):
        return [(f'#{row["id"]}', 'dim'), (f'{row.get("life", 0)} life', 'ok'), (f'{row.get("mana", 0)} mana', 'info')]

    def start_picture(self, folder, row):
        from editor.classes_tab import drawn_hero
        return self.s.project.picture(folder, row['id']) or drawn_hero(row)

    def picture_templates(self, folder, row):
        from editor.classes_tab import drawn_hero
        out = [(f'{r["id"]} {r.get("name", "")} (drawn)', lambda r=r: drawn_hero(r)) for r in sorted(self.rows(), key=lambda r: r['id'])]
        return out + super().picture_templates(folder, row)

    def picture_set(self, rid, folder, surface):
        self.s.pictures.forget('mon', rid)

    def show_row(self):
        r = self.row()
        if r is not None:
            # a skill that only comes free with a class is never offered to the others: show it ticked, as the game treats it
            only = [s['id'] for s in self.s.rows('skills') if s.get('kind') == 'skill' and s.get('only_free')]
            have = r.get('no_skill')
            have = [have] if isinstance(have, str) else list(have or [])
            want = list(have)
            for sid in only:
                if sid != r.get('skill') and sid not in want:
                    want.append(sid)
            if want != have:
                r['no_skill'] = want[0] if len(want) == 1 else want
        super().show_row()

    def new_row(self):
        p = self.s.project
        row = {'id': p.next_id('classes', 5), 'name': 'New class', 'life': 30, 'mana': 10, 'str': 12, 'int': 12, 'dex': 12, 'acc': 12,
               'growth': [4, 3], 'skill': 'bar', 'look': {'colour': 2}, 'bag': {'12,4': 201}, 'spells': []}
        free = [s['id'] for s in self.s.rows('skills') if s.get('kind') == 'skill' and s.get('only_free')]
        if free:
            row['no_skill'] = free[0] if len(free) == 1 else free
        return row
