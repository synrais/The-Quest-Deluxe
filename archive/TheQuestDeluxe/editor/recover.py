"""Pictures without an entry: after an update replaced the tables (items.json, creatures.json ...) the pictures in
sprites/ stay, so a picture can be there with nothing to say what it is. This finds them and makes a plain entry
for each ("Recovered item 2500"), so they can be reached and filled in again. No tkinter here."""
from __future__ import annotations

import copy

# (the table the pictures belong to, [sprite folders])
KINDS = [('items', ['items', 'bag']), ('creatures', ['creatures']), ('spells', ['spells']), ('classes', ['heroes']),
         ('floors', ['floors']), ('walls', ['walls']), ('decos', ['decos'])]


def rows_of(project, table: str) -> list:
    return project.tiles.setdefault(table, []) if table in ('floors', 'walls', 'decos') else project.tables[table]


def orphans(project) -> dict:
    """{table: [numbers]} of pictures that have no entry in their table."""
    out = {}
    for table, folders in KINDS:
        have = {r['id'] for r in rows_of(project, table)}
        ids = sorted({v for f in folders for v in project.picture_ids(f)} - have)
        if ids:
            out[table] = ids
    return out


def make_row(project, table: str, v: int) -> dict:
    name = {'items': 'item', 'creatures': 'creature', 'spells': 'spell', 'classes': 'class', 'floors': 'floor',
            'walls': 'wall', 'decos': 'decoration'}[table]
    label = f'Recovered {name} {v}'
    if table == 'items':
        return {'id': v, 'name': label, 'type': 'treasure'}
    if table == 'creatures':
        att = 9 if v > 0 else -2 if v > -100 else -3
        return {'id': v, 'name': label, 'life': 10, 'power': 3, 'atk': 60, 'def': 10, 'warm': 0, 'marm': 0, 'range': 1,
                'att': att, 'exp': 10 if v > 0 else 0, 'loot': []}
    if table in ('spells', 'classes'):
        rows = rows_of(project, table)
        row = copy.deepcopy(rows[0]) if rows else {}
        row.update({'id': v, 'name': label})
        return row
    return {'id': v, 'name': label}


def recover(project) -> list:
    """Make an entry for every picture without one. Returns what was made, as text."""
    made = []
    for table, ids in orphans(project).items():
        for v in ids:
            row = make_row(project, table, v)
            rows_of(project, table).append(row)
            made.append(f'{table[:-1] if table.endswith("s") else table} {v}')
        project.touch('tiles' if table in ('floors', 'walls', 'decos') else table)
    return made
