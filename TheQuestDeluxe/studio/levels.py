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


def put_generated(session, n: int, r, title=None, story_lines=(), new=True) -> int | None:
    """Write a generated level (worldgen.Result) as level n: a new last level when `new`, else over the map of level n (its events
    and shops stay unless the result has shops). Call it inside session.edit() with the scopes of that level (and 'texts' for a
    story). Returns the number of the story page it added, if any."""
    from . import levelmeta
    p = session.project
    if new:
        p.add_level()
        p.scripts[n] = LEVEL_SCRIPT.format(n=n)
    p.grids[n] = Grid(list(r.rows()))
    p.dirty |= {'quest', ('map', n), ('script', n), ('shops', n)}
    levelmeta.raw_put(p, n, 'START', tuple(r.start))
    levelmeta.raw_put(p, n, 'SHOPS', dict(r.shop_screens) or {})
    levelmeta.raw_put(p, n, 'PEACEFUL_SCREENS', list(r.peaceful))
    levelmeta.raw_put(p, n, 'DARK_SCREENS', list(r.dark))
    levelmeta.raw_put(p, n, 'TITLE', title or None)
    if r.shops:
        p.shops[n] = dict(r.shops)
    elif new:
        p.shops[n] = {}
    if not story_lines:
        return None
    from .storytext import add_story
    no = add_story(p, list(story_lines))
    levelmeta.raw_put(p, n, 'STORIES', [no] + [k for k in (levelmeta.get(session, n, 'STORIES', []) or []) if k != no])
    return no
