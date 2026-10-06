"""Compare to The Quest DOS: the pieces on their own, and (when DOSBox, xdotool and ImageMagick are installed and there is a display)
the real thing: our game and the original in DOSBox, started from one save and given the same keys, must roll the same dice and
draw the same pictures.

Run:  xvfb-run -a python tests/test_compare.py
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DISPLAY_ENV = {k: v for k, v in os.environ.items() if k != 'SDL_VIDEODRIVER'}
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.pop('QUEST_PACK', None)

from compare import dos, keys, session, state  # noqa: E402


def pieces():
    # the original is as it was found, and a comparison never writes to it
    assert dos.manifest_ok() == [], dos.manifest_ok()
    assert os.path.isfile(os.path.join(dos.ORIGINAL, 'TheQuest.exe'))
    # Borland's random numbers: the step, and counting steps
    assert dos.lcg(1) == (22695477 + 1) & 0xFFFFFFFF
    s = 12345
    t = s
    for _ in range(7):
        t = dos.lcg(t)
    assert session.count_draws(s, t) == 7 and session.count_draws(s, s) == 0 and session.count_draws(s, s ^ 1, limit=50) is None
    # keys both ways
    import pygame
    for name in ('Up', 'Return', 'space', 'Escape', 'F3', 'c', '6'):
        k, _ = keys.to_pygame(name)
        assert keys.from_pygame(k) == name, name
    assert not keys.sendable('f') and not keys.sendable(None) and keys.sendable('Up')
    del pygame
    # the save the original loads is the one our engine reads back
    import pygame
    pygame.init()
    window = pygame.display.set_mode((640, 480))
    from engine import savefile
    from engine.game import Game
    g = Game(window, settings={'fixes': 'off', 'sound': 'off'})
    state.start(g, 2, (10, 10), cls=2)
    assert (g.player.X, g.player.Y) == (10, 10) and g.world.level == 2 and g.player.hero.type == 2
    raw = state.save_bytes(g)
    d = savefile.from_bytes(raw)
    assert (d.X, d.Y) == (10, 10) and d.hero['type'] == 2 and d.st['level'] == 2
    assert savefile.to_bytes(d) == raw, 'the save does not survive a read and a write'
    state.start(g, 1, (22, 10), hero=d)
    assert g.world.level == 1 and (g.player.X, g.player.Y) == (22, 10) and g.player.hero.type == 2
    print('compare: the pieces (original untouched, dice, keys, the save both read): ok')


def can_run_for_real():
    if dos.find_dosbox() is None or not (shutil.which('xdotool') and shutil.which('import')) or not os.environ.get('DISPLAY'):
        return False
    return not dos.WINDOWS


def side_by_side(level, at, keys_to_press, label):
    import pygame
    pygame.init()
    window = pygame.display.set_mode((640, 480))
    c = session.Compare(level, at, dos_env=DISPLAY_ENV)
    try:
        c.start_dos()
        assert c.seed_ok, 'could not find the original\'s dice in DOSBox memory'
        c.start_ours(window, None)
        c.draw()
        assert c.pixel_difference() == 0, 'the two do not start on the same picture'
        total = 0
        for name in keys_to_press:
            k, u = keys.to_pygame(name)
            r = c.press(name, k, u)
            total += r.dos_draws or 0
            assert r.same, (label, name, r.notes, c.mark(os.path.join(ROOT, 'compare reports'), 'a test saw a difference'))
        return total
    finally:
        c.close()


def for_real():
    # the walk toward two imps and a fight: the dice must be rolled the same number of times every key, and the pictures equal
    seq = ['Right'] * 3 + ['Up'] * 7 + ['Right'] * 3 + ['space', 'Return', 'Left', 'Left', 'Up', 'Return']
    rolled = side_by_side(1, (22, 10), seq, 'level 1, imps')
    assert rolled > 10, f'the test saw only {rolled} dice rolls, so it did not test them'
    # the same on another level, with the hero somewhere else
    side_by_side(2, (10, 10), ['Right', 'Down', 'Down', 'Left', 'Up', 'Right', 'Right'], 'level 2')
    assert dos.manifest_ok() == []
    print(f'compare: our game and the original in DOSBox, same save, same keys: {rolled} dice rolls and every picture alike: ok')


if __name__ == '__main__':
    pieces()
    if can_run_for_real():
        for_real()
    else:
        print('compare: the side-by-side run was skipped (it needs DOSBox, xdotool, ImageMagick and a display)')
    print('all compare checks passed')
