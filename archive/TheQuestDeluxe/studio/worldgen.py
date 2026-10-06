"""Makes whole levels: terrain, rivers, buildings, paths, a way in and a way out, creatures, treasure and a shop.

Nothing here knows about windows. generate(project, params) returns a Result: the 100 x 100 squares, where the hero starts,
the screens that are peaceful or hold a shop, the shop's wares, and a list of things worth a warning. The same seed
and settings give the same level, so a level can be rolled again until it feels right.

What a level is made of (which floor is grass, which wall is a tree, which item is the exit) is read from the pack's own
tiles and items by `detect`, and the wizard lets the maker override any of it, so packs with their own pictures work.
"""
from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass, field

SIZE = 100
THEMES = ('country', 'village', 'dungeon', 'wilderness', 'maze', 'cave')
DIFFICULTY = {'gentle': 2.0, 'normal': 4.0, 'tough': 6.5, 'deadly': 10.0}      # hostile creatures per full screen
CORNERS = ('sw', 'nw', 'ne', 'se')
INF = 10 ** 9


# ── the pack's own tiles ─────────────────────────────────────────────────────
@dataclass
class Style:
    ground: int = 1
    ground_alt: list = field(default_factory=list)       # patches: shrubs, sand
    path: int | None = None
    bridge: int | None = None
    indoor: list = field(default_factory=list)           # floors inside buildings
    trees: list = field(default_factory=list)            # solid walls that make a forest
    rocks: list = field(default_factory=list)            # boulders and dead wood
    water: int | None = None
    building: list = field(default_factory=list)         # solid walls that make buildings
    door: int | None = None
    locked: dict = field(default_factory=dict)           # key colour -> (wall id, key item id)
    furniture: list = field(default_factory=list)        # tables and such, solid
    well: int | None = None
    exit_item: int | None = None
    chest_item: int | None = None
    deco_remains: list = field(default_factory=list)

    def asdict(self):
        return dict(self.__dict__)


def _name(r):
    return (r.get('name') or '').lower()


def detect(project) -> Style:
    """Work out from the pack's tiles which floor is grass, which wall is a tree, what makes a building."""
    t = project.tiles
    floors, walls = t.get('floors', []), t.get('walls', [])
    s = Style()
    plain = [f for f in floors if not f.get('map_colour')]
    grass = next((f for f in floors if 'grass' in _name(f)), None) or (plain[0] if plain else (floors[0] if floors else None))
    s.ground = grass['id'] if grass else 1
    s.path = next((f['id'] for f in floors if any(k in _name(f) for k in ('path', 'road', 'gravel', 'cobble', 'trail'))), None)
    s.bridge = next((f['id'] for f in floors if 'bridge' in _name(f)), None)
    s.indoor = [f['id'] for f in floors if f.get('roof') or any(k in _name(f) for k in ('carpet', 'tile', 'wood', 'marble'))]
    s.ground_alt = [f['id'] for f in floors if f['id'] not in (s.ground, s.path, s.bridge) and f['id'] not in s.indoor
                    and any(k in _name(f) for k in ('shrub', 'sand', 'dirt', 'moss', 'flower', 'mud', 'snow'))]
    for w in walls:
        n = _name(w)
        if w.get('water'):
            s.water = s.water or w['id']
        elif w.get('door') == 'plain':
            s.door = s.door or w['id']
        elif w.get('door') == 'locked':
            s.locked[w.get('key', '')] = [w['id'], None]
        elif w.get('door'):
            continue
        elif not w.get('solid'):
            continue
        elif any(k in n for k in ('table', 'counter', 'desk', 'bench')):
            s.furniture.append(w['id'])
        elif 'well' in n:
            s.well = w['id']
        elif any(k in n for k in ('decayed', 'dead', 'boulder', 'rock', 'stone pile', 'rubble')):
            s.rocks.append(w['id'])
        elif any(k in n for k in ('tree', 'pine', 'bush', 'shrub', 'hedge')):
            s.trees.append(w['id'])
        else:
            s.building.append(w['id'])
    s.rocks = s.rocks or [i for i in s.trees[:1]]
    for it in project.tables['items']:
        ty = it.get('type')
        if ty == 'exit' and s.exit_item is None:
            s.exit_item = it['id']
        elif ty == 'chest' and s.chest_item is None:
            s.chest_item = it['id']
        elif ty == 'key' and it.get('key') in s.locked and s.locked[it['key']][1] is None:
            s.locked[it['key']][1] = it['id']
    s.locked = {k: tuple(v) for k, v in s.locked.items() if v[1] is not None}
    s.deco_remains = [d['id'] for d in t.get('decos', []) if d.get('role') in ('remains', 'remains2', 'blood', 'bones')]
    return s


# ── creatures and items: how dangerous, how valuable ─────────────────────────
def threat(c: dict) -> float:
    """A rough number for how hard a creature is to fight: more life, harder hits, better aim, more danger."""
    atk = c.get('atk') or 100
    return max(1.0, (c.get('life') or 1) * (1 + (c.get('power') or 0) / 12) * (0.6 + atk / 200))


def is_hostile(c: dict) -> bool:
    """A monster (not a person or an ally) that comes for the hero: attitude above 0 (how far it sees), or a caster that keeps away."""
    att = c.get('att', 9)
    return c['id'] > 0 and (att is None or att > 0 or att == -4)


def hostile(project) -> list:
    return sorted((c for c in project.tables['creatures'] if is_hostile(c) and not c.get('hidden_by_default')),
                  key=threat)


def villagers(project) -> list:
    return [c['id'] for c in project.tables['creatures'] if -100 < c['id'] < 0 and c['id'] != -5 and c.get('att', -2) in (-2, -1)]


@dataclass
class Params:
    seed: int = 1
    theme: str = 'country'
    screens: tuple = (5, 5)
    start: str = 'sw'
    rivers: int = 1
    lakes: int = 1
    forest: float = 0.30
    buildings: int = 4
    paths: bool = True
    difficulty: str = 'normal'
    creatures: list = field(default_factory=list)
    boss: int | None = None
    monsters: float = 1.0
    calm_start: bool = True
    gold: float = 1.0
    potions: float = 1.0
    gear: float = 1.0
    chests: bool = True
    shop: bool = True
    villagers: int = 3
    puzzle: bool = False
    dark: bool = False
    tier: float | None = None             # how far along a whole quest this level is (0 first .. 1 last): shifts creatures and wares
    style: dict = field(default_factory=dict)


DEFAULTS = {'country': dict(rivers=1, lakes=1, forest=0.30, buildings=4), 'village': dict(rivers=0, lakes=0, forest=0.14, buildings=8),
            'dungeon': dict(rivers=0, lakes=0, forest=0, buildings=0), 'wilderness': dict(rivers=1, lakes=1, forest=0.5, buildings=2),
            'maze': dict(rivers=0, lakes=0, forest=0, buildings=0), 'cave': dict(rivers=0, lakes=0, forest=0, buildings=0)}


def theme_defaults(theme: str) -> dict:
    """What suits a kind of place: rivers, lakes, forest and buildings, and whether it gets a shop and how many villagers."""
    d = dict(DEFAULTS[theme])
    d['shop'] = theme in ('country', 'village', 'wilderness')
    d['villagers'] = 6 if theme == 'village' else 0 if theme in ('maze', 'cave') else 3
    return d


@dataclass
class Result:
    sq: list
    start: tuple
    exit: tuple | None
    shops: dict                      # shop number -> its text
    shop_screens: dict               # (screen column, row) -> shop number
    peaceful: list
    dark: list
    warnings: list
    stats: dict
    area: tuple

    def rows(self):
        for x in range(1, SIZE + 1):
            for y in range(1, SIZE + 1):
                fl, wa, it, mo, go, de = self.sq[x][y]
                yield x, y, fl, wa, it, mo, go, de


# ── a whole quest: which places, how hard, level after level ──────────────────
JOURNEYS = {'classic': ['village', 'country', 'wilderness', 'cave', 'dungeon'], 'depths': ['cave', 'dungeon', 'cave', 'dungeon'],
            'wild': ['country', 'wilderness', 'village', 'country', 'wilderness'], 'maze': ['maze'], 'mix': None}
