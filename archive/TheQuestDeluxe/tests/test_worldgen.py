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


def install(p, res, title=None, story=None):
    """Put a generated level (a worldgen.Result) in the project as its new last level; the number."""
    from editor.project import Grid
    n = p.add_level()
    p.grids[n] = Grid(list(res.rows()))
    p.set_constant(n, 'START', tuple(res.start), 'start')
    if res.shop_screens:
        p.set_constant(n, 'SHOPS', dict(res.shop_screens), 'shops')
    if res.peaceful:
        p.set_constant(n, 'PEACEFUL_SCREENS', list(res.peaceful), 'peace')
    if story:
        from studio import storytext
        p.set_constant(n, 'STORIES', [storytext.add_story(p, story)], 'stories')
    p.shops[n] = dict(res.shops)
    p.dirty |= {'quest', ('map', n), ('script', n), ('shops', n), 'stories'}
    return n


def open_game(p, pack):
    p.save()
    os.environ['QUEST_PACK'] = pack
    import pygame
    pygame.init()
    from engine.game import Game
    window = pygame.display.set_mode((640, 480))
    g = Game(window, settings={'fixes': 'on', 'sound': 'off'})
    g.fast = True
    return g


def key(g, k, uni=''):
    import pygame
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=uni, mod=0))


def walk_level(g, p, puzzle):
    """Walk the level the game is on from where the hero stands to its exit (the key picked up first when there is a locked door),
    ending with the 'leave?' question on screen. The terrain alone: the creatures are taken off."""
    import pygame
    from collections import deque
    from engine.state import has_key
    w = g.world
    w.enemies = []
    for x in range(1, 101):
        for y in range(1, 101):
            w.grid[x][y].mon = 0

    def walk_ok(x, y, keys):
        q = w.sq(x, y)
        if not q.wall:
            return True
        wall = g.pack.wall(q.wall)
        if wall.get('door') == 'plain':
            return True
        if wall.get('door') == 'locked':
            return wall.get('key') in keys
        return not wall.get('solid') and not wall.get('door')

    def bfs(src, want, keys):
        prev = {src: None}
        dq = deque([src])
        while dq:
            cur = dq.popleft()
            if want(cur):
                path, c = [], cur
                while c:
                    path.append(c)
                    c = prev[c]
                return path[::-1]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n_ = (cur[0] + dx, cur[1] + dy)
                if n_ not in prev and w.in_map(*n_) and walk_ok(*n_, keys):
                    prev[n_] = cur
                    dq.append(n_)
        return None
    KEY = {(1, 0): pygame.K_RIGHT, (-1, 0): pygame.K_LEFT, (0, 1): pygame.K_DOWN, (0, -1): pygame.K_UP}

    def walk(path):
        for a, b in zip(path, path[1:]):
            d = (b[0] - a[0], b[1] - a[1])
            for attempt in range(6):
                g.overlay = None
                key(g, KEY[d])
                if (g.player.X, g.player.Y) == b:
                    break
            else:
                print('STUCK at', a, '->', b, 'wall', w.sq(*b).wall)
                sys.exit(2)
    exit_item = next(r['id'] for r in p.tables['items'] if r.get('type') == 'exit')
    key_ids = {r['id']: r['key'] for r in p.tables['items'] if r.get('type') == 'key'}
    start = (g.player.X, g.player.Y)
    keys = set()
    if puzzle:
        kp = bfs(start, lambda c: w.sq(*c).item in key_ids, keys)
        print('key reachable without a key:', kp is not None)
        assert kp is not None, 'the key cannot be reached'
        walk(kp)
        key(g, pygame.K_RETURN, '\r')
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


def walk_in_engine(theme, seed, size, puzzle):
    """(child process) Put a generated level in a copy of the pack as level 8 and walk the game from its start to its exit."""
    tmp = tempfile.mkdtemp()
    pack = os.path.join(tmp, 'T')
    shutil.copytree('packs/TheQuest', pack)
    from editor.project import Project
    from studio import worldgen
    p = Project(pack)
    res = worldgen.generate(p, worldgen.Params(seed=seed, theme=theme, screens=(size, size), boss=34, puzzle=puzzle, shop=True, buildings=5))
    print('generated', res.stats, res.warnings)
    n = install(p, res)
    g = open_game(p, pack)
    g.quick_start(1, n, tuple(res.start))
    print('level', g.world.level, 'hero at', g.player.X, g.player.Y)
    assert g.world.level == n
    walk_level(g, p, puzzle)
    print('OK')


