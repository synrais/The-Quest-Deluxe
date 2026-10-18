"""The picture fills the window when the window is made bigger (engine.render.Renderer.fitted): a whole multiple of 640 x 480 is whole pixels, in between it is
enlarged and fitted so it stays sharp, a smaller window shrinks it, the shape is kept; settings.ini fit_window = off keeps the old whole multiples.

Run:  SDL_VIDEODRIVER=dummy python tests/test_window.py
"""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame                                                               # noqa: E402
pygame.init()
pygame.display.set_mode((640, 480))
from engine.render import Renderer, W, H                                    # noqa: E402

src = pygame.Surface((W, H))                                                # a picture of one-pixel stripes: every pixel counts
for x in range(W):
    for y in range(H):
        src.set_at((x, y), (255, 255, 255) if (x + y) % 2 else (0, 0, 0))


def size(ww, wh, fit=True, smooth=False):
    return Renderer.fitted(SimpleNamespace(fit=fit, smooth=smooth), src, ww, wh).get_size()


# fills the window as far as its shape allows, never bigger than it, the shape kept
for ww, wh, want in ((1280, 960, (1280, 960)), (640, 480, (640, 480)), (1920, 1080, (1440, 1080)), (1000, 700, (933, 700)),
                     (2000, 480, (640, 480)), (500, 400, (500, 375)), (1920, 1440, (1920, 1440)), (3840, 2160, (2880, 2160)), (1366, 768, (1024, 768))):
    got = size(ww, wh)
    assert got == want, (ww, wh, got, want)
    assert got[0] <= ww and got[1] <= wh and abs(got[0] / got[1] - 4 / 3) < 0.01, (ww, wh, got)
# a window that is not quite big enough for the next whole multiple used to leave the picture small: it grows now
assert size(1000, 700) != (640, 480) and size(1279, 959)[0] >= 1278
# whole multiples are whole pixels: every source pixel is a block of one colour
for n in (1, 2, 3):
    out = Renderer.fitted(SimpleNamespace(fit=True, smooth=False), src, W * n, H * n)
    assert out.get_size() == (W * n, H * n)
    for x, y in ((0, 0), (1, 0), (7, 3), (W - 1, H - 1), (100, 101)):
        want = tuple(src.get_at((x, y)))[:3]
        assert all(tuple(out.get_at((x * n + dx, y * n + dy)))[:3] == want for dx in range(n) for dy in range(n)), (n, x, y)
# in between it stays sharp: the stripes are still there (a plain blend would give grey)
out = Renderer.fitted(SimpleNamespace(fit=True, smooth=False), src, 1000, 750)
vals = [tuple(out.get_at((x, 300)))[0] for x in range(100, 140)]
assert max(vals) - min(vals) > 120, 'still black and white, not a flat grey'
# the old way (fit_window = off): whole multiples only; smooth_scaling = on fills it blended
assert size(1000, 700, fit=False) == (640, 480) and size(1280, 960, fit=False) == (1280, 960) and size(1919, 1439, fit=False) == (1280, 960)
assert size(500, 400, fit=False) == (500, 375)
assert size(1000, 700, smooth=True) == (933, 700)

# the game itself: a window of any size is filled, and shown
from engine.game import Game                                                # noqa: E402
for ww, wh in ((1000, 700), (1920, 1080), (700, 500)):
    window = pygame.Surface((ww, wh))
    g = Game(window, settings={'fixes': 'off', 'sound': 'off'})
    assert g.renderer.fit is True
    g.renderer.draw(g, present=False)
    g.renderer.present()
    box = g.renderer.fitted(g.renderer.screen, ww, wh)
    left, top = (ww - box.get_width()) // 2, (wh - box.get_height()) // 2
    assert (left == 0 or top == 0) and 2 * left + box.get_width() in (ww, ww - 1), (ww, wh, left, top)
    assert tuple(window.get_at((left + box.get_width() // 2, top + box.get_height() // 2))) == tuple(box.get_at((box.get_width() // 2, box.get_height() // 2))), 'on the window'
g = Game(pygame.Surface((1000, 700)), settings={'fixes': 'off', 'sound': 'off', 'fit_window': 'off'})
assert g.renderer.fit is False
print('window: the picture fills the window at any size, whole pixels at whole multiples and sharp in between; fit_window = off keeps whole multiples: ok')