RAMP_LEVELS = {'easy': ('gentle', 'gentle', 'normal'), 'steady': ('gentle', 'normal', 'tough'), 'steep': ('normal', 'tough', 'deadly')}


def difficulty_for(ramp: str, tier: float) -> str:
    """The difficulty of a level that far along a quest (tier 0 the first level, 1 the last)."""
    seq = RAMP_LEVELS.get(ramp, RAMP_LEVELS['steady'])
    return seq[min(len(seq) - 1, int(tier * len(seq)))]


def journey_themes(journey: str, count: int, rng: random.Random) -> list:
    """The kind of place of each of `count` levels along a journey (a list of places stretched over the levels)."""
    seq = JOURNEYS.get(journey)
    if seq is None:
        pool = [t for t in THEMES if t != 'village']
        out = [rng.choice(['village', 'country', 'wilderness']) if count > 1 else rng.choice(pool)]
        while len(out) < count:
            out.append(rng.choice([t for t in pool if t != out[-1]]))
        return out[:count]
    return [seq[min(len(seq) - 1, int(i * len(seq) / count))] for i in range(count)]


def quest_params(i: int, count: int, theme: str, seed: int, size: int, ramp: str, boss: int | None = None, puzzles: bool = True) -> Params:
    """The settings of level i of a whole quest of `count` levels: tougher creatures and dearer wares the farther along."""
    tier = i / (count - 1) if count > 1 else 0.0
    q = Params(seed=seed, theme=theme, screens=(size, size), tier=tier, difficulty=difficulty_for(ramp, tier), boss=boss)
    for k, v in theme_defaults(theme).items():
        setattr(q, k, v)
    q.puzzle = bool(puzzles and theme == 'dungeon' and i > 0)
    q.dark = theme in ('dungeon', 'cave') and tier > 0.4
    return q


# ── helpers ──────────────────────────────────────────────────────────────────
def value_noise(rng, scale):
    n = SIZE // scale + 3
    lat = [[rng.random() for _ in range(n)] for _ in range(n)]

    def f(x, y):
        fx, fy = x / scale, y / scale
        ix, iy = int(fx), int(fy)
        tx, ty = fx - ix, fy - iy
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = lat[ix][iy] * (1 - tx) + lat[ix + 1][iy] * tx
        b = lat[ix][iy + 1] * (1 - tx) + lat[ix + 1][iy + 1] * tx
        return a * (1 - ty) + b * ty
    return f


def fractal(rng, big=12, small=5):
    a, b = value_noise(rng, big), value_noise(rng, small)
    return lambda x, y: 0.65 * a(x, y) + 0.35 * b(x, y)


