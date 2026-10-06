"""A level's settings (the constants at the top of its script) and its landmarks (start, exits, links, entries, shops)."""
from __future__ import annotations

from editor.project import SIZE

LINK_TYPES = ('ladder', 'rope', 'stairs', 'hole', 'jump_pad')
MARKER_TYPES = ('exit', 'teleporter') + LINK_TYPES

COMMENTS = {
    'START': 'where the hero arrives', 'STORIES': 'story screens shown before the level',
    'SHOPS': 'screen (column, row) -> shop number', 'TELEPORT': 'how far a teleporter pad moves the hero',
    'ASK_TO_LEAVE': 'ask before leaving by the exit', 'LEAVE_JINGLE': 'play the jingle when leaving',
    'PEACEFUL_SCREENS': "screens where people and allies don't attack monsters",
    'DARK_SCREENS': 'screens where only the hero and his light show', 'LINKS': 'square -> where a ladder, stairs or exit leads',
    'ENTRIES': 'name -> (x, y): a way in other levels can link to', 'RESPAWN': 'where he wakes after dying here',
    'TITLE': 'what this level is called in the editor', 'SKY_3D': '3D sky colour', 'FOG_3D': '3D fog colour', 'RANGE_3D': '3D view distance',
}


def get(session, level: int, name: str, default=None):
    return session.project.constant(level, name, default)


def raw_put(project, level: int, name: str, value):
    """Set a constant without a history step (inside a larger edit). None or an empty list/dict removes it."""
    empty = value is None or value == [] or value == {}
    if empty:
        project.remove_constant(level, name)
    elif project.constant(level, name) != value:
        project.set_constant(level, name, value, COMMENTS.get(name, ''))


def put(session, level: int, name: str, value, label=None):
    """Set a constant (None or an empty list/dict removes it), as one undoable step."""
    p = session.project
    empty = value is None or value == [] or value == {}
    if empty and p.constant(level, name) is None:
        return
    if not empty and p.constant(level, name) == value:
        return
    with session.edit(label or f'Change {name.lower().replace("_", " ")}', ('script', level), merge=f'const:{level}:{name}'):
        raw_put(p, level, name, value)


def title(session, n: int) -> str:
    """What a level is called in lists: its TITLE if it has one, else 'Level n'."""
    t = session.project.constant(n, 'TITLE')
    return t if isinstance(t, str) and t.strip() else f'Level {n}'


def toggle_screen(session, level: int, name: str, screen: tuple, label: str):
    cur = [tuple(v) for v in (get(session, level, name, []) or [])]
    if screen in cur:
        cur.remove(screen)
    else:
        cur.append(screen)
    put(session, level, name, sorted(cur), label)
    return screen in cur


def start_of(session, level: int) -> tuple:
    v = get(session, level, 'START', (5, 5))
    return tuple(v) if v else (5, 5)


