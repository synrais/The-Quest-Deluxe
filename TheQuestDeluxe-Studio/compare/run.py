"""Compare to The Quest DOS, the window: our game with the original beside it, one keyboard for both.

    python run_compare.py --level 3 --at 45,60 [--pack PACK] [--hero-file SAVE | --class 1] [--fixes on|off]

Press keys in OUR window (the one that says "The Quest Deluxe"): each goes to both games. Everything is recorded; F12 asks a few questions and
saves the recording as a zip in Custom Maps/compare zips (Send my edits sends it with the rest). To leave the comparison close this window (it
offers to save a recording that has differences in it).
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
    ap.add_argument('--same-things', dest='same', choices=('on', 'off'), default='on')
    ap.add_argument('--hero-label', default='')
    ap.add_argument('--loadout', help='a JSON file: the gear both heroes start in (compare/loadout.py)')
    ap.add_argument('--replay', help='a recording (a zip from compare zips) to run again and check')
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


def message(font, screen, comp, text, colour):
    status(font, screen, text, colour)


def save_recording(comp, font, screen, a):
    import pygame
    from . import form
    r = comp.recorder
    summary = f'{len(r.steps)} keys pressed, {len(r.differences)} left the two different. Level {comp.level}.'
    answers = form.ask(summary)
    if answers is None:
        return None
    path = comp.save_recording(answers)
    status(font, screen, f'Saved {os.path.basename(path)}', (150, 200, 250))
    pygame.display.flip()
    try:
        from . import sending
        status(font, screen, sending.offer(path).split('\n')[0], (150, 200, 250))
    except Exception as e:                                         # noqa: BLE001 - sending is a courtesy; the zip is saved
        status(font, screen, f'Saved; not sent ({e})', (250, 200, 100))
    return path


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
    if a.replay:
        from . import replay
        bad, comp = replay.replay(a.replay, screen.subsurface((0, 0, 640, 480)))
        if bad:
            print(f'NOT THE SAME: {len(bad)} keys came out differently, the first is key {bad[0][0]} ({bad[0][1]}): {bad[0][2]}')
            return 1
        print('THE SAME: every key rolled the same dice and drew the same pictures as recorded.')
        return 0
    from . import keys
    from .session import Compare
    at = tuple(int(v) for v in a.at.split(','))
    hero = None
    if a.hero_file:
        from engine import savefile
        with open(a.hero_file, 'rb') as fh:
            hero = savefile.from_bytes(fh.read())
    gear = None
    if a.loadout:
        import json
        with open(a.loadout, encoding='utf-8') as fh:
            gear = json.load(fh)
    comp = Compare(a.level, at, pack_root=a.pack, hero_file=a.hero_file, cls=a.cls, fixes=a.fixes, same_things=a.same == 'on',
                   hero_label=a.hero_label, loadout=gear)
    try:
        comp.start_dos()
        put_beside(comp)
        comp.start_ours(screen.subsurface((0, 0, 640, 480)), hero)
        comp.draw()
        pygame.display.flip()
        msg, colour = 'Same keys go to both. Everything is recorded; F12 saves it.', (150, 220, 150)
        if comp.removed:
            msg, colour = comp.removed[:90], (240, 190, 90)
        if not comp.seed_ok:
            msg, colour = 'The dice cannot be matched (the original is laid out differently in memory).', (240, 190, 90)
        status(font, screen, msg, colour)
        clock = pygame.time.Clock()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    if comp.recorder and comp.recorder.unsaved:
                        status(font, screen, 'There are differences in the recording: save it?', (250, 200, 100))
                        pygame.display.flip()
                        try:
                            from tkinter import messagebox
                            import tkinter
                            root = tkinter.Tk()
                            root.withdraw()
                            ans = messagebox.askyesnocancel('Compare to DOS', 'The recording has differences in it. Save it before closing?', parent=root)
                            root.destroy()
                        except Exception:                                  # noqa: BLE001
                            ans = False
                        if ans is None:
                            continue
                        if ans:
                            save_recording(comp, font, screen, a)
                    return 0
                if ev.type != pygame.KEYDOWN:
                    continue
                if ev.key == pygame.K_F12:
                    save_recording(comp, font, screen, a)
                    continue
                name = keys.from_pygame(ev.key)
                if not keys.sendable(name):
                    continue
                status(font, screen, f'{name} ...', (230, 230, 230))
                pygame.display.flip()
                k, u = keys.to_pygame(name)
                r = comp.press(name, k, u)
                n = len(comp.recorder.differences)
                if r.same:
                    status(font, screen, f'{name}: same (dice {r.dos_draws}, pictures equal)   {n} differences so far', (150, 220, 150))
                else:
                    status(font, screen, f'{name}: ' + ' '.join(r.notes)[:70] + '  F12 saves', (250, 120, 110))
            comp.draw()
            pygame.display.flip()
            clock.tick(30)
    finally:
        comp.close()
        pygame.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