class Gen:
    def __init__(self, project, params: Params):
        self.project, self.q = project, params
        self.rng = random.Random(params.seed * 7919 + 17)
        self.style = detect(project)
        for k, v in (params.style or {}).items():
            if hasattr(self.style, k) and v is not None:
                setattr(self.style, k, v)
        s = self.style
        self.w = max(10, min(SIZE, params.screens[0] * 10))
        self.h = max(10, min(SIZE, params.screens[1] * 10))
        self.sq = [[[1, 0, 0, 0, 0, 0] for _ in range(SIZE + 2)] for _ in range(SIZE + 2)]
        for x in range(1, self.w + 1):
            for y in range(1, self.h + 1):
                self.sq[x][y][0] = s.ground
        self.tag = {}                 # (x, y) -> 'water' | 'house' | 'room' | 'street' | 'gate' ...
        self.reserved = set()
        self.doors = []               # (door square, porch square) of buildings
        self.interiors = []           # dicts: rect, kind
        self.warnings = []
        self.start = (3, self.h - 2)
        self.exit = None
        self.exit_porch = None
        self.shop_screens = {}
        self.shops = {}
        self.peaceful = []
        self.dark = []
        self.walls_info = {w['id']: w for w in project.tiles.get('walls', [])}

    # squares ----------------------------------------------------------------
    def inside(self, x, y):
        return 1 <= x <= self.w and 1 <= y <= self.h

    def cell(self, x, y):
        return self.sq[x][y]

    def wall(self, x, y):
        return self.sq[x][y][1]

    def passable(self, x, y, keys=()):
        if not self.inside(x, y):
            return False
        wa = self.sq[x][y][1]
        if not wa:
            return True
        info = self.walls_info.get(wa, {})
        door = info.get('door')
        if door == 'plain':
            return True
        if door == 'locked':
            return info.get('key') in keys
        if door:
            return False
        return not info.get('solid')

    def free(self, x, y):
        """Open ground with nothing on it: a place to put something."""
        if not self.inside(x, y) or self.tag.get((x, y)) in ('water', 'house', 'gate'):
            return False
        c = self.sq[x][y]
        return not c[1] and not c[2] and not c[3] and not c[4]

    def rect_free(self, x0, y0, x1, y1, margin=1, streets=False):
        """Is the rectangle (and a margin round it) clear of water, buildings and the zones kept for the start and way out?
        With streets=True a street may run along the edge: houses face them."""
        bad = ('water', 'house', 'room', 'gate') + (() if streets else ('street',))
        for x in range(x0 - margin, x1 + margin + 1):
            for y in range(y0 - margin, y1 + margin + 1):
                if not self.inside(x, y):
                    return False
                if (x, y) in self.reserved or self.tag.get((x, y)) in bad:
                    return False
        return True

    def set_wall(self, x, y, v, tag=None):
        if self.inside(x, y):
            self.sq[x][y][1] = v
            if tag:
                self.tag[(x, y)] = tag

    def set_floor(self, x, y, v, tag=None):
        if self.inside(x, y):
            self.sq[x][y][0] = v
            if tag:
                self.tag[(x, y)] = tag

    def pick(self, seq, default=0):
        return self.rng.choice(seq) if seq else default

    # the frame ---------------------------------------------------------------
    def border(self, ids=None):
        ids = ids or self.style.trees or self.style.building or [1]
        for x in range(1, self.w + 1):
            for y in (1, self.h):
                self.set_wall(x, y, self.pick(ids))
        for y in range(1, self.h + 1):
            for x in (1, self.w):
                self.set_wall(x, y, self.pick(ids))

    def zones(self):
        """Where the hero starts and the way out is: opposite corners, kept clear of everything else."""
        c = self.q.start if self.q.start in CORNERS else 'sw'
        left = c[1] == 'w'
        top = c[0] == 'n'
        sx = 5 if left else self.w - 4
        sy = 5 if top else self.h - 4
        ex = self.w - 5 if left else 6
        ey = self.h - 5 if top else 6
        self.start = (sx, sy)
        self.exit_pos = (ex, ey)
        for (cx, cy), r in ((self.start, 5), (self.exit_pos, 6)):
            for x in range(cx - r, cx + r + 1):
                for y in range(cy - r, cy + r + 1):
                    if self.inside(x, y):
                        self.reserved.add((x, y))

    # terrain -----------------------------------------------------------------
    def patches(self):
        s = self.style
        if not s.ground_alt:
            return
        n = fractal(self.rng, 14, 6)
        vals = sorted(n(x, y) for x in range(1, self.w + 1) for y in range(1, self.h + 1))
        thr = vals[int(0.78 * len(vals))]
        for x in range(2, self.w):
            for y in range(2, self.h):
                v = n(x, y)
                if v > thr:
                    self.sq[x][y][0] = s.ground_alt[int((v - thr) * 40) % len(s.ground_alt)]

    def forest(self, density, rocks=0.012):
        s = self.style
        if not s.trees or density <= 0:
            return
        n = fractal(self.rng, 11, 4)
        kind = value_noise(self.rng, 9)
        vals = sorted(n(x, y) for x in range(2, self.w) for y in range(2, self.h))
        thr = vals[min(len(vals) - 1, int((1 - min(0.9, density)) * len(vals)))]
        for x in range(2, self.w):
            for y in range(2, self.h):
                if (x, y) in self.reserved or self.tag.get((x, y)):
                    continue
                if n(x, y) > thr:
                    self.sq[x][y][1] = s.trees[int(kind(x, y) * len(s.trees) * 0.999)]
                elif s.rocks and self.rng.random() < rocks:
                    self.sq[x][y][1] = self.pick(s.rocks)

    def river(self, width=2):
        s = self.style
        if s.water is None:
            return
        rng = self.rng
        horizontal = rng.random() < 0.5
        span = self.w if horizontal else self.h
        cross = self.h if horizontal else self.w
        pos = rng.randint(cross // 4, 3 * cross // 4)
        drift = 0
        pts = []
        for a in range(1, span + 1):
            pts.append((a, pos))
            if rng.random() < 0.3:
                drift = max(-1, min(1, drift + rng.choice((-1, 0, 1))))
            if rng.random() < 0.55:
                pos += drift
            pos = max(3, min(cross - 2, pos))
        for a, b in pts:
            for k in range(width):
                x, y = (a, b + k) if horizontal else (b + k, a)
                if self.inside(x, y) and (x, y) not in self.reserved and self.tag.get((x, y)) not in ('house', 'room'):
                    self.set_wall(x, y, s.water, 'water')

    def lake(self):
        s = self.style
        if s.water is None:
            return
        rng = self.rng
        r = rng.randint(3, 6)
        for _ in range(40):
            cx, cy = rng.randint(r + 3, self.w - r - 2), rng.randint(r + 3, self.h - r - 2)
            if not self.rect_free(cx - r, cy - r, cx + r, cy + r, 1):
                continue
            wob = value_noise(rng, 4)
            for x in range(cx - r - 1, cx + r + 2):
                for y in range(cy - r - 1, cy + r + 2):
                    d = math.hypot(x - cx, y - cy)
                    if d < r * (0.75 + 0.5 * wob(x, y)):
                        self.set_wall(x, y, s.water, 'water')
            return

    # buildings ---------------------------------------------------------------
    def building(self, x0, y0, bw, bh, side=None, kind='house', walls=None, floor=None, locked=None, partition=False, streets=False):
        """A walled room with a door in one side (side: 'n' 's' 'e' 'w'). Returns the interior rect, or None if it will not fit."""
        s = self.style
        if not s.building:
            return None
        x1, y1 = x0 + bw - 1, y0 + bh - 1
        if not self.rect_free(x0, y0, x1, y1, 2 if not streets else 1, streets):
            return None
        rng = self.rng
        wall = walls or self.pick(s.building)
        floor = floor if floor is not None else (self.pick(s.indoor) if s.indoor else s.ground)
        side = side or rng.choice('nsew')
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                edge = x in (x0, x1) or y in (y0, y1)
                self.tag[(x, y)] = 'house' if edge else 'room'
                self.sq[x][y][0] = s.ground if edge else floor
                self.sq[x][y][1] = wall if edge else 0
        dx = {'n': rng.randint(x0 + 1, x1 - 1), 's': rng.randint(x0 + 1, x1 - 1), 'w': x0, 'e': x1}[side]
        dy = {'w': rng.randint(y0 + 1, y1 - 1), 'e': rng.randint(y0 + 1, y1 - 1), 'n': y0, 's': y1}[side]
        door = locked if locked is not None else s.door
        if door is not None:
            self.sq[dx][dy][1] = door
        else:
            self.sq[dx][dy][1] = 0
        self.tag[(dx, dy)] = 'door'
        porch = (dx + {'w': -1, 'e': 1}.get(side, 0), dy + {'n': -1, 's': 1}.get(side, 0))
        if self.inside(*porch):
            self.tag.pop(porch, None)
            self.sq[porch[0]][porch[1]][1] = 0
        self.doors.append(((dx, dy), porch))
        rect = (x0 + 1, y0 + 1, x1 - 1, y1 - 1)
        self.interiors.append({'rect': rect, 'kind': kind, 'door': (dx, dy), 'porch': porch})
        if partition and bw >= 9:
            px_ = x0 + bw // 2
            for y in range(y0 + 1, y1):
                self.sq[px_][y][1] = wall
            gap = rng.randint(y0 + 2, y1 - 2)
            self.sq[px_][gap][1] = s.door if s.door is not None else 0
        return rect

    def furnish(self, rect, kind='house'):
        """Tables, a chest, now and then a well-hidden treasure inside a room."""
        s = self.style
        x0, y0, x1, y1 = rect
        rng = self.rng
        spots = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if not self.sq[x][y][1]]
        rng.shuffle(spots)
        if s.furniture and len(spots) > 8:
            for x, y in spots[:rng.randint(0, 2)]:
                if not self.adjacent_door(x, y):
                    self.sq[x][y][1] = self.pick(s.furniture)
        return spots

    def adjacent_door(self, x, y):
        return any(abs(x - dx) + abs(y - dy) <= 2 for (dx, dy), _ in self.doors)

    def put_buildings(self, count, sizes=((5, 5), (6, 5), (7, 6), (8, 6), (9, 7), (10, 7), (12, 8), (14, 9))):
        placed = 0
        for _ in range(count * 40):
            if placed >= count:
                break
            bw, bh = self.rng.choice(sizes)
            x0 = self.rng.randint(3, max(3, self.w - bw - 2))
            y0 = self.rng.randint(3, max(3, self.h - bh - 2))
            if self.building(x0, y0, bw, bh, partition=bw >= 9):
                placed += 1
        if placed < count:
            self.warnings.append(f'Only {placed} of {count} buildings fitted.')

    # the way out -------------------------------------------------------------
    def gate(self):
        """A small walled yard in the far corner with the exit in it."""
        s = self.style
        ex, ey = self.exit_pos
        top = ey < self.h // 2
        left = ex < self.w // 2
        x0, y0 = ex - 2, ey - 1
        wall = self.pick(s.building or s.trees or [1])
        for x in range(x0, x0 + 5):
            for y in range(y0, y0 + 3):
                self.sq[x][y][1] = 0
                self.tag[(x, y)] = 'gate'
        for x in range(x0 - 1, x0 + 6):
            for y in range(y0 - 1, y0 + 4):
                edge = x in (x0 - 1, x0 + 5) or y in (y0 - 1, y0 + 3)
                if edge:
                    self.set_wall(x, y, wall, 'gate')
        mouth_y = y0 + 3 if top else y0 - 1
        mx = ex
        self.sq[mx][mouth_y][1] = 0
        porch_y = mouth_y + (1 if top else -1)
        self.exit_porch = (mx, porch_y)
        self.tag.pop(self.exit_porch, None)
        self.sq[mx][porch_y][1] = 0
        if s.exit_item is not None:
            self.sq[ex][ey][2] = s.exit_item
        else:
            self.warnings.append('The quest has no item of the type "exit", so this level has no way out yet.')
        self.exit = (ex, ey)
        return (x0, y0, x0 + 4, y0 + 2)

    def start_clearing(self):
        sx, sy = self.start
        for x in range(sx - 3, sx + 4):
            for y in range(sy - 3, sy + 4):
                if self.inside(x, y) and 1 < x < self.w and 1 < y < self.h and self.tag.get((x, y)) not in ('house', 'room', 'gate'):
                    c = self.sq[x][y]
                    if c[1] and not (self.walls_info.get(c[1], {}).get('door')):
                        c[1] = 0
                    if self.tag.get((x, y)) == 'water':
                        self.tag.pop((x, y))

    # routes ------------------------------------------------------------------
    def cost(self, x, y):
        if not self.inside(x, y):
            return INF
        wa = self.sq[x][y][1]
        tg = self.tag.get((x, y))
        if wa:
            info = self.walls_info.get(wa, {})
            if info.get('door') == 'plain':
                return 1.2
            if tg in ('house', 'gate'):
                return INF
            if info.get('water'):
                return 8 if self.style.bridge is not None else INF
            if wa in self.style.trees:
                return 4.5
            if wa in self.style.rocks:
                return 7
            return INF
        if tg == 'room':
            return 1.4
        if self.sq[x][y][0] == self.style.path:
            return 0.55
        return 1.0

    def route(self, a, b):
        """The cheapest way from a to b, cutting through trees and bridging water where it must. None if there is none."""
        if a == b:
            return [a]
        open_ = [(0.0, 0.0, a)]
        best = {a: 0.0}
        came = {}
        while open_:
            _, c, cur = heapq.heappop(open_)
            if cur == b:
                path = [cur]
                while cur in came:
                    cur = came[cur]
                    path.append(cur)
                return path[::-1]
            if c > best.get(cur, INF):
                continue
            x, y = cur
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                k = self.cost(nx, ny)
                if k >= INF:
                    continue
                n = (nx, ny)
                nc = c + k + self.rng.random() * 0.15
                if nc < best.get(n, INF):
                    best[n] = nc
                    came[n] = cur
                    h = abs(nx - b[0]) + abs(ny - b[1])
                    heapq.heappush(open_, (nc + h * 0.9, nc, n))
        return None

    def carve(self, path, paved=True):
        s = self.style
        for x, y in path:
            c = self.sq[x][y]
            wa = c[1]
            if wa:
                info = self.walls_info.get(wa, {})
                if info.get('door'):
                    continue
                if info.get('water'):
                    c[1] = 0
                    c[0] = s.bridge if s.bridge is not None else s.ground
                    self.tag.pop((x, y), None)
                    continue
                c[1] = 0
            if paved and s.path is not None and self.tag.get((x, y)) not in ('room', 'gate') and self.rng.random() < 0.92:
                c[0] = s.path
                self.tag.setdefault((x, y), 'trail')

    def connect(self, a, b, paved=True):
        r = self.route(a, b)
        if r is None:
            self.warnings.append(f'No way between {a} and {b}.')
            return False
        self.carve(r, paved)
        return True

    def reach(self, start=None, keys=()):
        """Distance in steps from the start over walkable squares: {(x, y): steps}."""
        start = start or self.start
        dist = {start: 0}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in dist and self.passable(nx, ny, keys):
                    dist[(nx, ny)] = dist[(x, y)] + 1
                    q.append((nx, ny))
        return dist


