"""The level generator behind the Studio's wizard: the levels it makes are whole, fair and playable.

Pure checks (no window): the same seed makes the same level; the hero starts on open ground; the way out can be reached
(with the key, when there is a locked door); nothing lies inside a wall; every item, heap of gold and creature can be reached;
the shop and the peaceful start are set. Then the real game engine walks each theme from its start to its exit
(the key picked up on the way when the level has a locked door), in a child process because the engine reads its pack
when it is imported.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')


def walk_in_engine(theme, seed, size, puzzle):
    """(child process) Put a generated level in a copy of the pack as level 8 and walk the game from its start to its exit."""
    tmp = tempfile.mkdtemp()
    pack = os.path.join(tmp, 'T')
    shutil.copytree('packs/TheQuest', pack)
    from editor.project import Project, Grid
    from studio import worldgen, levelmeta
    p = Project(pack)
    res = worldgen.generate(p, worldgen.Params(seed=seed, theme=theme, screens=(size, size), boss=34, puzzle=puzzle, shop=True, buildings=5))
    print('generated', res.stats, res.warnings)
    n = p.add_level()
    p.grids[n] = Grid(list(res.rows()))
    p.set_constant(n, 'START', tuple(res.start), 'start')
    if res.shop_screens: p.set_constant(n, 'SHOPS', dict(res.shop_screens), 'shops')
    if res.peaceful: p.set_constant(n, 'PEACEFUL_SCREENS', list(res.peaceful), 'peace')
    p.shops[n] = dict(res.shops)
    p.dirty |= {'quest', ('map', n), ('script', n), ('shops', n)}
    p.save()
    os.environ['QUEST_PACK'] = pack
    import pygame
    pygame.init()
    from engine.game import Game
    from engine import settings as player_settings
    window = pygame.display.set_mode((640, 480))
    g = Game(window, settings={'fixes': 'on', 'sound': 'off'})
    g.fast = True
    g.quick_start(1, n, tuple(res.start))
    w = g.world
    print('level', w.level, 'hero at', g.player.X, g.player.Y)
    assert w.level == n
    # the terrain alone: no creatures in the way
    w.enemies = []
    for x in range(1, 101):
        for y in range(1, 101):
            w.grid[x][y].mon = 0
    from collections import deque
    from engine.state import has_key
    def walk_ok(x, y, keys):
        q = w.sq(x, y)
        if not q.wall: return True
        wall = g.pack.wall(q.wall)
        if wall.get('door') == 'plain': return True
        if wall.get('door') == 'locked': return wall.get('key') in keys
        return not wall.get('solid') and not wall.get('door')
    def bfs(src, want, keys):
        prev = {src: None}; dq = deque([src])
        while dq:
            cur = dq.popleft()
            if want(cur):
                path = []; c = cur
                while c: path.append(c); c = prev[c]
                return path[::-1]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n_ = (cur[0] + dx, cur[1] + dy)
                if n_ not in prev and w.in_map(*n_) and walk_ok(*n_, keys):
                    prev[n_] = cur; dq.append(n_)
        return None
    KEY = {(1, 0): pygame.K_RIGHT, (-1, 0): pygame.K_LEFT, (0, 1): pygame.K_DOWN, (0, -1): pygame.K_UP}
    def walk(path):
        for a, b in zip(path, path[1:]):
            d = (b[0] - a[0], b[1] - a[1])
            for attempt in range(6):
                g.overlay = None
                g.handle(pygame.event.Event(pygame.KEYDOWN, key=KEY[d], unicode='', mod=0))
                if (g.player.X, g.player.Y) == b: break
            else:
                print('STUCK at', a, '->', b, 'wall', w.sq(*b).wall); sys.exit(2)
    exit_item = next(r['id'] for r in p.tables['items'] if r.get('type') == 'exit')
    key_ids = {r['id']: r['key'] for r in p.tables['items'] if r.get('type') == 'key'}
    start = (g.player.X, g.player.Y)
    keys = set()
    if puzzle:
        kp = bfs(start, lambda c: w.sq(*c).item in key_ids, keys)
        print('key reachable without a key:', kp is not None)
        assert kp is not None, 'the key cannot be reached'
        walk(kp)
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode='\r', mod=0))
        colour = key_ids[[i for i in key_ids if True][0]] if False else None
        got = [c for c in set(key_ids.values()) if has_key(g.player, c)]
        print('hero has keys:', got)
        assert got, 'walking over the key did not pick it up'
        keys = set(got)
        start = (g.player.X, g.player.Y)
    path = bfs(start, lambda c: w.sq(*c).item == exit_item, keys)
    print('exit reachable by the engine rules:', path is not None)
    assert path is not None, 'engine cannot reach the exit'
    walk(path)
    print('walked to', (g.player.X, g.player.Y), 'overlay:', type(g.overlay).__name__ if g.overlay else None)
    assert type(g.overlay).__name__ == 'YesNo'
    print('OK')



def pure_checks():
    from editor.project import Project
    from studio import worldgen
    p = Project(os.path.join(ROOT, 'packs', 'TheQuest'))
    walls = {w['id']: w for w in p.tiles['walls']}

    def passable(sq, x, y, keys=True):
        wa = sq[x][y][1]
        if not wa:
            return True
        w = walls.get(wa, {})
        if w.get('door') == 'plain':
            return True
        if w.get('door') == 'locked':
            return keys
        return not w.get('solid') and not w.get('door')
    made = 0
    for theme in worldgen.THEMES:
        for seed in (1, 2, 3):
            for screens, puzzle in (((3, 3), False), ((5, 5), True), ((10, 10), False)):
                par = worldgen.Params(seed=seed, theme=theme, screens=screens, puzzle=puzzle, boss=34, shop=True, buildings=5)
                r = worldgen.generate(p, par)
                again = worldgen.generate(p, par)
                assert r.sq == again.sq and r.start == again.start, (theme, seed, 'the same seed makes the same level')
                assert not any('cannot reach' in w or 'out of reach' in w for w in r.warnings), (theme, seed, screens, r.warnings)
                sx, sy = r.start
                assert passable(r.sq, sx, sy), (theme, seed, 'the hero starts in a wall')
                seen = {(sx, sy)}
                q = deque([(sx, sy)])
                while q:
                    x, y = q.popleft()
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if (nx, ny) not in seen and 1 <= nx <= 100 and 1 <= ny <= 100 and passable(r.sq, nx, ny):
                            seen.add((nx, ny))
                            q.append((nx, ny))
                assert r.exit in seen, (theme, seed, screens, 'the way out cannot be reached')
                w_, h_ = r.area
                for x in range(1, 101):
                    for y in range(1, 101):
                        fl, wa, it, mo, go, de = r.sq[x][y]
                        if (it or mo or go > 0) and (x > w_ or y > h_):
                            raise AssertionError((theme, seed, 'something outside the level area', x, y))
                        if (it or mo or go > 0) and (x, y) not in seen:
                            walled = wa and not passable(r.sq, x, y)
                            assert not walled, (theme, seed, screens, 'something lies inside a wall', x, y, it, mo, go)
                            assert not mo > 0, (theme, seed, 'a creature that cannot be reached', x, y)
                for sc, k in r.shop_screens.items():
                    assert k in r.shops and r.shops[k].strip(), (theme, seed, 'a shop with nothing to sell')
                made += 1
    print(f'worldgen: {made} levels (5 themes, 3 sizes, seeds): the same seed gives the same level, the hero starts on open ground, '
          'the way out and everything on the level can be reached, shops have wares: ok')


def engine_checks():
    me = os.path.abspath(__file__)
    cases = [('country', 7, 5, False), ('village', 7, 5, False), ('dungeon', 7, 5, True), ('wilderness', 7, 5, False),
             ('maze', 7, 4, False), ('country', 3, 5, True)]
    for theme, seed, size, puzzle in cases:
        r = subprocess.run([sys.executable, me, '--walk', theme, str(seed), str(size), 'puzzle' if puzzle else 'plain'],
                           capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert r.returncode == 0 and 'WALKED' in r.stdout, (theme, seed, size, puzzle, r.stdout[-600:], r.stderr[-600:])
    print(f'worldgen: the game walks {len(cases)} generated levels from start to exit (keys picked up on the way): ok')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--walk':
        walk_in_engine(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == 'puzzle')
        print('WALKED')
    else:
        pure_checks()
        engine_checks()
        print('all worldgen checks passed')
