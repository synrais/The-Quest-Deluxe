"""The Quest Doctor: reads the whole quest and says what is missing, broken or just odd, in plain words, with where to go to fix it.

check(session) -> [Problem]. Nothing here knows about windows. A problem has a severity ('error' stops something working,
'warn' is probably a mistake, 'info' is worth knowing), the part of the Studio it belongs to, a title, a detail, where to go
to look at it (`go`: a page key and its arguments) and, sometimes, a fix the Doctor can make itself (`fixer`).
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field

from core.project import SIZE

from . import levelmeta

LINK_TYPES = levelmeta.LINK_TYPES


@dataclass
class Problem:
    severity: str
    area: str
    title: str
    detail: str = ''
    go: tuple | None = None
    fix: str = ''
    fixer: object = None
    key: str = ''


def lv(n):
    return f'level {n}'


class Facts:
    """The things the checks look things up in, made once."""

    def __init__(self, session):
        p = session.project
        self.s, self.p = session, p
        self.items = {r['id']: r for r in p.tables['items']}
        self.creatures = {r['id']: r for r in p.tables['creatures']}
        self.spells = {r['id']: r for r in p.tables['spells']}
        self.classes = {r['id']: r for r in p.tables['classes']}
        self.floors = {r['id']: r for r in p.tiles.get('floors', [])}
        self.walls = {r['id']: r for r in p.tiles.get('walls', [])}
        self.decos = {r['id']: r for r in p.tiles.get('decos', [])}
        self.levels = p.levels


def passable(f: Facts, wa: int) -> bool:
    """Can the hero (with luck: a key, a potion, an item) walk into a square with this wall? Secret doors and doors count."""
    if not wa:
        return True
    w = f.walls.get(wa)
    if w is None:
        return False
    if w.get('door') or w.get('needs_item') or w.get('small_only') or w.get('giant_breaks'):
        return True
    return not w.get('solid')


def reach(f: Facts, grid, start) -> set:
    seen = {start}
    q = deque([start])
    sq = grid.sq
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 1 <= nx <= SIZE and 1 <= ny <= SIZE and (nx, ny) not in seen and passable(f, sq[nx][ny][1]):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


# ── levels ───────────────────────────────────────────────────────────────────
def check_levels(f: Facts, out: list):
    s = f.s
    used_floor, used_wall, used_deco = {}, {}, {}
    exit_types = {i for i, r in f.items.items() if r.get('type') == 'exit'}
    for n in range(1, f.levels + 1):
        g = f.p.grid(n)
        sq = g.sq
        exits, links, unknown = [], [], {'item': {}, 'mon': {}, 'floor': {}, 'wall': {}, 'deco': {}}
        for x in range(1, SIZE + 1):
            col = sq[x]
            for y in range(1, SIZE + 1):
                fl, wa, it, mo, go, de = col[y]
                if it:
                    if it not in f.items:
                        unknown['item'].setdefault(it, (x, y, 0))
                        unknown['item'][it] = (unknown['item'][it][0], unknown['item'][it][1], unknown['item'][it][2] + 1)
                    elif f.items[it].get('type') == 'exit':
                        exits.append((x, y))
                    elif f.items[it].get('type') in LINK_TYPES:
                        links.append((x, y))
                if mo and mo not in f.creatures:
                    a = unknown['mon'].setdefault(mo, [x, y, 0])
                    a[2] += 1
                if fl and fl not in f.floors:
                    a = unknown['floor'].setdefault(fl, [x, y, 0])
                    a[2] += 1
                if wa and wa not in f.walls:
                    a = unknown['wall'].setdefault(wa, [x, y, 0])
                    a[2] += 1
                if de and de not in f.decos:
                    a = unknown['deco'].setdefault(de, [x, y, 0])
                    a[2] += 1
        word = {'item': 'item', 'mon': 'creature', 'floor': 'floor', 'wall': 'wall', 'deco': 'decoration'}
        for kind, found in unknown.items():
            for v, (x, y, count) in found.items():
                out.append(Problem('error', 'World', f'Level {n} uses {word[kind]} {v}, which does not exist',
                                   f'{count} square{"s" if count != 1 else ""}; the first is at ({x}, {y}). The game would draw nothing there, or fail.',
                                   ('world', {'level': n, 'at': (x, y)}), 'Remove them from the map',
                                   (lambda sess, n=n, kind=kind, v=v: _remove_from_map(sess, n, kind, v)), key=f'unk:{n}:{kind}:{v}'))
        # start
        start = levelmeta.start_of(s, n)
        sx, sy = start
        sw = sq[sx][sy][1] if 1 <= sx <= SIZE and 1 <= sy <= SIZE else -9999
        if not (1 <= sx <= SIZE and 1 <= sy <= SIZE):
            out.append(Problem('error', 'World', f'The start of level {n} is off the map', f'START is ({sx}, {sy}).', ('world', {'level': n, 'panel': 'level'}), key=f'start:{n}'))
        elif sw and not passable(f, sw):
            out.append(Problem('error', 'World', f'The hero starts inside a wall on level {n}', f'The start square ({sx}, {sy}) is solid.',
                               ('world', {'level': n, 'at': start, 'tool': 'start'}), key=f'start:{n}'))
        # a way out
        script = s.project.scripts.get(n, '')
        if not exits and not links and 'next_level' not in script:
            events = bool(re.search(r'^def \w+\(', script, flags=re.M))                 # it has handlers of its own: they may end the level
            out.append(Problem('info' if events else 'warn', 'World', f'Level {n} has no way out',
                               'There is no exit, ladder or stairs on the map' + (', though its events may end it' if events else ', and no event sends the hero on')
                               + '. Put an Exit on the map (World page, Places).', ('world', {'level': n, 'panel': 'places'}), key=f'noexit:{n}'))
        # reachability
        if 1 <= sx <= SIZE and 1 <= sy <= SIZE and (not sw or passable(f, sw)):
            seen = reach(f, g, start)
            lost_exit = [e for e in exits if e not in seen]
            if exits and len(lost_exit) == len(exits):
                x, y = lost_exit[0]
                out.append(Problem('error', 'World', f'The hero cannot reach the exit of level {n}', f'The exit at ({x}, {y}) is walled in or across water from the start ({sx}, {sy}).',
                                   ('world', {'level': n, 'at': (x, y)}), key=f'lostexit:{n}'))
            lost = 0
            first = None
            for x in range(1, SIZE + 1):
                for y in range(1, SIZE + 1):
                    fl, wa, it, mo, go, de = sq[x][y]
                    if (it or go > 0 or mo > 0) and (x, y) not in seen and passable(f, wa):
                        if it in exit_types:
                            continue
                        lost += 1
                        first = first or (x, y)
            if lost > 5:
                out.append(Problem('info', 'World', f'{lost} things on level {n} cannot be reached from the start', f'Items, gold or creatures in areas the hero cannot walk to; the first is at {first}. '
                                   'That is fine for a secret or a scenery creature.', ('world', {'level': n, 'at': first}), key=f'lost:{n}'))
        # links
        links_map = levelmeta.get(s, n, 'LINKS', {}) or {}
        marks = levelmeta.landmarks(s, n)
        spots = {(x, y) for x, y, _ in marks['exits'] + marks['links'] + marks['teleporters']}
        for (x, y), link in links_map.items():
            to = link[0]
            if (x, y) not in spots:
                out.append(Problem('warn', 'World', f'A link on level {n} leads from a square with no stairs or exit', f'LINKS has an entry for ({x}, {y}), but nothing there.',
                                   ('world', {'level': n, 'at': (x, y)}), 'Remove the link', (lambda sess, n=n: levelmeta.clear_dangling(sess, n)), key=f'dangle:{n}:{x}:{y}'))
            if not 1 <= to <= f.levels:
                out.append(Problem('error', 'World', f'An exit on level {n} leads to level {to}, which does not exist', f'The link at ({x}, {y}).',
                                   ('world', {'level': n, 'at': (x, y), 'tool': 'exit'}), key=f'badlink:{n}:{x}:{y}'))
                continue
            if len(link) == 2 and isinstance(link[1], str):
                if link[1] not in (levelmeta.get(s, to, 'ENTRIES', {}) or {}):
                    out.append(Problem('error', 'World', f'A link on level {n} goes to an entry "{link[1]}" that level {to} does not have', f'The link at ({x}, {y}).',
                                       ('world', {'level': n, 'at': (x, y)}), key=f'badentry:{n}:{x}:{y}'))
            elif len(link) >= 3:
                tx, ty = link[1], link[2]
                if not (1 <= tx <= SIZE and 1 <= ty <= SIZE):
                    out.append(Problem('error', 'World', f'A link on level {n} goes off the map of level {to}', f'It lands on ({tx}, {ty}).', ('world', {'level': n, 'at': (x, y)}), key=f'offmap:{n}:{x}:{y}'))
                else:
                    twall = f.p.grid(to).sq[tx][ty][1]
                    if twall and not passable(f, twall):
                        out.append(Problem('error', 'World', f'A link on level {n} lands inside a wall of level {to}', f'It lands on ({tx}, {ty}).', ('world', {'level': n, 'at': (x, y)}), key=f'inwall:{n}:{x}:{y}'))
        for x, y, item in marks['links']:
            if (x, y) not in links_map:
                out.append(Problem('warn', 'World', f'A {f.items[item].get("type", "link")} on level {n} leads nowhere',
                                   f'The one at ({x}, {y}) has no destination: the hero would hear "It leads nowhere".', ('world', {'level': n, 'at': (x, y), 'panel': 'places'}), key=f'nolink:{n}:{x}:{y}'))
        # shops
        shops = levelmeta.get(s, n, 'SHOPS', {}) or {}
        for sc, k in shops.items():
            if k not in s.project.shops.get(n, {}):
                out.append(Problem('error', 'Shops', f'Screen {sc} of level {n} has shop {k}, which has no stock file', 'The shop screen would be empty.',
                                   ('shops', {'level': n}), key=f'shopmissing:{n}:{k}'))
            else:
                has_keeper = any(sq[x][y][3] == -5 for x in range((sc[0] - 1) * 10 + 1, sc[0] * 10 + 1) for y in range((sc[1] - 1) * 10 + 1, sc[1] * 10 + 1))
                if not has_keeper:
                    out.append(Problem('warn', 'Shops', f'The shop on screen {sc} of level {n} has no shopkeeper',
                                       'Shops open when the hero talks to a shopkeeper (creature -5) on that screen.', ('world', {'level': n, 'at': ((sc[0] - 1) * 10 + 5, (sc[1] - 1) * 10 + 5)}), key=f'nokeeper:{n}:{sc}'))
        for k, text in s.project.shops.get(n, {}).items():
            for v in text.split():
                if v.lstrip('-').isdigit() and int(v) and int(v) not in f.items:
                    out.append(Problem('error', 'Shops', f'Shop {k} of level {n} sells item {v}, which does not exist', '', ('shops', {'level': n, 'shop': k}), key=f'shopitem:{n}:{k}:{v}'))
                elif v.lstrip('-').isdigit() and int(v) in f.items and not f.items[int(v)].get('price'):
                    out.append(Problem('warn', 'Shops', f'Shop {k} of level {n} sells {f.items[int(v)].get("name") or v} with no price', 'Give the item a price on the Items page.',
                                       ('items', {'select': int(v)}), key=f'noprice:{n}:{k}:{v}'))
        # stories
        from engine.formats import parse_story
        have = parse_story(s.project.texts['stories'])
        for st in levelmeta.get(s, n, 'STORIES', []) or []:
            if st not in have:
                out.append(Problem('error', 'Story', f'Level {n} shows story {st}, which does not exist', '', ('story', {'tab': 'stories'}), key=f'nostory:{n}:{st}'))
        # screens
        for name, label in (('PEACEFUL_SCREENS', 'peaceful'), ('DARK_SCREENS', 'dark')):
            for sc in levelmeta.get(s, n, name, []) or []:
                if not (1 <= sc[0] <= 10 and 1 <= sc[1] <= 10):
                    out.append(Problem('warn', 'World', f'Level {n} has a {label} screen off the map', f'Screen {tuple(sc)}.', ('world', {'level': n, 'panel': 'places'}), key=f'screen:{n}:{name}:{sc}'))
        # the script
        try:
            from engine.script import Script, ScriptError
            Script(script, f'level {n}')
        except SyntaxError as e:
            out.append(Problem('error', 'Events', f'The events of level {n} have a mistake on line {e.lineno}', e.msg, ('events', {'level': n}), key=f'script:{n}'))
        except Exception as e:                                  # noqa: BLE001 - ScriptError and friends
            out.append(Problem('error', 'Events', f'The events of level {n} cannot be read', str(e)[:200], ('events', {'level': n}), key=f'script:{n}'))


def _remove_from_map(session, n, kind, v):
    idx = {'item': 2, 'mon': 3, 'floor': 0, 'wall': 1, 'deco': 5}[kind]
    blank = 1 if kind == 'floor' else 0
    g = session.project.grid(n)
    with session.edit(f'Remove {kind} {v} from level {n}', ('map', n)):
        for x in range(1, SIZE + 1):
            for y in range(1, SIZE + 1):
                if g.sq[x][y][idx] == v:
                    g.sq[x][y][idx] = blank


# ── creatures, items, spells, tiles, heroes, quest ───────────────────────────────
def used_on_maps(f: Facts):
    items, mons = set(), set()
    for n in range(1, f.levels + 1):
        sq = f.p.grid(n).sq
        for x in range(1, SIZE + 1):
            for y in range(1, SIZE + 1):
                c = sq[x][y]
                if c[2]:
                    items.add(c[2])
                if c[3]:
                    mons.add(c[3])
    return items, mons


def check_creatures(f: Facts, out: list):
    p = f.p
    _, on_map = used_on_maps(f)
    for c in p.tables['creatures']:
        cid, name = c['id'], c.get('name') or f'#{c["id"]}'
        go = ('creatures', {'select': cid})
        if cid > 0 and p.picture('creatures', cid) is None:
            out.append(Problem('warn', 'Creatures', f'{name} has no picture', 'It would be drawn as a grey square. Paint it on the Creatures page.', go, key=f'nopic:mon:{cid}'))
        if (c.get('life') or 0) <= 0 and cid > 0:
            out.append(Problem('warn', 'Creatures', f'{name} has no life', 'It dies as soon as it appears.', go, key=f'nolife:{cid}'))
        if cid > 0 and (c.get('atk') or 0) == 0 and (c.get('range') or 1) == 1 and not c.get('cast_anim') and not c.get('heals_allies') and (c.get('att', 9) or 0) > 0:
            out.append(Problem('info', 'Creatures', f'{name} can neither fight nor cast', 'Attack 0 with range 1 means it never hurts anyone. Fine for a harmless creature.', go, key=f'toothless:{cid}'))
        for k in ('raises_dead', 'reveals_as', 'hides_as', 'becomes_on_death', 'transforms_into'):
            v = c.get(k)
            if v and v not in f.creatures:
                out.append(Problem('error', 'Creatures', f'{name} refers to creature {v}, which does not exist', f'Its "{k.replace("_", " ")}" setting.', go, key=f'ref:{cid}:{k}'))
        for rule in (c.get('loot') or []) + (c.get('hit_drops') or []):
            if len(rule) >= 4 and rule[2] == 'item' and rule[3] not in f.items:
                out.append(Problem('error', 'Creatures', f'{name} drops item {rule[3]}, which does not exist', '', go, key=f'loot:{cid}:{rule[3]}'))
        for k, v in (c.get('bursts_into') or {}).items():
            if int(k) not in f.creatures:
                out.append(Problem('error', 'Creatures', f'{name} bursts into creature {k}, which does not exist', '', go, key=f'burst:{cid}:{k}'))
    unused = [c for c in p.tables['creatures'] if c['id'] > 0 and c['id'] not in on_map and p.picture('creatures', c['id']) is not None]
    made = set()
    for c in p.tables['creatures']:
        for k in ('raises_dead', 'reveals_as', 'hides_as', 'becomes_on_death', 'transforms_into'):
            if c.get(k):
                made.add(c[k])
    for sp in p.tables['spells']:
        if sp.get('creature'):
            made.add(sp['creature'])
    unused = [c for c in unused if c['id'] not in made]
    if unused and f.levels:
        names = ', '.join((c.get('name') or str(c['id'])) for c in unused[:6]) + ('...' if len(unused) > 6 else '')
        out.append(Problem('info', 'Creatures', f'{len(unused)} monsters are not on any map yet', names, ('creatures', {'select': unused[0]['id']}), key='unusedmon'))


def check_items(f: Facts, out: list):
    p = f.p
    for r in p.tables['items']:
        v, name = r['id'], r.get('name') or f'#{r["id"]}'
        if not v or r.get('type') in ('ammo',) and not r.get('name'):
            continue
        go = ('items', {'select': v})
        if r.get('name') and r.get('type') in ('weapon', 'armour', 'shield', 'helmet', 'amulet', 'launcher', 'potion', 'treasure', 'key', 'chest') and v > 0 and not r.get('quest'):
            if p.picture('items', v) is None:
                out.append(Problem('warn', 'Items', f'{name} has no picture on the map', 'Paint one on the Items page.', go, key=f'nopic:item:{v}'))
            carried = r.get('type') in ('weapon', 'armour', 'shield', 'helmet', 'amulet', 'launcher', 'potion') or (r.get('type') == 'treasure' and r.get('price'))
            if carried and p.picture('bag', v) is None:
                out.append(Problem('warn', 'Items', f'{name} has no picture in the bag', 'Paint one on the Items page.', go, key=f'nopic:bag:{v}'))
    for c in p.tables['classes']:
        for cell, v in (c.get('bag') or {}).items():
            if v and v not in f.items:
                out.append(Problem('error', 'Heroes', f'The {c["name"]} starts with item {v}, which does not exist', '', ('heroes', {'select': c['id']}), key=f'kit:{c["id"]}:{v}'))
        for sp in c.get('spells') or []:
            if sp not in f.spells:
                out.append(Problem('error', 'Heroes', f'The {c["name"]} starts knowing spell {sp}, which does not exist', '', ('heroes', {'select': c['id']}), key=f'kitspell:{c["id"]}:{sp}'))
    colours = {r.get('key') for r in p.tables['items'] if r.get('type') == 'key'}
    for w in f.walls.values():
        if w.get('door') == 'locked' and w.get('key') not in colours:
            out.append(Problem('warn', 'Tiles', f'The {w.get("name") or w["id"]} needs a {w.get("key")} key, and there is no such key item', 'Make a key on the Items page (type Key).', ('tiles', {'select': w['id']}), key=f'nokey:{w["id"]}'))
    for sp in p.tables['spells']:
        if sp.get('effect') in ('summon', 'shadow_clones') and sp.get('creature') not in f.creatures:
            out.append(Problem('error', 'Spells', f'{sp["name"]} summons a creature that does not exist', '', ('spells', {'select': sp['id']}), key=f'nosummon:{sp["id"]}'))
        if p.picture('spells', sp['id']) is None:
            out.append(Problem('info', 'Spells', f'{sp["name"]} has no icon in the spell book', '', ('spells', {'select': sp['id']}), key=f'nopic:spell:{sp["id"]}'))


def check_tiles(f: Facts, out: list):
    p = f.p
    for kind, rows in (('floors', f.floors), ('walls', f.walls), ('decos', f.decos)):
        for v, r in rows.items():
            if v and p.picture(kind, v) is None:
                out.append(Problem('warn', 'Tiles', f'{r.get("name") or v} has no picture', f'A {kind[:-1]} without a picture is drawn as a grey square.', ('tiles', {'select': v}), key=f'nopic:{kind}:{v}'))


def check_quest(f: Facts, out: list):
    q = f.p.quest
    if not 1 <= int(q.get('first_level') or 1) <= f.levels:
        out.append(Problem('error', 'Quest', 'The first level does not exist', f'The quest starts on level {q.get("first_level")}.', ('settings', {}), key='firstlevel'))
    if not (q.get('title') or '').strip():
        out.append(Problem('info', 'Quest', 'The quest has no title', 'Give it one on the Settings page.', ('settings', {}), key='notitle'))
    if not f.classes:
        out.append(Problem('error', 'Heroes', 'There are no hero classes', 'A new game needs at least one class to choose.', ('heroes', {}), key='noclass'))
    from engine.formats import parse_story
    stories = parse_story(f.p.texts['stories'])
    for n, why in ((0, 'opens a new game'), (1, 'is shown after the hero is made'), (8, 'is the ending')):
        if n not in stories:
            out.append(Problem('info', 'Story', f'There is no story {n}', f'Story {n} {why}.', ('story', {'tab': 'stories'}), key=f'story:{n}'))


def check(session) -> list:
    f = Facts(session)
    out: list = []
    for fn in (check_levels, check_creatures, check_items, check_tiles, check_quest):
        fn(f, out)
    order = {'error': 0, 'warn': 1, 'info': 2}
    out.sort(key=lambda p: (order[p.severity], p.area, p.title))
    return out


def counts(problems) -> dict:
    c = {'error': 0, 'warn': 0, 'info': 0}
    for p in problems:
        c[p.severity] += 1
    return c
