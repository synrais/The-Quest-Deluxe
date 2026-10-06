"""Compare to The Quest DOS, the window: our game with the original beside it, one keyboard for both.

    python run_compare.py --level 3 --at 45,60 [--pack PACK] [--hero-file SAVE | --class 1] [--fixes on|off]

Press keys in OUR window (the one that says "The Quest Deluxe"): each goes to both games. F12 saves a bug report of what both show now
(the two pictures and the differences side by side, and every key so far) in the 'compare reports' folder. Esc twice does what Esc does
in the game; to leave the comparison close this window.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--at', default='5,5')
    ap.add_argument('--pack')
    ap.add_argument('--hero-file')
    ap.add_argument('--class', dest='cls', type=int, default=1)
    ap.add_argument('--fixes', choices=('on', 'off'), default='off')
    ap.add_argument('--reports', default=os.path.join(ROOT, 'compare reports'))
    return ap.parse_args(argv)


def put_beside(comp, our_x=40, our_y=40, width=640):
    """Move the original's window to the right of ours."""
    if comp.dos.window is None:
        return
    if sys.platform.startswith('win'):
        import ctypes
        ctypes.windll.user32.SetWindowPos(comp.dos.window, 0, our_x + width + 40, our_y, 0, 0, 0x0001 | 0x0004)
    else:
        comp.dos._x('windowmove', comp.dos.window, str(our_x + width + 40), str(our_y))


def status(font, surface, text, colour, y=480, h=28):
    import pygame
    pygame.draw.rect(surface, (20, 24, 32), (0, y, 640, h))
    surface.blit(font.render(text[:90], True, colour), (8, y + 6))


def main(argv=None):
    a = parse(argv)
    if a.pack:
        os.environ['QUEST_PACK'] = a.pack                  # before the engine is loaded
    os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '40,40')
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((640, 480 + 28))
    pygame.display.set_caption('The Quest Deluxe - compare to DOS (type here)')
    font = pygame.font.SysFont('dejavusans,arial', 14)
    status(font, screen, 'Starting the original in DOSBox ...', (230, 230, 230))
    pygame.display.flip()
    from . import keys
    from .session import Compare
    at = tuple(int(v) for v in a.at.split(','))
    hero = None
    if a.hero_file:
        from engine import savefile
        with open(a.hero_file, 'rb') as fh:
            hero = savefile.from_bytes(fh.read())
    comp = Compare(a.level, at, pack_root=a.pack, hero_file=a.hero_file, cls=a.cls, fixes=a.fixes)
    try:
        comp.start_dos()
        put_beside(comp)
        comp.start_ours(screen.subsurface((0, 0, 640, 480)), hero)
        comp.draw()
        pygame.display.flip()
        msg, colour = 'Same keys go to both. F12 saves a bug report.', (150, 220, 150)
        if not comp.seed_ok:
            msg, colour = 'The dice cannot be matched (the original is laid out differently in memory).', (240, 190, 90)
        status(font, screen, msg, colour)
        clock = pygame.time.Clock()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return 0
                if ev.type != pygame.KEYDOWN:
                    continue
                if ev.key == pygame.K_F12:
                    path = comp.mark(a.reports, 'saved by F12')
                    status(font, screen, f'Saved {os.path.basename(path)}', (150, 200, 250))
                    continue
                name = keys.from_pygame(ev.key)
                if not keys.sendable(name):
                    continue
                status(font, screen, f'{name} ...', (230, 230, 230))
                pygame.display.flip()
                k, u = keys.to_pygame(name)
                r = comp.press(name, k, u)
                if r.same:
                    status(font, screen, f'{name}: both the same (dice {r.dos_draws}, pictures equal)', (150, 220, 150))
                else:
                    status(font, screen, f'{name}: ' + ' '.join(r.notes)[:80] + '  F12 saves it', (250, 120, 110))
            comp.draw()
            pygame.display.flip()
            clock.tick(30)
    finally:
        comp.close()
        pygame.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