def screen_of(x: int, y: int) -> tuple:
    return ((x - 1) // 10 + 1, (y - 1) // 10 + 1)


def landmarks(session, level: int) -> dict:
    """Everything worth a marker on a level: start, exits, links, teleporters, entries, shops, respawn, screens."""
    p = session.project
    g = p.grid(level)
    types = {r['id']: r.get('type', '') for r in p.tables['items']}
    links = get(session, level, 'LINKS', {}) or {}
    out = {'start': start_of(session, level), 'exits': [], 'links': [], 'teleporters': [],
           'entries': dict(get(session, level, 'ENTRIES', {}) or {}), 'shops': dict(get(session, level, 'SHOPS', {}) or {}),
           'respawn': get(session, level, 'RESPAWN'), 'peaceful': [tuple(v) for v in get(session, level, 'PEACEFUL_SCREENS', []) or []],
           'dark': [tuple(v) for v in get(session, level, 'DARK_SCREENS', []) or []], 'links_map': links}
    for x in range(1, SIZE + 1):
        col = g.sq[x]
        for y in range(1, SIZE + 1):
            item = col[y][2]
            if not item:
                continue
            kind = types.get(item, '')
            if kind == 'exit':
                out['exits'].append((x, y, item))
            elif kind in LINK_TYPES:
                out['links'].append((x, y, item))
            elif kind == 'teleporter':
                out['teleporters'].append((x, y, item))
    return out


def describe_destination(session, level: int, x: int, y: int, kind: str) -> str:
    """Where the exit or link at a square leads, in words."""
    link = (get(session, level, 'LINKS', {}) or {}).get((x, y))
    if not link:
        if kind == 'exit':
            return f'on to level {level + 1}' if level < session.levels else 'the ending'
        return 'leads nowhere yet'
    to = link[0]
    if len(link) == 1:
        return f'level {to}, at its start'
    if len(link) == 2 and isinstance(link[1], str):
        return f'level {to}, at the entry "{link[1]}"'
    return f'level {to}, at ({link[1]}, {link[2]})'


def set_link(session, level: int, x: int, y: int, target):
    """target: None (remove), (level,), (level, 'entry'), or (level, x, y [, text])."""
    links = dict(get(session, level, 'LINKS', {}) or {})
    if target is None:
        links.pop((x, y), None)
    else:
        links[(x, y)] = tuple(target)
    put(session, level, 'LINKS', links, 'Link a square to another level')


def clear_dangling(session, level: int):
    """Drop LINKS entries for squares that no longer hold a link or exit item."""
    marks = landmarks(session, level)
    spots = {(x, y) for x, y, _ in marks['exits'] + marks['links'] + marks['teleporters']}
    links = dict(marks['links_map'])
    kept = {k: v for k, v in links.items() if k in spots}
    if kept != links:
        put(session, level, 'LINKS', kept, 'Tidy links')


def exit_item(session):
    """The item an exit is made of (the first of type 'exit'), or None."""
    return next((r['id'] for r in session.project.tables['items'] if r.get('type') == 'exit'), None)


def link_item(session, kind: str):
    return next((r['id'] for r in session.project.tables['items'] if r.get('type') == kind), None)


def link_spec(session, level: int, x: int, y: int):
    """The link of a square as a dict for the editor: {'level', 'mode': 'start'|'entry'|'square', 'entry', 'x', 'y', 'text'}."""
    link = (get(session, level, 'LINKS', {}) or {}).get((x, y))
    if not link:
        return None
    to = link[0]
    if len(link) == 1:
        return {'level': to, 'mode': 'start', 'entry': '', 'x': 0, 'y': 0, 'text': ''}
    if len(link) == 2 and isinstance(link[1], str):
        return {'level': to, 'mode': 'entry', 'entry': link[1], 'x': 0, 'y': 0, 'text': ''}
    return {'level': to, 'mode': 'square', 'entry': '', 'x': link[1], 'y': link[2], 'text': link[3] if len(link) > 3 else ''}


def apply_link(session, level: int, x: int, y: int, item: int | None, spec: dict | None, kind: str, back: bool = False):
    """Make (or remove) the link of a square, putting `item` there if given; with `back`, the way back at the other end too.
    One undoable step."""
    p = session.project
    scopes = [('map', level), ('script', level)]
    target = spec['level'] if spec is not None else None
    if back and target is not None and target != level:
        scopes += [('map', target), ('script', target)]
    with session.edit('Link an exit' if kind == 'exit' else f'Link a {kind.replace("_", " ")}', *dict.fromkeys(scopes)):
        if item is not None:
            p.grid(level).sq[x][y][2] = item
        links = dict(get(session, level, 'LINKS', {}) or {})
        if spec is None:
            links.pop((x, y), None)
        else:
            mode = spec['mode']
            if mode == 'start':
                if kind == 'exit':
                    links[(x, y)] = (target,)
                else:
                    sx, sy = start_of(session, target)
                    links[(x, y)] = (target, sx, sy)
            elif mode == 'entry':
                links[(x, y)] = (target, spec['entry'])
            else:
                links[(x, y)] = (target, spec['x'], spec['y'], spec['text']) if spec['text'] else (target, spec['x'], spec['y'])
        raw_put(p, level, 'LINKS', links)
        if back and spec is not None:
            tx, ty = resolve(session, links[(x, y)], target)
            other = dict(get(session, target, 'LINKS', {}) or {})
            other[(tx, ty)] = (level, x, y)
            raw_put(p, target, 'LINKS', other)
            sq = p.grid(target).sq[tx][ty]
            if not sq[2] and item is not None:
                sq[2] = item
            elif not sq[2]:
                sq[2] = p.grid(level).sq[x][y][2]


def resolve(session, link, level=None):
    """The square a link lands on: (x, y)."""
    if len(link) == 1:
        return start_of(session, link[0])
    if len(link) == 2 and isinstance(link[1], str):
        sq = (get(session, link[0], 'ENTRIES', {}) or {}).get(link[1])
        return tuple(sq) if sq else start_of(session, link[0])
    return link[1], link[2]
