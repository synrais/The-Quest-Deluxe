"""Quest events: runs each level's script (the pack's levels/<n>/script.qs) against the game.

The original game hardcodes its story in talk(), deadenemycheck() and main2(). The Quest II keeps those
rules as per-level scripts in a small safe language (see script.py), ported from the original code and
checked against it by tools/re/verify_events.py. New levels (8+) just add a script.

The host API mirrors the original's globals so scripts read like the C they were ported from:
  level, m1, m2 (st.mission1/2), rep, coins, killer, ems, mons, leaving
  x, y      the square the event is about (talk: the NPC's square; otherwise the hero's)
  hx, hy    the hero's map position        ax, ay   the hero's position on the screen (1-10)
  say(n)                       choose the Talk.dat message (the original's `ran`)
  talk(npc)                    run the talk handler for npc and show its message
  random(n)                    0..n-1, Borland's random()
  has(item) / has_any(item)    backpack only / anywhere in the bag (haveit(1/0, item, 0))
  take(item) / take_any(item)  the same, but also removes it (haveit(.., 1))
  give(item)                   into the first free backpack square
  put(rx, ry, item)            drop an item on the screen (the original put(): nearest free square)
  remove(rx, ry)               take the creature at (rx, ry) off the screen
  room(rx, ry), map(x, y)      a map square (screen / map coordinates); fields floor wall mon item gold deco
  count(mon, x1, y1, x2, y2)   how many squares in the map rectangle hold that creature
  visited(sx, sy)              has the automap seen screen (sx, sy)? (1-based, the original carta)
  enemies()                    the creatures on this screen (fields type x y life mlife atk defense power
                               range warm marm att moved; x/y are screen coordinates)
  refresh()                    rebuild the creature list from the screen (enemycheck())
  change_rep(d)                reputation +- 1 with the original message
  hero_step(dx, dy)            move the hero
  poison(), autosave(slot), effect(name, *args)
"""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from . import rules
from .script import Script
from .state import BACKPACK, Enemy

if TYPE_CHECKING:
    from .game import Game


# put2(): where put() tries to drop an item, relative to the requested square, before picking at random
PUT_ORDER = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, -2), (0, 2)]


def talk_text(raw: str, level: int, npc: int, ran: int) -> tuple[str, str, int] | None:
    """talk()'s reading of Talk.dat, character for character: returns (line1, line2, x) as the game
    prints them, or None where the original would search forever (it hangs)."""
    d = raw.replace('\r\n', '\n')
    p = 0
    lvl = num = y = None

    def getc():
        nonlocal p
        if p >= len(d):
            return None
        c = d[p]
        p += 1
        return c

    def getnum():
        nonlocal p
        m = re.compile(r'\s*([-+]?\d+)').match(d, p)
        if not m:
            return None
        p = m.end()
        return int(m.group(1))

    last_c = None
    for _ in range(100000):
        a, b, c = getnum(), getnum(), getnum()
        # fscanf stops at the first field it can't read; earlier fields keep their new values
        if a is not None:
            lvl = a
            if b is not None:
                num = b
                if c is not None:
                    y = c
        match = lvl is not None and (lvl == level or lvl == 0) and num == npc and ran == y
        if not match:
            i = 0
            while i < 2:
                ch = getc()
                if ch is None:
                    if last_c not in ('"', ';'):
                        return None          # EOF: the original loops forever here
                    ch = last_c              # fscanf leaves the old character in place
                last_c = ch
                if ch in ('"', ';'):
                    i += 1
            if p >= len(d) and a is None:
                return None
            continue
        break
    else:
        return None
    s = [0] * 200
    ss = [0] * 200
    ii = 0
    i = 0
    while i < 200:
        ch = getc()
        code = ord(ch) if ch is not None else None
        if ii == 0:
            s[i] = 0
            if code is not None:
                s[i] = code
        else:
            ss[i] = 0
            if code is not None:
                ss[i] = code
        if ss[i] == 0x3B:
            ss[i] = 0x22
            break
        if s[i] == 0x3B:
            s[i] = 0x22
            break
        if s[i] == 0x22 and i != 1:
            s[i] = 0
            i = -1
            ii = 1
        if ii == 1:
            s[0] = 0xFF
        i += 1
    for k in range(200):
        if ss[k] == 0x22:
            ss[k] = 0xFF
            break

    def cstr(buf):
        out = []
        for v in buf:
            if v == 0:
                break
            out.append(chr(v))
        return ''.join(out)
    return cstr(s), cstr(ss), (-3 if ii == 0 else 8)