# ── the layouts ──────────────────────────────────────────────────────────────
def _chain(g, extra=2):
    """Join the start, every building's porch and the way out with paths, nearest first, and a few shortcuts."""
    sx, sy = g.start
    ex, ey = g.exit_porch or g.exit_pos
    nodes = [p for _, p in g.doors if g.inside(*p)]
    nodes.sort(key=lambda p: (p[0] - sx) * (ex - sx) + (p[1] - sy) * (ey - sy))
    order = [g.start] + nodes + [(ex, ey)]
    for a, b in zip(order, order[1:]):
        g.connect(a, b, g.q.paths)
    for _ in range(extra):
        if len(nodes) >= 2:
            a, b = g.rng.sample(nodes, 2)
            g.connect(a, b, g.q.paths)


def build_country(g):
    q = g.q
    g.zones()
    g.border()
    g.patches()
    g.forest(q.forest)
    for _ in range(q.rivers):
        g.river()
    for _ in range(q.lakes):
        g.lake()
    g.put_buildings(q.buildings)
    g.gate()
    g.start_clearing()
    _chain(g)


def build_wilderness(g):
    q = g.q
    g.zones()
    g.border()
    g.patches()
    g.forest(max(q.forest, 0.48), rocks=0.03)
    for _ in range(min(q.rivers, 1)):
        g.river()
    for _ in range(q.lakes):
        g.lake()
    g.put_buildings(min(q.buildings, 3), sizes=((5, 4), (6, 5)))
    g.gate()
    g.start_clearing()
    # a winding trail through the trees, with clearings where trouble waits
    rng = g.rng
    sx, sy = g.start
    ex, ey = g.exit_porch or g.exit_pos
    way = [g.start]
    n = max(3, (g.w + g.h) // 22)
    for i in range(1, n):
        t = i / n
        x = int(sx + (ex - sx) * t + rng.randint(-g.w // 6, g.w // 6))
        y = int(sy + (ey - sy) * t + rng.randint(-g.h // 6, g.h // 6))
        way.append((max(4, min(g.w - 3, x)), max(4, min(g.h - 3, y))))
    way.append((ex, ey))
    for a, b in zip(way, way[1:]):
        g.connect(a, b, q.paths)
    for cx, cy in way[1:-1]:
        r = rng.randint(2, 4)
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                if g.inside(x, y) and math.hypot(x - cx, y - cy) <= r + 0.3 and g.tag.get((x, y)) not in ('house', 'room', 'gate', 'water'):
                    g.sq[x][y][1] = 0
    for _, porch in g.doors:
        g.connect(porch, min(way, key=lambda p: abs(p[0] - porch[0]) + abs(p[1] - porch[1])), q.paths)


def build_village(g):
    q = g.q
    s = g.style
    g.zones()
    g.border()
    g.patches()
    street = s.path if s.path is not None else s.ground
    ym = g.h // 2 + g.rng.randint(-3, 3)
    xs = [x for x in range(14, g.w - 8, 16 + g.rng.randint(0, 4))]
    for x in range(2, g.w):
        for y in range(ym - 1, ym + 2):
            g.set_floor(x, y, street, 'street')
    for xc in xs:
        for y in range(2, g.h):
            for x in range(xc - 1, xc + 1 + 1):
                if g.tag.get((x, y)) != 'street':
                    g.set_floor(x, y, street, 'street')
    placed = []
    sizes = ((5, 5), (6, 5), (7, 6), (6, 6), (8, 6), (5, 4))

    keep = max(0.12, min(1.0, q.buildings / 14))                 # how many of the places along the streets get a house

    def try_house(x0, y0, bw, bh, side):
        r = g.building(x0, y0, bw, bh, side=side, kind='house', streets=True)
        if r:
            placed.append(r)
        return r
    # along the main street, both sides
    x = 3
    while x < g.w - 6:
        bw, bh = g.rng.choice(sizes)
        if g.rng.random() > keep:
            x += bw + g.rng.randint(1, 3)
        elif try_house(x, ym - 2 - bh + 1, bw, bh, 's') or try_house(x, ym - 2 - bh + 1, 5, 5, 's'):
            x += bw + g.rng.randint(1, 3)
        else:
            x += 2
    x = 3
    while x < g.w - 6:
        bw, bh = g.rng.choice(sizes)
        if g.rng.random() > keep:
            x += bw + g.rng.randint(1, 3)
        elif try_house(x, ym + 2, bw, bh, 'n') or try_house(x, ym + 2, 5, 5, 'n'):
            x += bw + g.rng.randint(1, 3)
        else:
            x += 2
    # along the cross streets
    for xc in xs:
        for side, x0 in (('e', xc - 1 - 6), ('w', xc + 2)):
            y = 3
            while y < g.h - 6:
                if abs(y - ym) < 6:
                    y += 3
                    continue
                bw, bh = g.rng.choice(sizes)
                if g.rng.random() > keep:
                    y += bh + g.rng.randint(1, 3)
                elif try_house(x0 if side == 'e' else x0 + 1, y, 6, bh, side):
                    y += bh + g.rng.randint(1, 3)
                else:
                    y += 2
    g.forest(max(0.08, q.forest * 0.5), rocks=0.01)
    # a well where two streets cross
    if s.well is not None and xs:
        wx = xs[len(xs) // 2]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                g.sq[wx + dx][ym + dy][1] = 0
        g.sq[wx][ym][1] = s.well
        g.tag[(wx, ym)] = 'street'
    g.gate()
    g.start_clearing()
    for x in range(2, g.w):
        for y in range(ym - 1, ym + 2):
            g.sq[x][y][1] = 0 if g.tag.get((x, y)) == 'street' else g.sq[x][y][1]
    for xc in xs:
        for y in range(2, g.h):
            for x in range(xc - 1, xc + 2):
                if g.tag.get((x, y)) == 'street':
                    g.sq[x][y][1] = 0
    g.connect(g.start, (g.start[0], ym) if g.sq[g.start[0]][ym][1] == 0 else g.start, False)
    g.connect((g.start[0], ym), g.exit_porch or g.exit_pos, False)
    g.village = {'ym': ym, 'xs': xs}


def _split(rng, x0, y0, x1, y1, depth=0, min_size=13):
    """Binary space partition: leaves are the rooms' territories."""
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if depth > 5 or (w < min_size * 2 and h < min_size * 2):
        return [(x0, y0, x1, y1)]
    horizontal = h > w if abs(h - w) > 4 else rng.random() < 0.5
    if horizontal and h >= min_size * 2:
        c = rng.randint(y0 + min_size - 1, y1 - min_size)
        return _split(rng, x0, y0, x1, c, depth + 1, min_size) + _split(rng, x0, c + 1, x1, y1, depth + 1, min_size)
    if not horizontal and w >= min_size * 2:
        c = rng.randint(x0 + min_size - 1, x1 - min_size)
        return _split(rng, x0, y0, c, y1, depth + 1, min_size) + _split(rng, c + 1, y0, x1, y1, depth + 1, min_size)
    return [(x0, y0, x1, y1)]


def build_dungeon(g):
    q = g.q
    s = g.style
    rng = g.rng
    wall_ids = s.building or s.trees or [1]
    floor_ids = s.indoor or [s.ground]
    base = rng.choice(wall_ids)
    for x in range(1, g.w + 1):
        for y in range(1, g.h + 1):
            g.sq[x][y][1] = base if rng.random() > 0.04 else rng.choice(wall_ids)
            g.sq[x][y][0] = s.ground
            g.tag[(x, y)] = 'house'
    leaves = _split(rng, 3, 3, g.w - 2, g.h - 2)
    rooms = []
    for (x0, y0, x1, y1) in leaves:
        rw = rng.randint(max(5, (x1 - x0 + 1) // 2), max(5, x1 - x0 - 2))
        rh = rng.randint(max(5, (y1 - y0 + 1) // 2), max(5, y1 - y0 - 2))
        rx = rng.randint(x0 + 1, max(x0 + 1, x1 - rw))
        ry = rng.randint(y0 + 1, max(y0 + 1, y1 - rh))
        rx1, ry1 = min(rx + rw - 1, g.w - 2), min(ry + rh - 1, g.h - 2)
        fl = rng.choice(floor_ids)
        for x in range(rx, rx1 + 1):
            for y in range(ry, ry1 + 1):
                g.sq[x][y][1] = 0
                g.sq[x][y][0] = fl
                g.tag[(x, y)] = 'room'
        rooms.append((rx, ry, rx1, ry1))
    centers = [((a + c) // 2, (b + d) // 2) for a, b, c, d in rooms]
    # corridors: a minimal spanning tree over the rooms, plus a loop or two
    linked, todo = {0}, set(range(1, len(rooms)))
    pairs = []
    while todo:
        i, j = min(((i, j) for i in linked for j in todo),
                   key=lambda p: abs(centers[p[0]][0] - centers[p[1]][0]) + abs(centers[p[0]][1] - centers[p[1]][1]))
        pairs.append((i, j))
        linked.add(j)
        todo.discard(j)
    for _ in range(max(1, len(rooms) // 4)):
        i, j = rng.sample(range(len(rooms)), 2) if len(rooms) > 1 else (0, 0)
        pairs.append((i, j))
    for i, j in pairs:
        (ax, ay), (bx, by) = centers[i], centers[j]
        corner = (bx, ay) if rng.random() < 0.5 else (ax, by)
        for (x0, y0), (x1, y1) in (((ax, ay), corner), (corner, (bx, by))):
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                        px_, py_ = x + dx, y + dy
                        if 2 <= px_ <= g.w - 1 and 2 <= py_ <= g.h - 1 and g.tag.get((px_, py_)) != 'room':
                            g.sq[px_][py_][1] = 0
                            g.sq[px_][py_][0] = s.ground if not s.indoor else rng.choice(floor_ids)
                            g.tag[(px_, py_)] = 'trail'
    # doors where corridors meet rooms
    if s.door is not None:
        for (a, b, c, d) in rooms:
            ring = [(x, b - 1) for x in range(a, c + 1)] + [(x, d + 1) for x in range(a, c + 1)] + \
                   [(a - 1, y) for y in range(b, d + 1)] + [(c + 1, y) for y in range(b, d + 1)]
            for x, y in ring:
                if g.inside(x, y) and g.tag.get((x, y)) == 'trail' and not g.sq[x][y][1] and rng.random() < 0.75:
                    g.sq[x][y][1] = s.door
    # the start room is nearest the start corner, the last the farthest
    c = q.start if q.start in CORNERS else 'sw'
    cx = 0 if c[1] == 'w' else g.w
    cy = 0 if c[0] == 'n' else g.h
    order = sorted(range(len(rooms)), key=lambda i: abs(centers[i][0] - cx) + abs(centers[i][1] - cy))
    first, last = order[0], order[-1]
    g.start = centers[first]
    a, b, c2, d = rooms[last]
    g.exit_pos = ((a + c2) // 2, (b + d) // 2)
    g.exit = g.exit_pos
    if s.exit_item is not None:
        g.sq[g.exit[0]][g.exit[1]][2] = s.exit_item
    else:
        g.warnings.append('The quest has no item of the type "exit", so this level has no way out yet.')
    g.rooms = rooms
    g.first_room, g.last_room = first, last
    for k, r in enumerate(rooms):
        g.interiors.append({'rect': r, 'kind': 'start' if k == first else 'boss' if k == last else 'room', 'door': None, 'porch': None})
    g.reserved |= {(x, y) for x in range(g.start[0] - 2, g.start[0] + 3) for y in range(g.start[1] - 2, g.start[1] + 3)}
    for k, (a, b, c2, d) in enumerate(rooms):
        if k not in (first, last) and rng.random() < 0.6 and s.furniture and (c2 - a) >= 4 and (d - b) >= 4:
            for _ in range(rng.randint(1, 3)):
                x, y = rng.randint(a + 1, c2 - 1), rng.randint(b + 1, d - 1)
                if (x, y) != g.start and not g.sq[x][y][2]:
                    g.sq[x][y][1] = rng.choice(s.furniture)
    if q.dark:
        g.dark = list({((x - 1) // 10 + 1, (y - 1) // 10 + 1) for x in range(1, g.w + 1) for y in range(1, g.h + 1)
                       if g.tag.get((x, y)) == 'room' and rng.random() < 0.01})


def build_maze(g):
    q = g.q
    s = g.style
    rng = g.rng
    wall_ids = s.trees or s.building or [1]
    floor = s.ground if not s.indoor else rng.choice(s.indoor)
    cw, ch = (g.w - 2) // 3, (g.h - 2) // 3
    for x in range(1, g.w + 1):
        for y in range(1, g.h + 1):
            g.sq[x][y][1] = rng.choice(wall_ids)
            g.tag[(x, y)] = 'house'

    def open_(x, y):
        g.sq[x][y][1] = 0
        g.sq[x][y][0] = floor
        g.tag[(x, y)] = 'room'
    for i in range(cw):
        for j in range(ch):
            for dx in (0, 1):
                for dy in (0, 1):
                    open_(3 + i * 3 + dx - 1 + 1, 3 + j * 3 + dy - 1 + 1)
    seen = {(0, 0)}
    stack = [(0, 0)]
    edges = []
    while stack:
        i, j = stack[-1]
        nb = [(i + a, j + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= i + a < cw and 0 <= j + b < ch and (i + a, j + b) not in seen]
        if not nb:
            stack.pop()
            continue
        n = rng.choice(nb)
        seen.add(n)
        edges.append(((i, j), n))
        stack.append(n)
    for _ in range(max(2, cw * ch // 12)):                      # a few loops, so it is not one road
        i, j = rng.randrange(cw), rng.randrange(ch)
        n = (i + rng.choice((1, -1)), j) if rng.random() < 0.5 else (i, j + rng.choice((1, -1)))
        if 0 <= n[0] < cw and 0 <= n[1] < ch:
            edges.append(((i, j), n))
    for (a, b), (c, d) in edges:
        x0, y0 = 3 + a * 3, 3 + b * 3
        x1, y1 = 3 + c * 3, 3 + d * 3
        for x in range(min(x0, x1), max(x0, x1) + 2):
            for y in range(min(y0, y1), max(y0, y1) + 2):
                open_(x, y)
    # start at the corner cell, the way out at the cell farthest from it
    c0 = q.start if q.start in CORNERS else 'sw'
    si = 0 if c0[1] == 'w' else cw - 1
    sj = 0 if c0[0] == 'n' else ch - 1
    g.start = (3 + si * 3, 3 + sj * 3)
    dist = g.reach(g.start)
    far = max(dist, key=lambda p: dist[p])
    g.exit_pos = far
    g.exit = far
    if s.exit_item is not None:
        g.sq[far[0]][far[1]][2] = s.exit_item
    else:
        g.warnings.append('The quest has no item of the type "exit", so this level has no way out yet.')
    g.reserved |= {(x, y) for x in range(g.start[0] - 2, g.start[0] + 3) for y in range(g.start[1] - 2, g.start[1] + 3)}
    g.maze = (cw, ch)
    for x in range(1, g.w + 1):                                   # the rooms of the maze are corridors, not buildings
        for y in range(1, g.h + 1):
            if g.tag.get((x, y)) == 'room':
                g.tag[(x, y)] = 'trail'


def _stone(g):
    """Walls that look like rock: grey and stone ones if the pack has them, else whatever builds its houses."""
    info = g.walls_info
    pool = [i for i in (g.style.building + g.style.rocks) if i != g.style.door and info.get(i, {}).get('solid')]
    rocky = [i for i in pool if any(k in _name(info[i]) for k in ('gray', 'grey', 'stone', 'rock', 'cave', 'stipple', 'mesh'))
             and 'boulder' not in _name(info[i])]
    return rocky or pool or g.style.trees or [1]


def build_cave(g):
    """Winding caverns, found with a few rounds of cellular automaton, with the way out at the far end and wide caverns for fights."""
    q, s, rng = g.q, g.style, g.rng
    w, h = g.w, g.h
    stone = _stone(g)
    tbl = {f['id']: f for f in g.project.tiles.get('floors', [])}
    grey = [i for i, f in tbl.items() if any(k in _name(f) for k in ('stone', 'gray', 'grey', 'cobble', 'gravel', 'cave', 'rock', 'slate'))]
    floors = grey or ([s.path] if s.path is not None else []) or [s.ground]
    spots = [f for f in s.ground_alt if f in tbl and any(k in _name(tbl[f]) for k in ('sand', 'dirt', 'mud', 'moss'))]
    base = rng.choice(stone)
    fill = 0.45
    best = None
    for attempt in range(10):
        wall = [[True] * (h + 2) for _ in range(w + 2)]
        for x in range(2, w):
            for y in range(2, h):
                wall[x][y] = rng.random() < fill
        for it in range(5):
            new = [row[:] for row in wall]
            for x in range(2, w):
                for y in range(2, h):
                    n = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if wall[x + dx][y + dy])           # the square and its neighbours
                    new[x][y] = n >= 5
            wall = new
        seen, comps = set(), []
        for x in range(2, w):
            for y in range(2, h):
                if wall[x][y] or (x, y) in seen:
                    continue
                comp, stack = [], [(x, y)]
                seen.add((x, y))
                while stack:
                    cx, cy = stack.pop()
                    comp.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nb = (cx + dx, cy + dy)
                        if nb not in seen and 2 <= nb[0] < w and 2 <= nb[1] < h and not wall[nb[0]][nb[1]]:
                            seen.add(nb)
                            stack.append(nb)
                comps.append(comp)
        comps.sort(key=len, reverse=True)
        if comps and (best is None or len(comps[0]) > len(best[1])):
            best = (wall, comps[0])
        if comps and len(comps[0]) >= w * h * 0.30:
            break
        fill = max(0.38, fill - 0.015)
    wall, main = best
    openset = set(main)
    for x in range(1, w + 1):
        for y in range(1, h + 1):
            cell = g.sq[x][y]
            if (x, y) in openset:
                cell[1] = 0
                cell[0] = rng.choice(spots) if spots and rng.random() < 0.12 else rng.choice(floors)
                g.tag[(x, y)] = 'trail'
            else:
                cell[1] = base if rng.random() > 0.05 else rng.choice(stone)
                cell[0] = s.ground
                g.tag[(x, y)] = 'house'
    c = q.start if q.start in CORNERS else 'sw'
    cx = 2 if c[1] == 'w' else w - 1
    cy = 2 if c[0] == 'n' else h - 1
    start = min(main, key=lambda p: abs(p[0] - cx) + abs(p[1] - cy))
    dist = {start: 0}
    queue = [start]
    for pt in queue:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (pt[0] + dx, pt[1] + dy)
            if nb in openset and nb not in dist:
                dist[nb] = dist[pt] + 1
                queue.append(nb)
    far = max(dist, key=lambda p: dist[p])

    def cavern(centre, r):
        """Open a round cavern so there is room to move (and for a boss)."""
        for x in range(centre[0] - r, centre[0] + r + 1):
            for y in range(centre[1] - r, centre[1] + r + 1):
                if 2 <= x < w and 2 <= y < h and math.hypot(x - centre[0], y - centre[1]) <= r + 0.3:
                    cell = g.sq[x][y]
                    cell[1] = 0
                    cell[0] = rng.choice(floors)
                    g.tag[(x, y)] = 'trail'
                    openset.add((x, y))
    cavern(start, 2)
    cavern(far, 4)
    g.start = start
    g.exit_pos = g.exit = far
    if s.exit_item is not None:
        g.sq[far[0]][far[1]][2] = s.exit_item
    else:
        g.warnings.append('The quest has no item of the type "exit", so this level has no way out yet.')
    g.reserved |= {(x, y) for x in range(start[0] - 2, start[0] + 3) for y in range(start[1] - 2, start[1] + 3)}
    # wide caverns to hold fights and chests: 5 x 5 squares of open floor, apart from each other
    rooms = []
    wanted = max(2, (w // 10) * (h // 10))
    cand = [p for p in openset if all((p[0] + i, p[1] + j) in openset for i in range(-2, 3) for j in range(-2, 3))]
    rng.shuffle(cand)
    for p in cand:
        if len(rooms) >= wanted:
            break
        rect = (p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2)
        if all(abs(p[0] - r[0] - 2) > 6 or abs(p[1] - r[1] - 2) > 6 for r in rooms) and abs(p[0] - start[0]) + abs(p[1] - start[1]) > 8 \
                and abs(p[0] - far[0]) + abs(p[1] - far[1]) > 8:
            rooms.append(rect)
    for r in rooms:
        g.interiors.append({'rect': r, 'kind': 'room', 'door': None, 'porch': None})
    g.interiors.append({'rect': (far[0] - 2, far[1] - 2, far[0] + 2, far[1] + 2), 'kind': 'boss', 'door': None, 'porch': None})
    g.rooms = rooms
    if q.dark:
        g.dark = sorted({screen_of(x, y) for (x, y) in openset if rng.random() < 0.02} - {screen_of(*start)})


BUILDERS = {'country': build_country, 'village': build_village, 'dungeon': build_dungeon, 'wilderness': build_wilderness,
            'maze': build_maze, 'cave': build_cave}


# ── people, creatures and treasure ───────────────────────────────────────────
def screen_of(x, y):
    return ((x - 1) // 10 + 1, (y - 1) // 10 + 1)


def _produced(project) -> set:
    """Creatures that only appear because another creature or a spell makes them (revealed wraiths, summons)."""
    out = set()
    for c in project.tables['creatures']:
        for k in ('raises_dead', 'reveals_as', 'hides_as'):
            if c.get(k):
                out.add(c[k])
        d = c.get('deceiver') or {}
        if d.get('becomes'):
            out.add(d['becomes'])
    for sp in project.tables['spells']:
        if sp.get('creature'):
            out.add(sp['creature'])
    return out


def progress_of(q: Params, prog: float) -> float:
    """How far along the quest the things at this spot should be: the walk through the level, lifted by the level's place in the quest."""
    return max(0.0, min(1.0, prog)) if q.tier is None else max(0.0, min(1.0, 0.65 * q.tier + 0.35 * prog))


def monster_pool(project, q: Params):
    """(regular creatures sorted by how hard they are, bosses) for the level."""
    made = _produced(project)
    allh = [c for c in hostile(project)]
    regular = [c for c in allh if (c.get('life') or 0) < 120 and int(c.get('size') or 1) == 1 and c['id'] not in made]
    bosses = [c for c in allh if (c.get('life') or 0) >= 120 or int(c.get('size') or 1) > 1]
    if q.creatures:
        pool = [c for c in allh if c['id'] in q.creatures and int(c.get('size') or 1) == 1]
    else:
        lo, hi = {'gentle': (0, .4), 'normal': (.12, .62), 'tough': (.35, .85), 'deadly': (.55, 1.0)}.get(q.difficulty, (.12, .62))
        if q.tier is not None:                                    # a whole quest: the weak ones first, the strong ones last
            t = max(0.0, min(1.0, q.tier))
            off = {'gentle': -.08, 'normal': 0, 'tough': .08, 'deadly': .16}.get(q.difficulty, 0)
            lo = max(0.0, min(.62, .55 * t + off))
            hi = min(1.0, lo + .42 + .1 * t)
        n = len(regular)
        a = int(lo * n)
        pool = regular[a:max(a + 3, int(hi * n))]
    return pool or regular[:3], bosses


def _blocked_around(g, x, y):
    return sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and not g.passable(x + dx, y + dy))


def _spot(g, x, y):
    return g.free(x, y) and g.tag.get((x, y)) not in ('door', 'gate') and not g.sq[x][y][5]


def _pick_weighted(rng, seq, weights):
    total = sum(weights)
    if total <= 0:
        return rng.choice(seq)
    r = rng.random() * total
    for item, w in zip(seq, weights):
        r -= w
        if r <= 0:
            return item
    return seq[-1]


def _creature_for(rng, pool, progress):
    n = len(pool)
    centre = progress * (n - 1)
    weights = [math.exp(-((i - centre) / (0.3 * n + 0.7)) ** 2) for i in range(n)]
    return _pick_weighted(rng, pool, weights)


def populate(g, dist, maxd):
    q, rng, p = g.q, g.rng, g.project
    pool, bosses = monster_pool(p, q)
    cells = [pt for pt in dist if _spot(g, *pt)]
    if not cells:
        return {}
    walk = len(cells)
    per = DIFFICULTY.get(q.difficulty, 4.0) * q.monsters
    if q.theme == 'village':
        per *= 0.35
    n_total = int(round(per * walk / 100 * 0.9))
    sstart = screen_of(*g.start)
    placed = {}
    taken = set()

    def put(pt, cid):
        g.sq[pt[0]][pt[1]][3] = cid
        taken.add(pt)
        placed[pt] = cid

    def near_taken(pt, r=1):
        x, y = pt
        return any((x + dx, y + dy) in taken for dx in range(-r, r + 1) for dy in range(-r, r + 1))
    tries = 0
    count = 0
    while count < n_total and tries < n_total * 40 + 200:
        tries += 1
        pt = rng.choice(cells)
        d = dist[pt]
        if d < 9 or near_taken(pt) or not _spot(g, *pt) or (q.calm_start and screen_of(*pt) == sstart):
            continue
        if g.exit and abs(pt[0] - g.exit[0]) + abs(pt[1] - g.exit[1]) < 3:
            continue
        c = _creature_for(rng, pool, max(0.0, min(1.0, d / maxd)))
        put(pt, c['id'])
        count += 1
        if rng.random() < 0.28 and q.theme not in ('maze',):                     # a pack
            for _ in range(rng.randint(1, 3)):
                nb = (pt[0] + rng.randint(-1, 1), pt[1] + rng.randint(-1, 1))
                if nb in dist and _spot(g, *nb) and nb not in taken:
                    put(nb, c['id'])
                    count += 1
    # rooms keep guards
    for it in g.interiors:
        x0, y0, x1, y1 = it['rect']
        spots = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if (x, y) in dist and _spot(g, x, y) and not near_taken((x, y))]
        if not spots or it['kind'] in ('start', 'shop'):
            continue
        d = min((dist[s] for s in spots), default=0)
        prog = max(0.0, min(1.0, d / maxd))
        if q.theme in ('dungeon', 'cave'):
            chance, many = 0.8, rng.randint(1, 3)
        else:
            chance, many = (0.35 if q.difficulty != 'gentle' else 0.12), 1
        if rng.random() < chance:
            for _ in range(many):
                spots = [s for s in spots if s not in taken]
                if spots and d > 6:
                    c = _creature_for(rng, pool, prog)
                    put(rng.choice(spots), c['id'])
                    count += 1
    # a boss near the way out
    boss = next((c for c in bosses if c['id'] == q.boss), None) if q.boss else None
    if q.boss is not None and boss is None:
        boss = next((c for c in p.tables['creatures'] if c['id'] == q.boss), None)
    if boss and g.exit:
        size = int(boss.get('size') or 1)
        ex, ey = g.exit
        best, bd = None, 10 ** 9
        for pt in dist:
            x, y = pt
            dd = abs(x - ex) + abs(y - ey)
            if dd < 2 or dd > 14 or (x, y) == g.exit:
                continue
            if all(_spot(g, x + i, y + j) and (x + i, y + j) in dist for i in range(size) for j in range(size)) and \
                    not any((x + i, y + j) in taken for i in range(size) for j in range(size)):
                score = abs(dd - 5) + rng.random()
                if score < bd:
                    best, bd = pt, score
        if best:
            put(best, boss['id'])
            g.boss_at = best
        else:
            g.warnings.append('There was no room near the way out for the boss.')
    # people about
    vil = villagers(p)
    want = q.villagers * (3 if q.theme == 'village' else 1)
    if vil and want > 0:
        near = [pt for pt in dist if _spot(g, *pt) and dist[pt] <= (maxd if q.theme == 'village' else 18) and dist[pt] >= 3
                and (q.theme != 'village' or g.tag.get(pt) in ('street', 'trail'))]
        for _ in range(want):
            near = [pt for pt in near if pt not in taken]
            if not near:
                break
            put(rng.choice(near), rng.choice(vil))
    return placed


def treasure(g, dist, maxd):
    q, rng, p = g.q, g.rng, g.project
    cells = [pt for pt in dist if _spot(g, *pt) and not g.sq[pt[0]][pt[1]][3]]
    if not cells:
        return {'gold': 0, 'items': 0, 'chests': 0}
    walk = len(cells)
    nooks = [pt for pt in cells if _blocked_around(g, *pt) >= 5 and dist[pt] > 6]
    used = set()

    def spot(prefer_nook=0.6):
        pool = nooks if nooks and rng.random() < prefer_nook else cells
        for _ in range(30):
            pt = rng.choice(pool)
            if pt not in used and _spot(g, *pt) and not g.sq[pt[0]][pt[1]][3] and dist[pt] > 5:
                used.add(pt)
                return pt
        return None
    screens = walk / 100
    stats = {'gold': 0, 'items': 0, 'chests': 0}
    for _ in range(int(round(1.3 * screens * q.gold))):
        pt = spot()
        if pt:
            prog = progress_of(q, dist[pt] / maxd)
            g.sq[pt[0]][pt[1]][4] = max(1, int((6 + 90 * prog) * rng.uniform(0.5, 1.6)))
            stats['gold'] += 1
    items = p.tables['items']
    potions = [r for r in items if r.get('type') == 'potion' and r['id'] > 0]
    gear = [r for r in items if r.get('type') in ('weapon', 'armour', 'helmet', 'shield', 'amulet') and r['id'] > 0
            and (r.get('price') or 0) > 0 and not r.get('quest')]
    for _ in range(int(round(0.8 * screens * q.potions))):
        pt = spot(0.4)
        if pt and potions:
            r = _pick_weighted(rng, potions, [1.0 / (1 + (r_.get('price') or 20) / 15) for r_ in potions])
            g.sq[pt[0]][pt[1]][2] = r['id']
            stats['items'] += 1
    for _ in range(int(round(0.3 * screens * q.gear))):
        pt = spot(0.75)
        if pt and gear:
            target = 60 + 900 * progress_of(q, dist[pt] / maxd)
            r = _pick_weighted(rng, gear, [math.exp(-(((r_.get('price') or 0) - target) / (target * 0.7 + 50)) ** 2) for r_ in gear])
            g.sq[pt[0]][pt[1]][2] = r['id']
            stats['items'] += 1
    if q.chests and g.style.chest_item is not None:
        cap = max(2, int(screens * 0.4))
        for it in rng.sample(g.interiors, len(g.interiors)):
            if stats['chests'] >= cap:
                break
            x0, y0, x1, y1 = it['rect']
            if it['kind'] in ('start', 'shop'):
                continue
            if rng.random() < (0.5 if q.theme in ('dungeon', 'cave') else 0.45):
                spots = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
                         if (x, y) in dist and _spot(g, x, y) and not g.sq[x][y][3] and _blocked_around(g, x, y) >= 3]
                if spots:
                    x, y = rng.choice(spots)
                    g.sq[x][y][2] = g.style.chest_item
                    stats['chests'] += 1
    return stats


def shop_wares(g, progress):
    items = g.project.tables['items']
    rng = g.rng
    out = []
    potions = sorted((r for r in items if r.get('type') == 'potion' and r['id'] > 0), key=lambda r: r.get('price') or 0)
    out += [r['id'] for r in potions[:5]]
    target = 60 + 700 * progress_of(g.q, progress) + {'gentle': 0, 'normal': 80, 'tough': 160, 'deadly': 260}.get(g.q.difficulty, 80)
    for ty in ('weapon', 'armour', 'shield', 'helmet', 'amulet'):
        rows = [r for r in items if r.get('type') == ty and r['id'] > 0 and (r.get('price') or 0) > 0 and not r.get('quest')]
        rows.sort(key=lambda r: abs((r.get('price') or 0) - target))
        out += [r['id'] for r in rows[:3 if ty in ('weapon', 'armour') else 2]]
    seen, wares = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            wares.append(v)
    return wares[:40]


def make_shop(g, dist, maxd):
    """The house nearest the start (not on its own screen square) becomes a shop; its keeper stands inside."""
    q = g.q
    kept = next((c for c in g.project.tables['creatures'] if c['id'] == -5), None)
    cands = []
    for it in g.interiors:
        if it['kind'] != 'house' or not it.get('porch') or it['porch'] not in dist:
            continue
        x0, y0, x1, y1 = it['rect']
        area = (x1 - x0 + 1) * (y1 - y0 + 1)
        key_at = getattr(g, 'key_at', None)
        if area < 9 or (key_at and x0 <= key_at[0] <= x1 and y0 <= key_at[1] <= y1):
            continue
        cands.append((dist[it['porch']] - area * 0.3, it))
    if not cands or kept is None:
        if q.shop:
            g.warnings.append('There was no house to make a shop of.' if kept else 'This quest has no shopkeeper creature (-5).')
        return
    cands.sort(key=lambda c: c[0] if c[1]['porch'] and dist[c[1]['porch']] >= 6 else c[0] + 40)
    it = cands[0][1]
    it['kind'] = 'shop'
    x0, y0, x1, y1 = it['rect']
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    for x in range(x0, x1 + 1):                                # nothing else in the shop but the keeper
        for y in range(y0, y1 + 1):
            c = g.sq[x][y]
            c[2] = c[3] = c[4] = 0
    g.sq[cx][cy][1] = 0
    g.sq[cx][cy][3] = -5
    sc = screen_of(cx, cy)
    k = 1
    g.shop_screens[sc] = k
    wares = shop_wares(g, min(1.0, dist[it['porch']] / maxd))
    g.shops[k] = '\n'.join(' '.join(str(v) for v in wares[i:i + 4]) for i in range(0, len(wares), 4)) + '\n'
    if sc not in g.peaceful:
        g.peaceful.append(sc)


def make_puzzle(g):
    """A locked door with its key somewhere else: the boss room in a dungeon, the farthest house elsewhere."""
    s = g.style
    if not s.locked:
        g.warnings.append('The quest has no locked doors and keys, so there is no puzzle.')
        return None
    colour, (door_id, key_id) = next(iter(s.locked.items()))
    rng = g.rng
    if g.q.theme == 'dungeon' and getattr(g, 'rooms', None):
        a, b, c, d = g.rooms[g.last_room]
        ring = [(x, b - 1) for x in range(a, c + 1)] + [(x, d + 1) for x in range(a, c + 1)] + \
               [(a - 1, y) for y in range(b, d + 1)] + [(c + 1, y) for y in range(b, d + 1)]
        doors = [pt for pt in ring if g.inside(*pt) and g.sq[pt[0]][pt[1]][1] == s.door and s.door is not None]
        if not doors:
            doors = [pt for pt in ring if g.inside(*pt) and g.tag.get(pt) == 'trail' and not g.sq[pt[0]][pt[1]][1]]
        if not doors:
            g.warnings.append('The last room has no doorway to lock.')
            return None
        for x, y in doors:
            g.sq[x][y][1] = door_id
        vault = g.rooms[g.last_room]
    else:
        cands = [it for it in g.interiors if it['kind'] == 'house' and it.get('door')]
        if not cands:
            g.warnings.append('There was no house to lock.')
            return None
        dist0 = g.reach()
        cands = [it for it in cands if it['porch'] in dist0]
        if not cands:
            return None
        it = max(cands, key=lambda i: dist0[i['porch']])
        dx, dy = it['door']
        g.sq[dx][dy][1] = door_id
        it['kind'] = 'vault'
        vault = it['rect']
    dist = g.reach()                                       # without the key: the vault is out of reach
    cells = [pt for pt in dist if _spot(g, *pt) and dist[pt] > 8]
    nooks = [pt for pt in cells if _blocked_around(g, *pt) >= 5] or cells
    if not nooks:
        g.warnings.append('There was no place to hide the key.')
        return None
    far = max(dist.values()) or 1
    mid = [pt for pt in nooks if 0.3 * far <= dist[pt] <= 0.8 * far] or nooks
    kx, ky = rng.choice(mid)
    g.sq[kx][ky][2] = key_id
    g.key_at = (kx, ky)
    g.vault = vault
    return colour


def ensure_connected(g):
    """Everything that should be reachable is: the way out, every porch. Missing ones are joined by a trail."""
    for _ in range(3):
        dist = g.reach()
        targets = []
        if g.exit and g.q.theme not in ('dungeon', 'maze', 'cave'):
            targets.append(g.exit_porch or g.exit)
        for _, porch in g.doors:
            if g.inside(*porch):
                targets.append(porch)
        missing = [t for t in targets if t not in dist]
        if not missing:
            return
        for t in missing:
            near = min(dist, key=lambda p: abs(p[0] - t[0]) + abs(p[1] - t[1]))
            g.connect(near, t, False)


def finish(g, stats) -> Result:
    sq = [[[1, 0, 0, 0, 0, 0] for _ in range(SIZE + 1)] for _ in range(SIZE + 1)]
    for x in range(1, SIZE + 1):
        for y in range(1, SIZE + 1):
            sq[x][y] = list(g.sq[x][y])
    return Result(sq=sq, start=g.start, exit=g.exit, shops=g.shops, shop_screens=g.shop_screens, peaceful=sorted(set(g.peaceful)),
                  dark=sorted(set(g.dark)), warnings=g.warnings, stats=stats, area=(g.w, g.h))


def generate(project, params: Params) -> Result:
    g = Gen(project, params)
    q = params
    BUILDERS.get(q.theme, build_country)(g)
    ensure_connected(g)
    for dx in range(-1, 2):                                       # the hero must stand on open ground
        pass
    sx, sy = g.start
    g.sq[sx][sy][1] = 0
    keyed = None
    if q.puzzle:
        keyed = make_puzzle(g)
    dist = g.reach(keys=tuple(g.style.locked)) if keyed else g.reach()
    maxd = max(dist.values()) or 1
    if q.calm_start:
        g.peaceful.append(screen_of(*g.start))
    if q.shop and q.theme not in ('maze', 'dungeon', 'cave'):
        make_shop(g, dist, maxd)
    placed = populate(g, dist, maxd)
    tre = treasure(g, dist, maxd)
    if g.exit and g.exit not in g.reach(keys=tuple(g.style.locked)):
        g.warnings.append('The hero cannot reach the way out. Roll again, or change the settings.')
    if keyed:
        kx, ky = g.key_at
        kid = g.style.locked[keyed][1]
        if g.sq[kx][ky][2] != kid or g.key_at not in g.reach():
            g.warnings.append('The key for the locked door is out of reach. Roll again.')
    stats = {'creatures': sum(1 for v in placed.values() if v > 0), 'people': sum(1 for v in placed.values() if v < 0),
             'walkable': len(dist), 'screens': (g.w // 10, g.h // 10), 'buildings': len(g.interiors), 'puzzle': keyed, **tre}
    return finish(g, stats)
