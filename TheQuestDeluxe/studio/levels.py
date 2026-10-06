"""Adding, copying and removing levels: each is one undoable step."""
from __future__ import annotations

import copy

from editor.project import LEVEL_SCRIPT, Grid


def _scopes(n: int):
    return ('quest', ('map', n), ('script', n), ('shops', n))


def add_blank(session, grid_rows=None, script: str | None = None, shops: dict | None = None, label='Add a level') -> int:
    """A new last level: empty (or with the given squares, script and shops). Returns its number."""
    p = session.project
    n = p.levels + 1
    with session.edit(label, *_scopes(n)):
        p.add_level()
        if grid_rows is not None:
            p.grids[n] = Grid(grid_rows)
        if script is not None:
            p.scripts[n] = script
        if shops is not None:
            p.shops[n] = dict(shops)
        p.dirty |= {'quest', ('map', n), ('script', n), ('shops', n)}
    return n


def duplicate(session, n: int) -> int:
    """A copy of level n, as the new last level."""
    p = session.project
    rows = list(p.grid(n).rows())
    script = p.scripts.get(n, LEVEL_SCRIPT.format(n=n))
    return add_blank(session, rows, script.replace(f'Level {n} ', f'Level {p.levels + 1} ', 1), copy.deepcopy(p.shops.get(n, {})),
                     label=f'Copy level {n}')


def remove_last(session) -> bool:
    p = session.project
    n = p.levels
    if n <= 1:
        return False
    with session.edit(f'Remove level {n}', *_scopes(n)):
        p.remove_last_level()
    return True
