"""World: the 100x100 level map split into 10x10 screens ("rooms").

The original keeps a separate `room` copy of the current screen and writes it
back into `map` when leaving (goroom2).  Here the screen is a *view* onto the
map, and the write-back rules are applied in `leave_room()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .formats import GameData, Square, MAP_SIZE
from .state import Player, Status, Enemy
from . import rules

ROOM = 10

# Per-level settings (start position, shops, stories, teleporter) live at the top of each level's script
# in the pack's levels/<n>/script.qs, so new levels can set their own.


def screen_of(x: int, y: int) -> tuple[int, int]:
    """1-based screen coordinates (original peddler() / carta indexing)."""
    return (x - 1) // ROOM + 1, (y - 1) // ROOM + 1


def room_origin(X: int, Y: int) -> tuple[int, int]:
    """Top-left absolute tile of the screen containing (X, Y)."""
    return ((X - 1) // ROOM) * ROOM + 1, ((Y - 1) // ROOM) * ROOM + 1


@dataclass
class World:
    data: GameData
    level: int = 0
    grid: list = field(default_factory=list)            # grid[x][y] -> Square, 1-based
    visited: set = field(default_factory=set)            # screens seen (automap, original `carta`)
    enemies: list = field(default_factory=list)          # Enemy objects on the current screen
    origin: tuple = (1, 1)
    carry: list = field(default_factory=list)            # raised allies that follow the hero to the next screen
    stash: dict = field(default_factory=dict)            # level -> (grid, visited) of levels left by a link (Game.travel)

    # ── levels ────────────────────────────────────────────────────────────────
    def pristine(self, level: int) -> list:
        """A level's map as the pack has it (with the pack's corrections to its own maps)."""
        grid = self.data.load_level(level)
        pack = self.data.src.pack
        if pack.fixed('map'):
            for fix in pack.quest.get('map_fixes') or []:
                if fix.get('level') == level and self.in_map(fix.get('x', 0), fix.get('y', 0)):
                    q = grid[fix['x']][fix['y']]
                    for f in ('floor', 'wall', 'mon', 'item', 'gold', 'deco'):
                        if f in fix:
                            setattr(q, f, fix[f])
        return grid

    def travel(self, level: int, x: int, y: int, player: Player, st: Status) -> bool:
        """A link (ladder, stairs, hole ...) to (x, y) on another level: this level's map is kept as it is
        (so what was done here stays done when the hero comes back), the other's is picked up as it was
        left, or loaded. True if it was loaded fresh."""
        self.leave_room()
        self.stash[self.level] = (self.grid, self.visited)
        fresh = level not in self.stash
        if fresh:
            self.grid, self.visited = self.pristine(level), set()
        else:
            self.grid, self.visited = self.stash.pop(level)
        self.level = st.level = level
        player.X, player.Y = x, y
        self.enter_room(player, st)
        return fresh

    def stash_to_save(self) -> dict:
        """The levels left by links, as what differs from the pack's maps (the DELUXE block of a save)."""
        out = {}
        for level, (grid, visited) in self.stash.items():
            base, diff = self.pristine(level), []
            for x in range(1, MAP_SIZE + 1):
                for y in range(1, MAP_SIZE + 1):
                    a, b = grid[x][y], base[x][y]
                    if (a.floor, a.wall, a.item, a.mon, a.gold, a.deco) != (b.floor, b.wall, b.item, b.mon, b.gold, b.deco):
                        diff.append([x, y, a.floor, a.wall, a.item, a.mon, a.gold, a.deco])
            out[str(level)] = {'diff': diff, 'visited': sorted([i, j] for i, j in visited)}
        return out

    def stash_from_save(self, saved: dict) -> None:
        self.stash = {}
        for level, v in (saved or {}).items():
            grid = self.pristine(int(level))
            for x, y, fl, wa, it, mo, go, de in v.get('diff', []):
                if self.in_map(x, y):
                    grid[x][y] = Square(fl, wa, mo, it, go, de)
            self.stash[int(level)] = (grid, {tuple(c) for c in v.get('visited', [])})

    def load_level(self, level: int, player: Player, st: Status, start=(5, 5)) -> None:
        if not self.level:
            self.stash = {}                                # a new game starts with no level kept
        self.level = level
        st.level = level
        self.grid = self.pristine(level)
        self.visited = set()
        player.X, player.Y = start
        st.mission1 = st.mission2 = 0
        player.inv.rkey = player.inv.bkey = player.inv.ykey = 0
        player.more.pop('keys', None)                      # a pack's own key colours go too
        if player.hero.rep <= -4:
            player.hero.rep = -3
        self.enter_room(player, st)

    def sq(self, x: int, y: int) -> Square:
        return self.grid[x][y]

    def in_map(self, x: int, y: int) -> bool:
        return 1 <= x <= MAP_SIZE and 1 <= y <= MAP_SIZE

    # ── screens ───────────────────────────────────────────────────────────────
    def in_room(self, x: int, y: int) -> bool:
        ox, oy = self.origin
        return ox <= x < ox + ROOM and oy <= y < oy + ROOM

    def room_tiles(self):
        ox, oy = self.origin
        for x in range(ox, ox + ROOM):
            for y in range(oy, oy + ROOM):
                yield x, y

    def enter_room(self, player: Player, st: Status) -> None:
        """goroom2 (second half) + enemycheck(): build the enemy list for the new screen."""
        self.origin = room_origin(player.X, player.Y)
        self.visited.add(((self.origin[0] - 1) // ROOM, (self.origin[1] - 1) // ROOM))
        self.rescan(player, st)
        self.place_carried(player, st)

    def place_carried(self, player: Player, st: Status) -> None:
        """Allies raised with a following spell arrive with the hero: each on the nearest free square to him."""
        carried, self.carry = self.carry, []
        pack = self.data.src.pack
        for e in carried:
            n = self.size_of(e.type)
            taken = {(player.X, player.Y)}
            best = None
            for sx, sy in self.room_tiles():
                cells = self.footprint(sx, sy, n)
                if all(self.in_room(cx, cy) and self.grid[cx][cy].wall == 0 and self.grid[cx][cy].mon == 0
                       and (cx, cy) not in taken and pack.item_type(self.grid[cx][cy].item) not in
                       ('teleporter', 'exit', 'ladder', 'rope', 'stairs', 'hole', 'jump_pad') for cx, cy in cells):
                    d = max(abs(sx - player.X), abs(sy - player.Y))
                    if best is None or (d, sx, sy) < best[:3]:
                        best = (d, sx, sy)
            if best is None:
                continue                                    # no room on this screen: it stays behind
            e.x, e.y = best[1], best[2]
            for cx, cy in self.cells(e):
                self.grid[cx][cy].mon = e.type
            e.moved = True
            self.enemies.append(e)
        st.mons = len(self.enemies)

    def rescan(self, player: Player, st: Status) -> None:
        """enemycheck(): rebuild the creature list from the current screen, column by column."""
        self.enemies = []
        covered = set()                                    # squares of a big creature past its top-left one
        for x, y in self.room_tiles():
            t = self.grid[x][y].mon
            if t == 0 or (x, y) in covered:
                continue
            e = Enemy(type=t, x=x, y=y)
            n = self.size_of(t)
            for cx, cy in self.footprint(x, y, n)[1:]:      # a big creature stands on n x n squares
                if self.in_room(cx, cy):
                    self.grid[cx][cy].mon = t
                    covered.add((cx, cy))
            ms = self.data.monsters.get(t)
            if ms:
                e.life = e.mlife = ms.life
                e.power, e.atk, e.defense = ms.power, ms.atk, ms.defense
                e.warm, e.marm, e.range, e.att = ms.warm, ms.marm, ms.range, ms.att
                if t < 0 and player.hero.rep <= -4:
                    e.att = 9                              # bad reputation: NPCs turn hostile
            shape = player.more.get('disguise')
            if shape and player.hero.invisible > 0 and e.is_npc and e.type != -5 and e.att > -10 \
                    and rules.random(100) < shape[1]:
                e.att = 8                                  # a disguised hero: some people see through it
            if player.hero.invisible > 0 and e.att >= 0 and e.att != 8:
                e.att = -5                                 # can't see the invisible hero
            self.enemies.append(e)
        st.mons = len(self.enemies)

    def leave_room(self) -> None:
        """goroom2 (first half): write-back rules applied to the screen being left."""
        pack = self.data.src.pack
        self.carry = []
        for e in self.enemies:
            if e.__dict__.get('_risen'):                   # the raised go back to rest when the hero leaves
                for cx, cy in self.cells(e):
                    self.grid[cx][cy].mon = 0
                if e.__dict__.get('_follow') and e.life > 0:
                    self.carry.append(e)                   # unless the spell said they follow him: until they die
        for x, y in self.room_tiles():
            q = self.grid[x][y]
            hidden = pack.trait(q.mon, 'hides_as') if q.mon else None
            if hidden:
                q.mon = hidden                             # a revealed wraith goes invisible again
            if q.mon <= -100:
                q.mon = 0                                  # summoned allies vanish
            if q.deco == pack.deco('open_door') and q.mon == 0:   # an opened door closes (as a plain door)
                q.deco = 0
                q.wall = pack.door('plain')
        # NPCs standing on the edge are nudged inside so they don't block the doorway
        ox, oy = self.origin
        for x, y in self.room_tiles():
            q = self.grid[x][y]
            if q.mon and (x in (ox, ox + ROOM - 1) or y in (oy, oy + ROOM - 1)):
                for _ in range(200):
                    nx, ny = ox + 1 + rules.random(8), oy + 1 + rules.random(8)
                    t = self.grid[nx][ny]
                    if t.wall == 0 and t.mon == 0:
                        t.mon, q.mon = q.mon, 0
                        break

    def enemy_at(self, x: int, y: int) -> Enemy | None:
        for e in self.enemies:
            n = self.size_of(e.type)
            if e.x <= x < e.x + n and e.y <= y < e.y + n and e.life > 0:
                return e
        return None

    # ── big creatures (creatures.json `size`: n x n squares, the creature's own square its top left) ──
    def size_of(self, t: int) -> int:
        return max(1, int(self.data.src.pack.trait(t, 'size', 1) or 1)) if t else 1

    @staticmethod
    def footprint(x: int, y: int, n: int) -> list:
        """The squares an n x n creature with its top left at (x, y) stands on, that one first."""
        return [(x + i, y + j) for i in range(n) for j in range(n)]

    def cells(self, e: Enemy) -> list:
        return self.footprint(e.x, e.y, self.size_of(e.type))

    def gap(self, e: Enemy, x: int, y: int) -> tuple:
        """How far (x, y) is from the creature's nearest square, across and down."""
        n = self.size_of(e.type)
        return max(e.x - x, 0, x - (e.x + n - 1)), max(e.y - y, 0, y - (e.y + n - 1))
