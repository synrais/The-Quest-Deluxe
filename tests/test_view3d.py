"""FPS mode (Deluxe): a view, not a different game.

1. The same random games played from above and in FPS mode (turning to face the way, then walking
   forward) must reach the same state after every key: hero, inventory, map, creatures, messages.
2. The 3D view draws everywhere those games go, fast enough to glide (under 60 ms a frame here).
3. The Quest I pack's looks: building walls are blocks, trees billboards, water and blood flat,
   carpeted rooms have roofs; an animation's hit lands on the creature in view.
4. The status frame: the hero's portrait (eyes and rings) and his states in words, in FPS mode only.

    python tests/test_view3d.py              # 12 runs of 200 keys
    python tests/test_view3d.py --runs 3 --keys 80
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lockstep  # noqa: E402  (sets up pygame with the dummy video driver)
from lockstep import pygame, deluxe, deluxe_rules, DeluxeSlots, setup, state, pick_key, diff, MOVES  # noqa: E402

from deluxe import view3d  # noqa: E402

K = pygame


class Single:
    """lockstep's setup() with one game."""

    def __init__(self, g):
        self.c = self.d = self.g = g

    def both(self, fn):
        fn(self.g)

    def key(self, k):
        press(self.g, k)


def press(g, k):
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=''))


def play(seed: int, keys: int, three_d: bool, timings: list):
    deluxe_rules.srand(seed)
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.slots = DeluxeSlots(tempfile.mkdtemp())
    g.view3d = three_d
    rnd = random.Random(seed)
    how = setup(Single(g), rnd)
    states, names = [state(g)], []
    for i in range(keys):
        if not g.running:
            break
        k = pick_key(rnd)
        names.append(pygame.key.name(k))
        if three_d and g.overlay is None and k in MOVES:
            want = deluxe.FACES[deluxe.DIRS[k]]
            while g.facing != want:
                press(g, K.K_RIGHT if (want - g.facing) % 4 != 3 else K.K_LEFT)
            press(g, K.K_UP)
        else:
            press(g, k)
        states.append(state(g))
        if three_d and i % 7 == 0:
            t = time.perf_counter()
            g.renderer.draw(g, present=False)
            timings.append(time.perf_counter() - t)
    return how, states, names


def same_games(runs: int, keys: int) -> int:
    bad, timings = 0, []
    for run in range(runs):
        seed = 5000 + run
        how, flat, names = play(seed, keys, False, [])
        _, deep, _ = play(seed, keys, True, timings)
        for i, (a, b) in enumerate(zip(flat, deep)):
            why = diff(a, b)
            if why:
                bad += 1
                print(f'run {run} (seed {seed}, {how}): FPS mode differs after {i} keys')
                print(f'   last keys: {" ".join(names[max(0, i - 15):i])}')
                print(f'   {why.replace("classic", "flat").replace("deluxe ", "3D     ")}')
                break
        else:
            if len(flat) != len(deep):
                bad += 1
                print(f'run {run}: the games ended at different keys')
    timings.sort()
    print(f'{runs - bad} of {runs} runs play the same in FPS mode ({keys} keys each); '
          f'{len(timings)} views drawn, median {timings[len(timings) // 2] * 1000:.0f} ms, '
          f'slowest {timings[-1] * 1000:.0f} ms')
    assert timings[len(timings) // 2] < 0.06, 'the 3D view is too slow to glide'
    return bad


def looks():
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 4, (45, 86))
    g.view3d = True
    g.renderer.draw(g, present=False)
    sc = g.renderer.scene3d(g)
    assert sc.look('wall', 4) == 'block' and sc.look('wall', -1) == 'block'      # building walls, doors
    assert sc.look('wall', 1) == 'billboard' and sc.look('wall', 5) == 'billboard'    # pines, boulders
    assert sc.look('wall', 2) == 'flat' and sc.look('deco', 5) == 'flat'          # water, blood
    assert sc.look('deco', 1) == 'billboard'                                      # an opened door
    assert sc.look('item', 1000) == 'flat' and sc.look('item', 4) == 'small'      # stairs, a potion
    assert sc.roof(6) == 10 and sc.roof(1) == 0                                   # carpet indoors, grass outside
    # facing the shop door from two squares away: the door is in the middle of the view
    g.facing = 0
    frame = g.renderer.v3d.render(sc, (45.5, 86.5, view3d.facing_angle(0)))
    door = sc.picture('wall', -1)
    mid = frame.get_at((100, 100))[:3]
    assert tuple(mid) in {tuple(door.get_at((x, y))[:3]) for x in range(40) for y in range(40)}, mid
    # turning is free: no turn passes, nothing moves, the messages stay
    g.messages = [deluxe.Msg('hello')]
    before = lockstep.state(g)
    press(g, K.K_LEFT)
    assert g.facing == 3 and lockstep.state(g) == before
    press(g, K.K_e)                                                               # step sideways: north
    assert (g.player.X, g.player.Y) == (45, 85), (g.player.X, g.player.Y)
    print('the Quest I looks, the view, free turns and side steps: ok')


