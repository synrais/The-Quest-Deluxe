"""The Tiles tab: floors, walls and doors, and decorations (tiles.json), with their pictures. Walls
are solid or a door (plain, a fake wall that opens the same way, or locked with a key colour); floors
and walls can colour the automap; decorations can have a role the engine puts them down for."""
from __future__ import annotations

from tkinter import ttk, messagebox

from .table_tab import TableTab, Field

KINDS = [('floors', 'Floors', 'floor'), ('walls', 'Walls and doors', 'wall'), ('decos', 'Decorations', 'deco')]
DOORS = [(None, '(not a door)'), ('plain', 'plain: opens when walked into'),
         ('fake', 'fake: a secret wall that opens the same way'), ('locked', 'locked: needs a key')]
WALL_LOOKS = [(None, '(by the picture: opaque = block)'), ('block', 'block: a solid cube'),
              ('billboard', 'billboard: standing up (trees)'), ('flat', 'flat: on the ground (water)')]
DECO_LOOKS = [(None, 'billboard: standing up'), ('flat', 'flat: on the ground (blood)')]
KEYS = [('yellow', 'yellow'), ('red', 'red'), ('blue', 'blue')]


def key_choices(quest, labels=None):
    """The original's three key colours, then the pack's own (quest.json's \"keys\", set on the Quest tab)."""
    out = [(k, (labels or {}).get(k, k)) for k, _ in KEYS]
    return out + [(k, k) for k in (quest.get('keys') or {}) if k not in dict(KEYS)]
ROLES = [(None, '(none)'), ('open_door', 'open door: where a door opened'),
         ('open_chest', 'open chest: an emptied chest'), ('remains', 'remains: where a creature died'),
         ('remains2', 'remains 2: the other kind of remains'), ('blood', 'blood: where a blow landed'),
         ('bones', 'bones: where a hero died')]


def fmt_colour(key):
    def fmt(row):
        c = row.get(key)
        return '' if not c else f'{c[0]}, {c[1]}'
    return fmt


def parse_colour(text):
    if not text.strip():
        return None
    parts = [int(v) for v in text.replace(',', ' ').split()]
    if len(parts) != 2 or not 0 <= parts[0] <= 15:
        raise ValueError('an EGA colour (0-15) and a priority, e.g. "8, 2"')
    return parts


def fmt_on_level(row):
    return '; '.join(f'{n}: {c[0]}, {c[1]}' for n, c in (row.get('map_colour_on_level') or {}).items())


def parse_on_level(text):
    out = {}
    for part in text.split(';'):
        if part.strip():
            level, colour = part.split(':')
            out[str(int(level))] = parse_colour(colour)
    return out or None


class TilesTab(TableTab):
    TABLE = 'tiles'
    INTRO = ('The squares of the map. Walls with numbers 1 and up are solid; doors take numbers below 0. '
             'Automap colour: an EGA colour and a priority. The floor\'s or the wall\'s colour with the higher '
             'priority wins; squares with neither are grass green.')

    def __init__(self, master, app):
        self.kind = 'floors'
        super().__init__(master, app)
        self.kinds = ttk.Combobox(self.buttons, state='readonly', width=18, values=[k[1] for k in KINDS])
        self.kinds.set(KINDS[0][1])
        self.kinds.pack(side='left', padx=(8, 0))
        self.kinds.bind('<<ComboboxSelected>>', lambda e: self.pick_kind(KINDS[self.kinds.current()][0]))

    def pick_kind(self, kind):
        self.kind = kind
        self.kinds.set(next(label for k, label, _ in KINDS if k == kind))
        self.load()

    @property
    def layer(self):
        return next(layer for k, _, layer in KINDS if k == self.kind)

    @property
    def ICON_LAYER(self):
        return self.layer

    @property
    def PICTURES(self):
        return [('Picture', self.kind, False)]

    @property
    def rows(self):
        return self.app.project.tiles.setdefault(self.kind, [])

    def fields(self):
        out = [Field('id', 'Number', 'readonly'), Field('name', 'Name', 'str')]
        if self.kind == 'walls':
            out += [Field('solid', 'Solid', 'bool', hint='blocks the way'),
                    Field('door', 'Door', 'choice', DOORS),
                    Field('key', 'Key', 'choice', key_choices(self.app.project.quest), when=lambda r: r.get('door') == 'locked',
                          hint='the key colour that opens it')]
        if self.kind in ('floors', 'walls'):
            out += [Field('map_colour', 'Automap colour', 'custom', fmt=fmt_colour('map_colour'),
                          parse=parse_colour, hint='colour, priority (e.g. 8, 2); empty: none'),
                    Field('map_colour_on_level', 'On a level', 'custom', fmt=fmt_on_level, parse=parse_on_level,
                          hint='other colours on some levels: "5: 8, 2; 7: 1, 1"')]
        if self.kind == 'decos':
            out.append(Field('role', 'Role', 'choice', ROLES, hint='what the engine puts it down for (one of each)'))
        if self.kind == 'walls':
            out.append(Field('view3d', 'In 3D', 'choice', WALL_LOOKS, hint='how FPS mode shows it'))
        if self.kind == 'decos':
            out.append(Field('view3d', 'In 3D', 'choice', DECO_LOOKS, hint='how FPS mode shows it'))
        if self.kind == 'floors':
            walls = [(None, '(open sky)')] + [(w['id'], f'{w["id"]} {w.get("name", "")}')
                                             for w in sorted(self.app.project.tiles.get('walls', []),
                                                             key=lambda w: w['id'])]
            out.append(Field('roof', 'Roof in 3D', 'choice', walls,
                             hint="indoors: FPS mode draws this wall's picture overhead"))
        return out

    def after_change(self, row, key, old):
        if key == 'door' and row.get('door') != 'locked':
            row.pop('key', None)
        if key == 'door' and row.get('door') == 'locked' and 'key' not in row:
            row['key'] = 'yellow'
        if key == 'role' and row.get('role'):
            for r in self.rows:                       # a role belongs to one decoration
                if r is not row and r.get('role') == row['role']:
                    r.pop('role')
        self.app.pictures_changed(self.layer, row['id'])

    def new_row(self):
        if self.kind == 'walls' and messagebox.askyesno('New', 'A door? (No makes a solid wall.)'):
            used = {r['id'] for r in self.rows}
            v = next(n for n in range(-1, -1000, -1) if n not in used)
            return {'id': v, 'name': 'New door', 'door': 'plain'}
        return {'id': self.next_free(1), 'name': f'New {self.layer}', **({'solid': True} if self.kind == 'walls' else {})}

    def next_free(self, start):
        used = {r['id'] for r in self.rows}
        v = start
        while v in used or v == 0:
            v += 1 if start > 0 else -1
        return v

    def duplicate_id(self, row):
        return self.next_free(1 if row['id'] > 0 else -1)

    def uses(self, row):
        p, out = self.app.project, []
        field = {'floors': 0, 'walls': 1, 'decos': 5}[self.kind]
        from .project import SIZE
        for n in range(1, p.levels + 1):
            g = p.grid(n)
            count = sum(1 for x in range(1, SIZE + 1) for y in range(1, SIZE + 1) if g.sq[x][y][field] == row['id'])
            if count:
                out.append(f'level {n} map: {count} square{"s" if count > 1 else ""}')
        if row.get('role'):
            out.append(f'the engine puts it down as {row["role"]}')
        return out