def walk_quest(seed):
    """(child process) A whole quest of generated levels (with a story before each) in a blank pack: the game plays level after level
    from the first start to the last exit, through the stories, the ending and the credits."""
    tmp = tempfile.mkdtemp()
    pack = os.path.join(tmp, 'Q')
    from editor.project import Project
    from engine.pack import DEFAULT_PACK
    from studio import worldgen
    import random
    Project.create(pack, DEFAULT_PACK, blank=True)
    p = Project(pack)
    themes = worldgen.journey_themes('depths', 3, random.Random(seed))
    made = []
    for i, theme in enumerate(themes):
        par = worldgen.quest_params(i, 3, theme, seed * 10 + i, 3, 'steady', boss=34 if i == 2 else None, puzzles=True)
        res = worldgen.generate(p, par)
        assert not any('cannot reach' in w or 'out of reach' in w for w in res.warnings), (theme, res.warnings)
        made.append((par, res))
    # the blank pack's empty level 1 becomes the first
    from editor.project import Grid
    first = made[0][1]
    p.grids[1] = Grid(list(first.rows()))
    p.set_constant(1, 'START', tuple(first.start), 'start')
    p.shops[1] = dict(first.shops)
    p.dirty |= {('map', 1), ('script', 1), ('shops', 1)}
    for par, res in made[1:]:
        install(p, res, story=['The road goes on.', 'Deeper.'])
    assert p.levels == 3
    g = open_game(p, pack)
    g.quick_start(1, 1, tuple(first.start))
    import pygame
    for n in (1, 2, 3):
        assert g.world.level == n, (g.world.level, n)
        walk_level(g, p, made[n - 1][0].puzzle)
        key(g, pygame.K_y, 'y')                                    # yes, leave
        for _ in range(8):                                         # the stories (and the ending) wait for a key
            if g.overlay is None or g.world.level != n:
                break
            key(g, pygame.K_RETURN, '\r')
        print('left level', n, '-> level', g.world.level, 'overlay:', type(g.overlay).__name__ if g.overlay else None)
        if n < 3:
            assert g.world.level == n + 1, 'the exit did not lead to the next level'
        else:
            assert g.overlay is not None, 'after the last level the ending shows'
    print('QUEST')


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
    # a level late in a whole quest holds tougher creatures and dearer wares than one at its start
    def mean_threat(tier):
        total = n = 0
        for seed in (1, 2, 3):
            r = worldgen.generate(p, worldgen.Params(seed=seed, theme='country', screens=(5, 5), tier=tier, boss=None))
            for x in range(1, 101):
                for y in range(1, 101):
                    mo = r.sq[x][y][3]
                    c = next((c for c in p.tables['creatures'] if c['id'] == mo), None) if mo > 0 else None
                    if c:
                        total += worldgen.threat(c)
                        n += 1
        return total / max(1, n)
    first, last = mean_threat(0.0), mean_threat(1.0)
    assert last > first * 1.5, ('later levels are tougher', first, last)
    print(f'worldgen: {made} levels (6 themes, 3 sizes, seeds): the same seed gives the same level, the hero starts on open ground, '
          'the way out and everything on the level can be reached, shops have wares: ok')


def engine_checks():
    me = os.path.abspath(__file__)
    cases = [('country', 7, 5, False), ('village', 7, 5, False), ('dungeon', 7, 5, True), ('wilderness', 7, 5, False),
             ('maze', 7, 4, False), ('country', 3, 5, True), ('cave', 7, 5, False)]
    for theme, seed, size, puzzle in cases:
        r = subprocess.run([sys.executable, me, '--walk', theme, str(seed), str(size), 'puzzle' if puzzle else 'plain'],
                           capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert r.returncode == 0 and 'WALKED' in r.stdout, (theme, seed, size, puzzle, r.stdout[-600:], r.stderr[-600:])
    for seed in (3, 5):
        r = subprocess.run([sys.executable, me, '--quest', str(seed)], capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert r.returncode == 0 and 'QUEST' in r.stdout, (seed, r.stdout[-900:], r.stderr[-900:])
    print(f'worldgen: the game walks {len(cases)} generated levels from start to exit (keys picked up on the way): ok')
    print('worldgen: the game plays a whole generated quest, level after level, through the stories to the ending: ok')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--quest':
        walk_quest(int(sys.argv[2]))
        print('QUEST')
    elif len(sys.argv) > 1 and sys.argv[1] == '--walk':
        walk_in_engine(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == 'puzzle')
        print('WALKED')
    else:
        pure_checks()
        engine_checks()
        print('all worldgen checks passed')
