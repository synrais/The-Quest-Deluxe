"""FPS mode (Deluxe): a view, not a different game.

1. The same random games played from above and in FPS mode (turning to face the way, then walking
   forward) must reach the same state after every key: hero, inventory, map, creatures, messages.
2. The 3D view draws everywhere those games go, fast enough to glide (under 60 ms a frame here).
3. The Quest I pack's looks: building walls are blocks, trees billboards, water and blood flat,
   carpeted rooms have roofs; an animation's hit lands on the creature in view.
4. The panel's Map box shows the screen from above in FPS mode (M: the level map), and only then.

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


def map_box():
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1)
    r = g.renderer
    box = (480, 276, 100, 100)

    def shown():
        r.draw(g, present=False)
        return pygame.image.tobytes(r.screen.subsurface(box), 'RGB')
    level_map = shown()                                           # from above: the original's level map
    g.view3d = True
    screen = shown()
    assert screen != level_map                                     # FPS mode: this screen from above
    view = r.screen.subsurface((300, 0, 100, 100))
    assert pygame.image.tobytes(view, 'RGB') != screen             # and no longer over the view's corner
    press(g, K.K_m)
    assert shown() == level_map                                    # M: the level map
    press(g, K.K_m)
    assert shown() == screen
    g.view3d = False
    assert shown() == level_map
    print("the Map box: this screen from above in FPS mode, M for the level map, the original's from above: ok")


def weapon_in_view():
    from deluxe.hands import attack_kind, cut_out, ATTACK_MS
    from deluxe.render import EGA
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1)
    g.view3d = True
    r = g.renderer
    corner = (200, 150, 200, 250)                                # the bottom right of the view

    def colours():
        r.draw(g, present=False)
        s = r.screen.subsurface(corner)
        return {tuple(s.get_at((x, y))[:3]) for x in range(0, 200, 2) for y in range(0, 250, 2)}
    g.player.bag[(12, 4)] = 211                                  # a Long Sword: white blade, blue hilt
    held = colours()
    assert EGA[15][:3] in held and EGA[1][:3] in held, 'the sword'
    pic = cut_out(r.sprites.bag[211])
    assert not any(tuple(pic.get_at((x, y))) == (84, 84, 84, 255)
                   for x in range(pic.get_width()) for y in range(pic.get_height())), "the cell's grey stays"
    del g.player.bag[(12, 4)]
    assert EGA[15][:3] not in colours() and EGA[1][:3] not in colours()   # nothing in hand: nothing
    g.view3d = False
    assert EGA[1][:3] not in colours()                           # from above: no hand
    # the kinds of attack, and how the hand moves
    pk = g.pack
    assert (attack_kind(pk.item(211)), attack_kind(pk.item(206)), attack_kind(pk.item(231))) == \
        ('swing', 'thrust', 'shoot')
    assert cut_out(r.sprites.bag[233]).get_width() >= 28 and pk.item(233).get('fps_turn') == 90
    hands = r.hands
    now = 10000
    g.swing = ('swing', now - ATTACK_MS['swing'] // 2)
    dx, dy, da = hands.pose(g, now)
    assert dx < -100 and da < -40                                # mid-swing: across to the left
    g.swing = ('thrust', now - ATTACK_MS['thrust'] // 2)
    dx, dy, da = hands.pose(g, now)
    assert dy < -60 and da == 0                                  # mid-thrust: forward
    g.swing = ('swing', now - 5000)
    assert hands.pose(g, now)[:2] == (0, 0) or r._cam            # long over: back at rest
    g.swing = None
    print('the weapon in view: the sword in hand, nothing without, swings, thrusts and shots: ok')



def face():
    from deluxe.face import AT, SCALE, eye_colour
    from deluxe.render import EGA
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1)
    r, h, st, p = g.renderer, g.player.hero, g.status, g.player
    half = 11 * SCALE // 2 + 1
    area = (AT[0] - half, AT[1] - half, 2 * half, 2 * half)

    def colours():
        r.draw(g, present=False)
        s = r.screen.subsurface(area)
        return {tuple(s.get_at((x, y))[:3]) for x in range(area[2]) for y in range(area[3])}
    assert colours() <= {(0, 0, 0)}                               # from above: no bust
    g.view3d = True
    seen = colours()
    assert {EGA[5][:3], EGA[15][:3]} <= seen and EGA[4][:3] not in seen    # the Knight's hood, white eyes
    assert area[1] > 172 and area[1] + area[3] < 214 and area[0] > 550      # below the gold, above the key
    p.bag[(14, 6)] = 504                                          # the Evergreen Amulet: a green necklace
    assert EGA[2][:3] in colours()
    p.bag[(14, 6)] = 511                                          # the Pearl Necklace: white
    assert r.face.amulet_colour(511) == 15
    h.type = 2                                                    # a Mage: the hood in the Mage's colour
    assert EGA[g.pack.classes[2]['look']['colour']][:3] in colours()
    st.killer = 1
    assert eye_colour(h, st) == 4 and EGA[4][:3] in colours()
    h.poisoned = 1
    assert eye_colour(h, st) == 10                                # poison first, as guy2()
    h.invisible = 5
    assert colours() == {(0, 0, 0), EGA[4][:3]}                   # only the (killer-red) eyes
    print("the bust: in FPS mode only, the class's hood, the amulet's necklace, guy2()'s eyes, invisible: ok")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=12)
    ap.add_argument('--keys', type=int, default=200)
    a = ap.parse_args()
    looks()
    fight()
    real_time()
    map_box()
    weapon_in_view()
    face()
    bad = same_games(a.runs, a.keys)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
