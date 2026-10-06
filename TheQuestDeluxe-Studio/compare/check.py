"""Does the comparison work on this computer?   python run_compare.py --check

Starts the original in DOSBox the way a comparison does and tries each thing it needs, one at a time, saying what worked and, when something
did not, what to do about it: DOSBox found and running, its window found, its picture taken, keys reaching it, its memory read (for the dice).
The report is plain text, to be sent back as it is."""
from __future__ import annotations

import os
import platform
import sys
import tempfile
import time


def run(say=print, env=None) -> bool:
    for name in ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER'):
        if env is None and os.environ.get(name) == 'dummy':
            del os.environ[name]                           # (started from the Studio, which runs with the dummy driver: the check needs a real window)
    results = []

    def step(name, ok, detail=''):
        results.append(ok)
        say(f'{"OK  " if ok else "FAIL"}  {name}' + (f': {detail}' if detail else ''))
        return ok

    def info(name, detail):
        say(f'      {name}: {detail}')

    from . import dos, session
    say(f'Compare check, {time.strftime("%Y-%m-%d %H:%M")}')
    info('computer', f'{platform.platform()}, Python {sys.version.split()[0]}')
    try:
        import pygame
        info('pygame', pygame.version.ver)
    except ImportError:
        return step('pygame is installed', False, 'it is not: the Studio could not run either')
    info('running as', 'an administrator' if _admin() else 'an ordinary user (that is fine: nothing here needs more)')
    exe = dos.find_dosbox()
    if not step('DOSBox is there', exe is not None, exe or 'not found: it belongs in dos/dosbox (Windows) or install it (apt install dosbox)'):
        return False
    bad = dos.manifest_ok()
    if not step('the original game files are as they were', not bad, ', '.join(bad[:3])):
        return False
    d = dos.Dos(env=env)
    try:
        game = d.prepare()
        step('a scratch copy of the game can be made', os.path.isdir(game), tempfile.gettempdir())
    except OSError as e:
        step('a scratch copy of the game can be made', False, f'{e} (is the temporary folder writable, or blocked by a security program?)')
        return False
    try:
        t = time.time()
        problem, removed = session.make_dos_save(os.path.join(game, 'data'), 1, (22, 10))
        if not step('the save for the original can be made', problem is None, problem or f'{time.time() - t:.0f}s'):
            return False
        d.start()
        alive = d.alive()
        if not step('DOSBox starts', alive, '' if alive else 'it closed straight away: a security program may have stopped it'):
            return False
        if not step('its window is found', d.window is not None, '' if d.window else 'DOSBox is running but no window of it was found'):
            return False
        d.wait_still(1.2, 20)
        first = d.picture_bytes()
        shot = os.path.join(d.scratch, 'check.png')
        got = d.screenshot(shot)
        dark = True
        if got:
            surf = pygame.image.load(shot)
            dark = max(surf.get_at((x, y))[:3] for x in range(0, surf.get_width(), 7) for y in range(0, surf.get_height(), 7)) == (0, 0, 0)
        step('its picture can be taken', bool(first) and got and not dark,
             '' if (first and got and not dark) else 'the picture could not be taken or is all black (the comparison would run without comparing pixels)')
        for k in ('Down', 'Return', 'Return'):
            d.key_and_wait(k)
        after = d.picture_bytes()
        moved = bool(first) and after != first
        step('keys reach it', moved, (f'input by {"the keyboard (DOSBox brought forward)" if os.environ.get("DOS_INPUT") == "focus" else "posted keys"}' if dos.WINDOWS else '')
             if moved else 'the picture did not change when keys were sent: set DOS_INPUT=focus and try again, or click on DOSBox once')
        try:
            pygame.display.init()
            pygame.display.set_mode((1280, 508))
            locked = d.embed(pygame.display.get_wm_info().get('window'), 640, 0)
            info('locked into the compare window', 'yes' if locked else 'no: the original will be shown as a picture in the right half instead')
            pygame.display.quit()
        except Exception as e:      # noqa: BLE001 - only a note
            info('locked into the compare window', f'could not be tried ({e})')
        ok, last = False, ''
        for _ in range(24):
            try:
                if d.locate_text(session.SEED_MARKER):
                    ok = True
                    break
            except (OSError, RuntimeError, ValueError) as e:
                last = str(e)
                d._mem = None
            time.sleep(0.25)
        step('its memory can be read (so the dice can be matched)', ok,
             '' if ok else 'the comparison would run, but the dice would not match' + (f' ({last})' if last else ''))
        if ok:
            import struct
            seed = struct.unpack('<I', d.read(d.marker_at + session.SEED_DELTA, 4))[0]
            info('the original\'s dice', f'{seed:#010x}')
    except Exception as e:          # noqa: BLE001 - say what happened, whatever it was
        step('no error', False, f'{type(e).__name__}: {e}')
    finally:
        try:
            d.stop()
        except RuntimeError as e:
            step('the original game files are left as they were', False, str(e))
    say('')
    say('EVERYTHING WORKS' if all(results) else 'SOMETHING DID NOT WORK: send these lines on.')
    return all(results)


def _admin() -> bool:
    try:
        if sys.platform.startswith('win'):
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:       # noqa: BLE001
        return False