class Cell:
    """A square as scripts see it. Writes to the screen's border, and map() writes to the current
    screen, are kept aside and dropped when the hero leaves, as the original's separate room copy did."""
    FIELDS = ('floor', 'wall', 'mon', 'item', 'gold', 'deco')

    def __init__(self, events: 'Events', x: int, y: int, shadow: bool):
        self._e, self._x, self._y, self._shadow = events, x, y, shadow


class EnemyView:
    """An Enemy as scripts see it: x/y in screen coordinates like the original enemies[] array."""
    FIELDS = ('type', 'x', 'y', 'life', 'mlife', 'atk', 'defense', 'power', 'range', 'warm', 'marm', 'att', 'moved')

    def __init__(self, events: 'Events', e: Enemy):
        self._e, self._en = events, e


class Events:
    def __init__(self, game: 'Game'):
        self.g = game
        self.scripts: dict[int, Script] = {}
        self.shadow: dict[tuple[int, int], dict] = {}
        self.ctx = {'x': 0, 'y': 0, 'ran': 0}
        self.attacker = -1              # deadenemycheck()'s killer: -1 the hero, else a creature index
        self.restart_scan = False
        self._talk_raw = None

    # ── loading ─────────────────────────────────────────────────────────────
    def script(self, level: int) -> Script | None:
        if level not in self.scripts:
            path = self.g.data.src.pack.script_path(level)
            self.scripts[level] = None
            if os.path.exists(path):
                with open(path, encoding='utf-8') as fh:
                    self.scripts[level] = Script(fh.read(), path)
        return self.scripts[level]

    def meta(self, level: int, name: str, default=None):
        """A setting from the top of a level script (START, SHOPS, STORIES, TELEPORT, ASK_TO_LEAVE)."""
        sc = self.script(level)
        return sc.constants.get(name, default) if sc is not None else default

    def ask(self, handler: str, default=True):
        """The answer of a handler that returns a value (the level's, else common.qs's, else default)."""
        for sc in (self.script(self.g.world.level), self.script(0)):
            if sc is not None and sc.has(handler):
                return sc.run(handler, self)
        return default

    @property
    def talk_raw(self) -> str:
        if self._talk_raw is None:
            self._talk_raw = self.g.data.src.text('Talk.dat')
        return self._talk_raw

    # ── hooks from the game ─────────────────────────────────────────────────
    def on_level_start(self):
        self.snapshot()

    def on_enter_room(self):
        self.snapshot()

    def snapshot(self):
        """goroom(): the original copies the new screen (with a one-square border) from map[] into room[].
        From then on map[] keeps those arrival values for the screen, and room[] holds the live ones.
        We keep the arrival values here: map() reads and writes them for the current screen, and room()
        uses them for the border squares."""
        self.shadow.clear()
        w = self.g.world
        if not w.grid:
            return
        ox, oy = w.origin
        for x in range(ox - 1, ox + 11):
            for y in range(oy - 1, oy + 11):
                if w.in_map(x, y):
                    q = w.grid[x][y]
                    self.shadow[(x, y)] = {f: getattr(q, f) for f in Cell.FIELDS}

    def on_step(self, x: int, y: int): ...

    def on_pickup(self, item: int): ...

    def run(self, handler: str, *args):
        """Run a handler in common.qs and then in the level's script, if they define it."""
        for sc in (self.script(0), self.script(self.g.world.level)):
            if sc is not None and sc.has(handler):
                sc.run(handler, self, *args)

    def run_check(self, w: int):
        """deadenemycheck()'s per-creature checks: common.qs first, then the level's own."""
        for sc in (self.script(0), self.script(self.g.world.level)):
            if sc is not None and sc.has('check'):
                sc.run('check', self, w)

    def run_dies(self, w: int):
        for sc in (self.script(0), self.script(self.g.world.level)):
            if sc is not None and sc.has('dies'):
                sc.run('dies', self, w)

    def on_talk(self, npc: int, x: int, y: int) -> bool:
        """The hero walked into a talking NPC at (x, y): run talk() and show its message."""
        self.talk(npc, x, y)
        return True

    def on_use_item(self, item: int, slot) -> str | None:
        return None

    def save_state(self) -> dict:
        return {}

    def load_state(self, d: dict): ...

    # ── running scripts ─────────────────────────────────────────────────────
    def talk(self, npc: int, x: int | None = None, y: int | None = None):
        """talk(npc): ran = random(3) + 1, the level's talk handler may change it, then the message."""
        p = self.g.player
        saved = dict(self.ctx)
        self.ctx['x'] = p.X if x is None else x
        self.ctx['y'] = p.Y if y is None else y
        self.ctx['ran'] = rules.random(3) + 1
        sc = self.script(self.g.world.level)
        if sc is not None and sc.has('talk'):
            sc.run('talk', self, npc)
        ran = self.ctx['ran']
        self.ctx = saved
        text = talk_text(self.talk_raw, self.g.world.level, npc, ran)
        self.g.show_talk(text)
        return ran

    # ── script host interface ───────────────────────────────────────────────
    VARS = {'level', 'm1', 'm2', 'rep', 'coins', 'killer', 'ems', 'mons', 'leaving', 'x', 'y', 'hx', 'hy', 'ax',
            'ay', 'attacker'}
    FUNCS = {'say', 'talk', 'random', 'has', 'has_any', 'take', 'take_any', 'give', 'put', 'remove', 'room',
             'map', 'count', 'visited', 'enemies', 'refresh', 'change_rep', 'hero_step', 'poison', 'autosave',
             'effect', 'min', 'max', 'abs', 'range', 'slot', 'said', 'len', 'restart', 'hurt_hero', 'next_level'}

    def has_var(self, name):
        return name in self.VARS

    def get_var(self, name):
        g, p, st, w = self.g, self.g.player, self.g.status, self.g.world
        ox, oy = w.origin
        return {
            'level': lambda: w.level, 'm1': lambda: st.mission1, 'm2': lambda: st.mission2,
            'rep': lambda: p.hero.rep, 'coins': lambda: p.inv.coins, 'killer': lambda: st.killer,
            'ems': lambda: st.ems, 'mons': lambda: len(w.enemies), 'leaving': lambda: 0,
            'x': lambda: self.ctx['x'], 'y': lambda: self.ctx['y'], 'hx': lambda: p.X, 'hy': lambda: p.Y,
            'ax': lambda: p.X - ox + 1, 'ay': lambda: p.Y - oy + 1, 'attacker': lambda: self.attacker,
        }[name]()

    def set_var(self, name, v):
        g, p, st = self.g, self.g.player, self.g.status
        if name == 'm1':
            st.mission1 = v
        elif name == 'm2':
            st.mission2 = v
        elif name == 'rep':
            p.hero.rep = v
        elif name == 'coins':
            p.inv.coins = v
        elif name == 'killer':
            st.killer = v
        elif name == 'attacker':
            self.attacker = v
        else:
            raise AttributeError(f'{name} is read-only')

    def has_func(self, name):
        return name in self.FUNCS

    def call(self, name, *a, **kw):
        return getattr(self, 'f_' + name)(*a, **kw)

    def get_attr(self, obj, attr):
        if isinstance(obj, Cell):
            if attr not in Cell.FIELDS:
                raise AttributeError(attr)
            key = (obj._x, obj._y)
            if obj._shadow and key in self.shadow:
                return self.shadow[key][attr]
            return getattr(self.g.world.grid[obj._x][obj._y], attr) if self.g.world.in_map(obj._x, obj._y) else 0
        if isinstance(obj, EnemyView):
            if attr not in EnemyView.FIELDS:
                raise AttributeError(attr)
            e, (ox, oy) = obj._en, self.g.world.origin
            if attr == 'x':
                return e.x - ox + 1
            if attr == 'y':
                return e.y - oy + 1
            return getattr(e, attr)
        raise AttributeError(attr)

    def set_attr(self, obj, attr, v):
        if isinstance(obj, Cell):
            if attr not in Cell.FIELDS:
                raise AttributeError(attr)
            key = (obj._x, obj._y)
            if obj._shadow:
                if key not in self.shadow:
                    q = self.g.world.grid[obj._x][obj._y] if self.g.world.in_map(*key) else None
                    self.shadow[key] = {f: (getattr(q, f) if q else 0) for f in Cell.FIELDS}
                self.shadow[key][attr] = v
            elif self.g.world.in_map(*key):
                setattr(self.g.world.grid[obj._x][obj._y], attr, v)
            return
        if isinstance(obj, EnemyView):
            if attr not in EnemyView.FIELDS:
                raise AttributeError(attr)
            e, (ox, oy) = obj._en, self.g.world.origin
            if attr == 'x':
                e.x = v + ox - 1
            elif attr == 'y':
                e.y = v + oy - 1
            else:
                setattr(e, attr, v)
            return
        raise AttributeError(attr)

    # ── functions ───────────────────────────────────────────────────────────
    def f_say(self, n):
        self.ctx['ran'] = n

    def f_talk(self, npc):
        return self.talk(npc)

    def f_random(self, n):
        return rules.random(n)

    def f_min(self, *a):
        return min(*a)

    def f_max(self, *a):
        return max(*a)

    def f_abs(self, a):
        return abs(a)

    def f_range(self, *a):
        return range(*a)

    def f_next_level(self):
        self.g.pending_next_level = True

    def f_restart(self):
        """deadenemycheck() starts its scan over after this creature (at index 1, like the original)."""
        self.restart_scan = True

    def f_hurt_hero(self, power, kind, w):
        """hurt(power, hero, kind, attacker w): returns the damage done."""
        lst = self.g.world.enemies
        return self.g.combat.hurt(power, None, kind, lst[w] if 0 <= w < len(lst) else None)

    def f_len(self, a):
        return len(a)

    def f_said(self):
        """The message chosen so far (the original's `ran`)."""
        return self.ctx['ran']

    def _find(self, item, anywhere):
        """haveit(where, item): the bag is scanned column 12..15, row 8..11 (row 1..11 when anywhere)."""
        bag = self.g.player.bag
        for col in range(12, 16):
            for row in range(1 if anywhere else 8, 12):
                if bag.get((col, row), 0) == item:
                    return (col, row)
        return None

    def f_has(self, item):
        return self._find(item, False) is not None

    def f_has_any(self, item):
        return self._find(item, True) is not None

    def f_take(self, item):
        slot = self._find(item, False)
        if slot:
            self.g.player.bag[slot] = 0
        return slot is not None

    def f_take_any(self, item):
        slot = self._find(item, True)
        if slot:
            self.g.player.bag[slot] = 0
        return slot is not None

    def f_give(self, item):
        """The first free backpack square, row by row (the loops in talk())."""
        bag = self.g.player.bag
        for row in range(8, 12):
            for col in range(12, 16):
                if not bag.get((col, row), 0):
                    bag[(col, row)] = item
                    return True
        return False

    def f_put(self, rx, ry, item):
        """put(): the square itself, then 1 and 2 squares left/right/up/down, then random squares."""
        w = self.g.world
        ox, oy = w.origin
        for dx, dy in PUT_ORDER:
            i, ii = rx + dx, ry + dy
            if dx < 0 and not (rx > -dx):
                continue
            if dx > 0 and not (rx < 11 - dx):
                continue
            if dy < 0 and not (ry > -dy):
                continue
            if dy > 0 and not (ry < 11 - dy):
                continue
            q = w.grid[ox + i - 1][oy + ii - 1]
            if q.item == 0 and q.wall == 0:
                q.item = item
                return i, ii
        for _ in range(100000):
            i, ii = rules.random(10) + 1, rules.random(10) + 1
            q = w.grid[ox + i - 1][oy + ii - 1]
            if q.item == 0 and q.wall == 0:
                q.item = item
                return i, ii
        return None

    def f_remove(self, rx, ry):
        """remove(): the first creature standing at screen square (rx, ry) leaves the screen."""
        w = self.g.world
        ox, oy = w.origin
        for e in w.enemies:
            if e.x == rx + ox - 1 and e.y == ry + oy - 1:
                w.enemies.remove(e)
                w.grid[e.x][e.y].mon = 0
                if self.g.target is e:
                    self.g.target = None
                break
        self.g.status.mons = len(w.enemies)

    def f_room(self, rx, ry):
        ox, oy = self.g.world.origin
        return Cell(self, ox + rx - 1, oy + ry - 1, shadow=not (1 <= rx <= 10 and 1 <= ry <= 10))

    def f_map(self, x, y):
        return Cell(self, x, y, shadow=(x, y) in self.shadow and self.g.world.in_room(x, y))

    def f_count(self, mon, x1, y1, x2, y2):
        grid, n = self.g.world.grid, 0
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                key = (x, y)
                v = self.shadow[key]['mon'] if key in self.shadow and self.g.world.in_room(x, y) else grid[x][y].mon
                n += v == mon
        return n

    def f_visited(self, sx, sy):
        return (sx - 1, sy - 1) in self.g.world.visited

    def f_slot(self, k):
        """enemies[k] as the original indexes it, even past the end of the list (then writes go nowhere)."""
        lst = self.g.world.enemies
        return EnemyView(self, lst[k]) if 0 <= k < len(lst) else EnemyView(self, Enemy(type=0, x=0, y=0))

    def f_enemies(self):
        return [EnemyView(self, e) for e in self.g.world.enemies]

    def f_refresh(self):
        self.g.world.rescan(self.g.player, self.g.status)

    def f_change_rep(self, d):
        self.g.change_rep(d)

    def f_hero_step(self, dx, dy):
        p = self.g.player
        p.X += dx
        p.Y += dy

    def f_poison(self):
        """hero.poisoned = 1; ampoisoned(1), over whatever the screen shows (the original doesn't redraw)."""
        self.g.player.hero.poisoned = 1
        self.g.play('ampoisoned2', 1, redraw=False)

    def f_autosave(self, slot):
        self.g.autosave(slot)

    def f_effect(self, name, *args):
        """One of the original's animations (deluxe.anim: dcast2, asskeleton, screen_flash ...), played
        now, at 1-based screen squares. It has no game effect."""
        self.g.play(name, *args)
