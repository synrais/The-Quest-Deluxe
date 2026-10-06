"""The Tiles page: the floors, walls, doors and decorations a map is made of, with their pictures and what they do."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import icons, ui
from ..gallery import Entry
from ..model import TILE_KINDS
from ..theme import C, px
from .tablepage import TablePage

KINDS = [('floors', 'Floors'), ('walls', 'Walls and doors'), ('decos', 'Decorations')]
LAYER = {'floors': 'floor', 'walls': 'wall', 'decos': 'deco'}
NOUN = {'floors': 'floor', 'walls': 'wall', 'decos': 'decoration'}
GROUPS = {
    'floors': [('Floor', True, 'what stepping on it does', ['hurts', 'heals']),
               ('On the automap', False, 'the colour it shows in the map screen', ['map_colour', 'map_colour_on_level']),
               ('In FPS mode', False, 'a roof overhead indoors', ['roof'])],
    'walls': [('What it is', True, 'solid, a door, or water', ['solid', 'door', 'key', 'water', 'freezes_to']),
              ('Moved or broken', False, 'a boulder, a crack, a hedge', ['small_only', 'giant_breaks', 'needs_item', 'becomes',
                                                                         'consumes', 'message', 'blocked_message']),
              ('On the automap', False, 'the colour it shows in the map screen', ['map_colour', 'map_colour_on_level']),
              ('In FPS mode', False, 'how it looks in 3D', ['view3d'])],
    'decos': [('Decoration', True, 'what it does and what the engine uses it for', ['hurts', 'heals', 'role']),
              ('In FPS mode', False, 'how it looks in 3D', ['view3d'])]}


class TilesPage(TablePage):
    key = 'tiles'
    title = 'Tiles'
    icon = 'tiles'
    table = 'floors'
    nouns = 'tiles'
    filters = KINDS
    card = (90, 100)

    def build(self):
        self.table = self.app.settings.get('tiles_kind', 'floors')
        super().build()
        self.schema.set_kind(self.table)
        self.schema.groups_override = GROUPS[self.table]
        self.seg.choose(self.table, run=False)
        self.schema.t.after_change = self._after_change

    @property
    def layer(self):
        return LAYER[self.table]

    @layer.setter
    def layer(self, v):
        pass

    @property
    def noun(self):
        return NOUN[self.table]

    @noun.setter
    def noun(self, v):
        pass

    # the three kinds are the filter ---------------------------------------------
    def category(self, row):
        return self.table

    def _filter(self, key):
        if key == self.table:
            return
        self.table = key
        self.app.settings['tiles_kind'] = key
        self.schema.set_kind(key)
        self.schema.groups_override = GROUPS[key]
        self.rid = None
        self.query = ''
        self.search_box.clear()
        self.fill()
        self.rid = self.first_id()
        self.gallery.select(self.rid, scroll=True)
        self.show_row()

    def entries(self):
        out = []
        pic = self.s.pictures
        for r in sorted(self.rows(), key=lambda r: (r['id'] < 0, abs(r['id']))):
            out.append(Entry(r['id'], r.get('name') or '(no name)', f'#{r["id"]}', pic.thumb(self.layer, r['id'], 44, 'raised'),
                             search=f'{r.get("name", "")} {r["id"]}'.lower()))
        return out

    def first_id(self):
        rows = sorted(self.rows(), key=lambda r: (r['id'] < 0, abs(r['id'])))
        return rows[0]['id'] if rows else None

    def thumb_image(self, row, size, bg='raised', frame=False):
        return self.s.pictures.thumb(self.layer, row['id'], size, bg, frame)

    def badges(self, row):
        out = [(f'#{row["id"]}', 'dim')]
        if self.table == 'walls':
            door = row.get('door')
            if door:
                out.append((f'{door} door', 'warn'))
            elif row.get('water'):
                out.append(('water', 'info'))
            elif row.get('solid'):
                out.append(('solid', 'accent'))
            else:
                out.append(('walk through', 'ok'))
        if self.table == 'decos' and row.get('role'):
            out.append((row['role'].replace('_', ' '), 'info'))
        return out

    def pictures(self):
        return [('Picture', self.table, False)]

    def _changed(self, scope, source):
        if source is self.inspector or not self.built:
            return
        self.fill()
        if self.rid is not None and self.row() is None:
            self.rid = self.first_id()
        self.show_row()

    # what changes with a field ------------------------------------------------------
    def _after_change(self, row, key, old):
        p = self.s.project
        if key == 'freezes_to' and row.get('freezes_to') is not None:
            ice = next((w for w in p.tiles.get('walls', []) if w['id'] == row['freezes_to']), None)
            if ice is not None and ice.get('solid') and ui.confirm(self, 'Freezes to', f'"{ice.get("name")}" is solid, so nobody could walk '
                                                                  'on the ice. Make it walkable (not solid)?', 'Make it walkable'):
                ice.pop('solid', None)
        if key == 'door' and row.get('door') != 'locked':
            row.pop('key', None)
        if key == 'door' and row.get('door') == 'locked' and 'key' not in row:
            row['key'] = 'yellow'
        if key == 'role' and row.get('role'):
            for r in self.rows():
                if r is not row and r.get('role') == row['role']:
                    r.pop('role')
        self.s.pictures.forget(self.layer, row['id'])

    def new_row(self):
        used = {r['id'] for r in self.rows()}
        if self.table == 'walls' and ui.confirm(self, 'A new wall', 'Is it a door?\n(No makes a solid wall.)', 'A door', 'A wall'):
            v = next(n for n in range(-1, -1000, -1) if n not in used)
            return {'id': v, 'name': 'New door', 'door': 'plain'}
        v = 1
        while v in used or v == 0:
            v += 1
        return {'id': v, 'name': f'New {NOUN[self.table]}', **({'solid': True} if self.table == 'walls' else {})}

    def delete_extra(self, row):
        self.s.pictures.forget(self.layer, row['id'])
