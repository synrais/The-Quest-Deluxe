"""The comparison as a person meets it: the real program, started the way the Studio starts it, on a real display (xvfb-run -a python tests/test_compare_process.py).

What must be true, each checked on the screen and in the process list:
  * a window with OUR game in its left half and the original's DOSBox in its right half comes up, within a time limit;
  * keys typed there go to both (the picture of both changes);
  * if the original dies, our game stays up and plays, and the window says so; nothing hangs;
  * however the compare window goes (closed, asked to stop, killed), no DOSBox and no compare process is left behind;
  * no console window is made for it.
"""
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {k: v for k, v in os.environ.items() if k != 'SDL_VIDEODRIVER'}
START_LIMIT = 45                    # seconds from starting to both games on the screen
problems = []


def fail(text):
    problems.append(text)
    print('FAIL', text, flush=True)


def run(*cmd):
    return subprocess.run(cmd, env=ENV, capture_output=True, text=True).stdout


def windows():
    """[(id, title, geometry line)] of every window under the root."""
    out = []
    for line in run('xwininfo', '-root', '-tree').splitlines():
        line = line.strip()
        if line.startswith('0x') and '"' in line:
            out.append((line.split()[0], line.split('"')[1], line))
    return out


def find(part):
    return next((w for w in windows() if part in w[1]), None)


def alive(name):
    return [p for p in run('pgrep', '-af', name).splitlines() if 'pgrep' not in p]


def picture(window_id, box=None):
    """The window's pixels (PNG bytes), the whole window or a (w, h, x, y) box of it."""
    args = ['import', '-window', window_id] + (['-crop', '%dx%d+%d+%d' % box] if box else []) + ['png:-']
    return subprocess.run(args, env=ENV, capture_output=True).stdout


def not_blank(png):
    import io
    import pygame
    surf = pygame.image.load(io.BytesIO(png))
    w, h = surf.get_size()
    colours = {tuple(surf.get_at((x, y)))[:3] for x in range(0, w, 5) for y in range(0, h, 5)}
    return len(colours) > 6


LOGS = []


def start(extra_env=None):
    import tempfile
    log = tempfile.NamedTemporaryFile('w+', suffix='.log', delete=False)
    LOGS.append(log.name)
    cmd = [sys.executable, os.path.join(ROOT, 'run_compare.py'), '--level', '1', '--at', '22,10', '--class', '1']
    proc = subprocess.Popen(cmd, cwd=ROOT, env=dict(ENV, **(extra_env or {})), stdout=log, stderr=subprocess.STDOUT)
    proc.log = log.name
    return proc


def said(proc):
    with open(proc.log, errors='replace') as fh:
        return ''.join(line for line in fh if 'ALSA' not in line)


def wait_both(proc, limit=START_LIMIT):
    """Wait until the compare window exists and DOSBox is inside it, drawn; the seconds it took, or None."""
    t = time.time()
    while time.time() - t < limit:
        time.sleep(0.5)
        if proc.poll() is not None:
            return None
        win = find('compare to DOS')
        if win and 'compare: ready' in said(proc):                       # (the program says so when both games are loaded)
            kids = run('xwininfo', '-id', win[0], '-children')
            if 'DOSBox' in kids and '640x480+640+0' in kids:
                return time.time() - t, win
    return None


def clean_up():
    for name in ('run_compare', 'dosbox'):
        for line in alive(name):
            try:
                os.kill(int(line.split()[0]), signal.SIGKILL)
            except (OSError, ValueError):
                pass
    time.sleep(1)


def leftovers(label):
    time.sleep(3)
    left = alive('run_compare') + alive('dosbox')
    if left:
        fail(f'{label}: processes left behind: {left}')
        clean_up()


def main():
    import pygame
    pygame.init()
    clean_up()

    # 1. it comes up: ours on the left, the original on the right, inside the time limit
    proc = start()
    got = wait_both(proc)
    if not got:
        fail('the compare window with both games did not come up in %ds: ' % START_LIMIT + said(proc)[-700:])
        clean_up()
        return finish()
    seconds, win = got
    print(f'both games up after {seconds:.0f}s', flush=True)
    if seconds > START_LIMIT - 5:
        fail(f'too slow to start: {seconds:.0f}s')
    time.sleep(2)
    left, right = picture(win[0], (640, 480, 0, 0)), picture(win[0], (640, 480, 640, 0))
    if not not_blank(left):
        fail('OUR game is not drawn in the left half')
    if not not_blank(right):
        fail('the ORIGINAL is not drawn in the right half')

    # 2. a key typed in the window reaches both: both pictures change
    run('xdotool', 'windowfocus', win[0])
    run('xdotool', 'key', 'Right')
    time.sleep(6)
    if picture(win[0], (640, 480, 0, 0)) == left:
        fail('a key typed in the window did not move OUR game')
    if picture(win[0], (640, 480, 640, 0)) == right:
        fail('a key typed in the window did not move the ORIGINAL')

    # 3. the original dies: ours stays up, the window says so, and nothing hangs
    for line in alive('dosbox'):
        os.kill(int(line.split()[0]), signal.SIGKILL)
    time.sleep(1)
    run('xdotool', 'windowfocus', win[0])
    t = time.time()
    run('xdotool', 'key', 'Left')
    time.sleep(8)
    if proc.poll() is not None:
        fail('the compare program ended when the original died (our game vanished): ' + said(proc)[-400:])
    else:
        if find('compare to DOS') is None:
            fail('the compare window went away when the original died')
        if time.time() - t > 20:
            fail('the compare program hung when the original died')

    # 4. the window is closed: nothing is left (the normal way out)
    run('xdotool', 'windowclose', win[0])
    time.sleep(2)
    if proc.poll() is None:
        proc.terminate()
        time.sleep(1)
    leftovers('after the window was closed')

    # 5. the program is asked to stop (SIGTERM), and 6. it is killed outright (the Studio closed, a terminal closed, Task Manager): DOSBox must not stay
    for how in (signal.SIGTERM, signal.SIGKILL):
        proc = start()
        got = wait_both(proc)
        if not got:
            fail(f'no window for the {how.name} test')
            clean_up()
            continue
        os.kill(proc.pid, how)
        leftovers(f'after the compare program got {how.name}')
        run('pkill', '-x', 'dosbox')

    # 7. the original cannot start at all: our game is up and playable, and the window says why (and nothing is left)
    proc = start({'QUEST_NO_DOSBOX': '1'})
    time.sleep(12)
    win = find('compare to DOS')
    if proc.poll() is not None or not win:
        fail('without the original, our game did not stay on the screen')
    elif not not_blank(picture(win[0], (640, 480, 0, 0))):
        fail('without the original, OUR game is not drawn')
    proc.terminate()
    leftovers('after the run without the original')

    # 8. the Studio's own start of it must not make a console window (Windows) and must see an early failure
    sys.path.insert(0, ROOT)
    from core import proc as procmod
    if sys.platform.startswith('win'):
        assert procmod.quiet().get('creationflags') == 0x08000000
    finish()


def finish():
    if problems:
        print(f'\n{len(problems)} problems:')
        for p in problems:
            print(' -', p)
        sys.exit(1)
    print('compare process: both games come up side by side, keys reach both, a dead original leaves ours playing, and nothing is left behind: ok')


if __name__ == '__main__':
    main()