def fight():
    """An animation at a creature's square shows at that creature in the 3D view."""
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1, (9, 19))
    g.view3d, g.fast = True, False
    r = g.renderer
    shown = []
    r.present = lambda surface=None: shown.append(surface)
    for _ in range(3):
        press(g, K.K_UP)
    composed = [s for s in shown if s is not None]
    assert composed, 'no animation frames were composed'
    # the frames differ inside the view (the hits), and the view is not the map from above
    views = {pygame.image.tobytes(s.subsurface((0, 0, 400, 400)), 'RGB') for s in composed}
    assert len(views) > 1
    print(f'a fight in FPS mode: {len(composed)} animation frames carried into the view: ok')


def real_time():
    """With the steps gliding and the animations timed (not a scripted run): facing each way, a step
    ends its glide and the turn goes on (facing west once never arrived: +pi against -pi), and an
    animation with no level loaded (the title) doesn't reach for the 3D view."""
    import signal

    def stuck(*a):
        raise AssertionError('a key took over 10 seconds: FPS mode hangs')
    signal.signal(signal.SIGALRM, stuck)
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1, (10, 10))
    g.view3d, g.fast = True, False
    g.speaker.enabled = False
    g.renderer.draw(g, present=False)
    for k in [K.K_LEFT, K.K_UP, K.K_LEFT, K.K_UP, K.K_LEFT, K.K_UP, K.K_LEFT, K.K_UP, K.K_RIGHT, K.K_DOWN]:
        signal.alarm(10)
        press(g, k)
        g.renderer.draw(g, present=False)
        signal.alarm(0)
    g.world.grid = []                                 # back at the title: no level
    signal.alarm(10)
    g.tones((400, 50))
    g.renderer.draw(g, present=False)
    signal.alarm(0)
    print('in real time: steps and turns every way, and no level loaded: ok')


def status_frame(shot=None):
    from deluxe.render import EGA
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1)
    r = g.renderer

    def colours(box):
        x0, y0, x1, y1 = box
        return {tuple(r.screen.get_at((x, y))[:3]) for x in range(x0, x1) for y in range(y0, y1)}
    g.view3d = True
    r.draw(g, present=False)
    assert EGA[6][:3] in colours((2, 2, 4, 84))                   # the frame
    assert EGA[15][:3] in colours((4, 4, 84, 84))                 # the eyes: white
    before = r.screen.subsurface((2, 89, 100, 30)).copy()
    g.player.hero.poisoned = 1
    g.status.killer = 1
    g.status.Shield = 3
    r.draw(g, present=False)
    assert EGA[10][:3] in colours((4, 4, 84, 84))                 # poisoned eyes are green
    assert EGA[14][:3] in colours((4, 4, 84, 84))                 # the Shield's yellow ring
    for n, (word, c) in enumerate((('Poisoned', 10), ('Killer', 12), ('Shield', 14))):
        y = 89 + 10 * n                                           # each on its own black strip
        assert colours((2, y, 2 + 8 * len(word) + 4, y + 10)) == {(0, 0, 0), EGA[c][:3]}, word
    assert pygame.image.tobytes(before, 'RGB') != pygame.image.tobytes(r.screen.subsurface((2, 89, 100, 30)), 'RGB')
    if shot:
        pygame.image.save(r.screen, shot)
    g.view3d = False                                              # from above the hero shows it himself
    r.draw(g, present=False)
    assert EGA[6][:3] not in colours((2, 2, 4, 84))
    print('the status frame: the portrait and the states in words, in FPS mode only: ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=12)
    ap.add_argument('--keys', type=int, default=200)
    a = ap.parse_args()
    looks()
    fight()
    real_time()
    status_frame()
    bad = same_games(a.runs, a.keys)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
