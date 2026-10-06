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
    ap.add_argument('--check', action='store_true', help='try each thing the comparison needs on this computer and say what works')
    ap.add_argument('--replay', help='a recording (a zip from compare zips) to run again and check')
    return ap.parse_args(argv)


def put_beside(comp, our_x=40, our_y=40, width=640):
    """Lock the original's window into the right half of ours, so they are one window (True). If the system will not do that, put it beside ours (False)."""
    if comp.dos.window is None:
        return False
    import pygame
    if comp.dos.embed(pygame.display.get_wm_info().get('window'), width, 0):
        return True
    if sys.platform.startswith('win'):
        from . import dos
        dos._api()[0].SetWindowPos(comp.dos.window, None, our_x + width + 40, our_y, 0, 0, 0x0001 | 0x0004)       # SWP_NOSIZE | SWP_NOZORDER
    else:
        comp.dos._x('windowmove', comp.dos.window, str(our_x + width + 40), str(our_y))
    return False


def status(font, surface, text, colour, y=480, h=28):
    import pygame
    pygame.draw.rect(surface, (20, 24, 32), (0, y, surface.get_width(), h))
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
    """Run it; whatever goes wrong is written down (the Studio shows it) and shown in a window, never left silent."""
    try:
        return run(argv)
    except SystemExit:
        raise
    except BaseException as e:                                     # noqa: BLE001
        import traceback
        text = traceback.format_exc()
        print(text, file=sys.stderr, flush=True)
        try:
            import tkinter
            from tkinter import messagebox
            root = tkinter.Tk()
            root.withdraw()
            messagebox.showerror('Compare to DOS', f'The comparison stopped: {e}\n\nThe details are in {os.path.join(os.path.expanduser("~"), ".quest_compare_log.txt")}')
            root.destroy()
        except Exception:                                          # noqa: BLE001
            pass
        return 1


def play_alone(comp, font, screen, why):
    """Our game on its own (the original could not be started): the window says why, and the game can still be played."""
    import pygame
    print('compare:', why, flush=True)
    status(font, screen, why, (250, 120, 110))
    clock = pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return 1
            if ev.type == pygame.KEYDOWN:
                comp.game.handle(ev)
        comp.draw()
        pygame.display.flip()
        clock.tick(30)


def run(argv=None):
    a = parse(argv)
    if a.check:
        from . import check
        return 0 if check.run() else 1
    if a.pack:
        os.environ['QUEST_PACK'] = a.pack                  # before the engine is loaded
    os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '40,40')
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((1280, 480 + 28))                # ours on the left, the original's window locked into the right half
    pygame.display.set_caption('The Quest Deluxe (left) and the original in DOSBox (right) - compare to DOS: type here')
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
    beside = [False]                                                   # its picture could not be copied in: DOSBox is shown beside ours instead
    docked = [None]                                                    # None: not tried yet; then whether it could be locked in

    def say(text):
        """What is happening, in the window (which keeps answering Windows while it waits) and in the log."""
        print('compare:', text, flush=True)
        status(font, screen, text, (230, 230, 230))
        pygame.event.pump()
        pygame.display.flip()

    def dock():
        """Lock DOSBox's window into the right half of ours (again whenever DOSBox has made a new one)."""
        if comp.dos.window is None:
            return
        if docked[0] is None:
            docked[0] = put_beside(comp)
            print('compare: the original\'s window is', 'locked into ours' if docked[0] else 'shown in the right half (it could not be locked in)', flush=True)
        elif docked[0] and comp.dos.keep_embedded(640, 0):
            print('compare: DOSBox made a new window; locked it in again', flush=True)
        elif docked[0] is False and sys.platform.startswith('win') and not beside[0]:
            comp.dos.tuck_behind(pygame.display.get_wm_info().get('window'))      # (its picture is shown in the right half instead)
        pygame.event.pump()

    comp.progress, comp.after_dos_window = say, dock
    try:
        import signal
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))              # asked to stop: leave by the normal way, which closes DOSBox
    except (ValueError, OSError):
        pass
    comp.dos.idle = pygame.event.pump
    ours = screen.subsurface((0, 0, 640, 480))
    try:
        if sys.platform.startswith('win'):
            try:
                from . import dos
                dos.bring_to_front(pygame.display.get_wm_info().get('window'))
            except Exception as e:                                        # noqa: BLE001
                print('compare: could not bring the window to the front:', e, flush=True)
        say('Starting The Quest Deluxe ...')
        comp.begin_ours(ours, hero)                                   # our game first: it is on the screen while the original loads
        comp.draw()
        pygame.display.flip()
        solo = None
        try:
            comp.start_dos()
            dock()
            comp.finish_ours()
        except Exception as e:                                        # noqa: BLE001 - the original could not be started: ours still plays
            import traceback
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            solo = f'The original could not be started ({type(e).__name__}: {e}). Press "Check it works" in the Studio. Ours plays alone.'
        comp.draw()
        pygame.display.flip()
        if solo:
            return play_alone(comp, font, screen, solo)
        msg, colour = 'Same keys go to both. Everything is recorded; F12 saves it.', (150, 220, 150)
        if comp.removed:
            msg, colour = comp.removed[:90], (240, 190, 90)
        if not comp.seed_ok:
            msg, colour = 'The dice cannot be matched (the original is laid out differently in memory).', (240, 190, 90)
        status(font, screen, msg, colour)
        print('compare: ready', flush=True)
        if sys.platform.startswith('win'):
            try:
                from . import dos
                dos.bring_to_front(pygame.display.get_wm_info().get('window'))      # (a window started by another program is often left behind it)
            except Exception as e:                                        # noqa: BLE001
                print('compare: could not bring the window to the front:', e, flush=True)
        clock = pygame.time.Clock()
        last_dock = last_mirror = 0.0
        mirror_since = time.time()
        copied = [False]
        while True:
            if time.time() - last_dock > 0.5:
                last_dock = time.time()
                if comp.dos.proc is not None and not comp.dos.alive():
                    return play_alone(comp, font, screen, 'The original has closed. Ours plays on alone; start the comparison again to compare.')
                dock()
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
                if ev.key == pygame.K_F11:                                      # bring the original's window into view, beside this one (Windows)
                    beside[0] = True
                    shown = comp.dos.show_beside(pygame.display.get_wm_info().get('window'))
                    status(font, screen, 'The original is in its own window beside this one.' if shown else 'F11 puts the original beside this window (Windows only).', (240, 190, 90))
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
            if docked[0] is False and not beside[0] and time.time() - last_mirror > 0.15:
                last_mirror = time.time()
                shot = comp.dos.picture_surface()
                if shot is not None:
                    screen.blit(shot, (640, 0))
                    if not copied[0]:
                        copied[0] = True
                        print('compare: the original\'s picture is being copied into the right half', flush=True)
                elif time.time() - mirror_since > 4:
                    beside[0] = True
                    shown = comp.dos.show_beside(pygame.display.get_wm_info().get('window'))
                    print('compare: the original\'s picture could not be copied; DOSBox is shown beside this window:', shown, flush=True)
                    status(font, screen, 'The original is in its own window beside this one (its picture could not be copied in).', (240, 190, 90))
            pygame.display.flip()
            clock.tick(30)
    finally:
        comp.close()
        pygame.quit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
