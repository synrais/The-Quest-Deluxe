"""Compare to The Quest DOS: the pieces on their own, and (when DOSBox, xdotool and ImageMagick are installed and there is a display)
the real thing: our game and the original in DOSBox, started from one save and given the same keys, must roll the same dice and
draw the same pictures.

Run:  xvfb-run -a python tests/test_compare.py
"""
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DISPLAY_ENV = {k: v for k, v in os.environ.items() if k != 'SDL_VIDEODRIVER'}
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.pop('QUEST_PACK', None)

from compare import dos, keys, session, state  # noqa: E402


def loadouts_unit():
    from compare import loadout, state
    from engine import savefile, state as est
    assert all(loadout.problems(dict(v)) == [] for v in loadout.BUILT_IN.values()), 'every built-in loadout is original items in the right places'
    assert loadout.problems({'worn': {'weapon': 99999, 'armor': 216}, 'bag': [1] * 17}) != []
    d = savefile.SaveData()
    d.bag = {c: 5 for c in savefile.BAG_CELLS}
    loadout.apply(d, loadout.BUILT_IN['Archer'])
    assert d.bag[est.SLOT_WEAPON] == 232 and d.bag[est.SLOT_OFFHAND] == 0 and d.bag[est.SLOT_ARMOR] == 101
    assert [d.bag[c] for c in est.BACKPACK[:5]] == [640, 640, 1, 2, 7] and d.bag[est.BACKPACK[5]] == 0, 'the bag is emptied, then filled'
    mine = os.path.join(tempfile.mkdtemp(), 'loadouts.json')
    loadout.save_preset('Tank', {'weapon': 213, 'armor': 108}, [2, 0, 2], mine)
    assert loadout.presets(mine)['Tank'] == {'worn': {'weapon': 213, 'armor': 108}, 'bag': [2, 2]} and 'Fighter' in loadout.presets(mine)
    loadout.save_preset('Fighter', {'weapon': 201}, [], mine)
    assert loadout.presets(mine)['Fighter']['worn'] == {'weapon': 201}, 'a saved one replaces a built-in'
    loadout.delete_preset('Fighter', mine)
    assert loadout.presets(mine)['Fighter'] == loadout.BUILT_IN['Fighter'] and 'gone' not in loadout.describe(None)
    from engine.game import Game
    import pygame
    pygame.init()
    g = Game(pygame.display.set_mode((640, 480)), settings={'fixes': 'off', 'sound': 'off'})
    state.start(g, 1, (22, 10), cls=1, loadout=dict(loadout.BUILT_IN['Fighter']))
    assert g.player.bag[est.SLOT_WEAPON] == 216 and g.player.bag[est.SLOT_ARMOR] == 104 and g.player.bag[est.BACKPACK[0]] == 1
    raw = savefile.from_bytes(state.save_bytes(g))
    assert raw.bag[est.SLOT_WEAPON] == 216 and raw.bag[est.BACKPACK[6]] == 14, 'the save the original loads has the gear'
    print('compare: loadouts: presets kept, applied to the worn places and the bag, in the save: ok')


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
    # what the original does not have is left out of the hero it is given, and said
    from compare import hero as hero_mod
    d.bag[(12, 4)] = 201            # a club: the original has it
    d.bag[(12, 5)] = 99999          # an item only a pack has
    d.book[(13, 2)] = 1
    d.book[(13, 3)] = 77            # a spell only a pack has
    d.hero['type'] = 9              # a class only a pack has
    d.extra = {'spells': [30]}
    gone = hero_mod.strip_unknown(d)
    assert ('item', 99999, 'bag') in gone and ('spell', 77, 'spell book') in gone and ('class', 9, 'hero') in gone, gone
    assert d.bag[(12, 5)] == 0 and d.bag[(12, 4)] == 201 and d.book[(13, 3)] == 0 and d.hero['type'] == 1 and not d.extra
    assert '99999' in hero_mod.describe(gone) and hero_mod.strip_unknown(d) == []
    from compare import record
    assert record.crc(window) == record.crc(window.copy())
    print('compare: the pieces (original untouched, dice, keys, the save both read, what the original lacks): ok')


def can_run_for_real():
    if dos.find_dosbox() is None or not (shutil.which('xdotool') and shutil.which('import')) or not os.environ.get('DISPLAY'):
        return False
    return not dos.WINDOWS


def side_by_side(level, at, keys_to_press, label, save_to=None, loadout=None, known=None):
    """known: {key number: most pixels that may differ} for a difference already found and written down (see docs/COMPARE.md)."""
    import pygame
    pygame.init()
    window = pygame.display.set_mode((640, 480))
    c = session.Compare(level, at, dos_env=DISPLAY_ENV, seed=20240607, loadout=loadout)
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
            assert r.same or r.pixels <= (known or {}).get(len(c.recorder.steps) - 1, -1), (label, name, r.notes, c.save_recording({'name': 'test'}, os.path.join(ROOT, 'compare reports'), 'testfailed'))
        zip_path = c.save_recording({'name': 'Tester', 'seen': 'nothing'}, save_to, label) if save_to else None
        return total, zip_path
    finally:
        c.close()


def one_window():
    """The real program, started as the Studio starts it: the original's DOSBox window ends up inside the compare window, in its right half."""
    import subprocess
    cmd = [sys.executable, os.path.join(ROOT, 'run_compare.py'), '--level', '1', '--at', '22,10', '--class', '1']
    proc = subprocess.Popen(cmd, cwd=ROOT, env=DISPLAY_ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        found = None
        for _ in range(120):
            time.sleep(0.5)
            tree = subprocess.run(['xwininfo', '-root', '-tree'], env=DISPLAY_ENV, capture_output=True, text=True).stdout
            parent = [line for line in tree.splitlines() if 'compare to DOS' in line]
            if parent:
                kids = subprocess.run(['xwininfo', '-id', parent[0].split()[0], '-children'], env=DISPLAY_ENV, capture_output=True, text=True).stdout
                if 'DOSBox' in kids and '640x480+640+0' in kids:
                    found = kids
                    break
        if not found:
            proc.terminate()
            said = proc.communicate(timeout=10)[0].decode(errors='replace')[-800:]
            raise AssertionError('the original\'s window did not end up inside the compare window: ' + said + repr(parent))
        assert proc.poll() is None, 'the comparison stopped'
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print('compare: the original\'s window is locked into the right half of the compare window: ok')


def for_real():
    from compare import form, record, replay
    out = os.path.join(tempfile.mkdtemp(), 'compare zips')
    # the walk toward two imps and a fight: the dice must be rolled the same number of times every key, and the pictures equal
    seq = ['Right'] * 3 + ['Up'] * 7 + ['Right'] * 3 + ['space', 'Return', 'Left', 'Left', 'Up', 'Return']
    rolled, zip_path = side_by_side(1, (22, 10), seq, 'level1', out)
    assert rolled > 10, f'the test saw only {rolled} dice rolls, so it did not test them'
    # the same on another level, with the hero somewhere else
    side_by_side(2, (10, 10), ['Right', 'Down', 'Down', 'Left', 'Up', 'Right', 'Right'], 'level 2')
    one_window()
    # the check a person runs when it does not work: every step of what a comparison needs, said one by one
    from compare import check
    said = []
    assert check.run(said.append, env=DISPLAY_ENV), said
    assert any('keys reach it' in s for s in said) and any('its memory can be read' in s for s in said) and said[-1] == 'EVERYTHING WORKS', said
    # the same gear on both heroes (worn and in the bag, from the original's own items): pictures and dice stay equal through the inventory,
    # which shows it (and whose closing takes a turn, as in the original), and a worn armour's hatching is the original's phase (up to a few
    # pixels where the shape's edge is hatching or outline: docs/COMPARE.md)
    from compare import loadout
    gear = dict(loadout.BUILT_IN['Fighter'], name='Fighter')
    side_by_side(1, (22, 10), ['Right', 'Right', 'i', 'Escape', 'Left', 'i', 'i', 'Right'], 'with gear', loadout=gear, known={2: 8, 5: 8})
    for armour in (101, 107, 112, 114):
        side_by_side(1, (22, 10), ['i', 'Escape'], f'armour {armour}', loadout={'name': 'one', 'worn': {'armor': armour}, 'bag': [armour, 1]}, known={0: 8})
    assert dos.manifest_ok() == []
    # the recording: the zip holds everything, and run again it comes out the same, to the pixel
    rec = record.read(zip_path)
    assert rec['keys'] == seq and len(rec['steps']) == len(seq) and rec['start_save'], 'the recording is incomplete'
    import zipfile
    names = zipfile.ZipFile(zip_path).namelist()
    for need in ('report.txt', 'meta.json', 'steps.csv', 'log.txt', 'questions.json', 'keys.txt', 'frames/start-ours.png', 'frames/start-dos.png', 'frames/end-ours.png'):
        assert need in names, (need, names)
    assert all(s['same'] for s in rec['steps']) and all(s['crc_ours'] == s['crc_dos'] for s in rec['steps'])
    assert 'Tester' in zipfile.ZipFile(zip_path).read('report.txt').decode()
    import pygame
    window = pygame.display.set_mode((640, 480))
    bad, _ = replay.replay(zip_path, window, dos_env=DISPLAY_ENV)
    assert bad == [], f'the replay did not come out the same: {bad[:3]}'
    del form
    # a difference is recorded with both pictures and the pixels that differ (the original's character sheet still draws a little differently)
    pygame.init()
    c = session.Compare(1, (22, 10), dos_env=DISPLAY_ENV, seed=7)
    try:
        c.start_dos()
        c.start_ours(window, None)
        r = c.press('c', *keys.to_pygame('c'))
        assert r.pixels > 0 and not r.same
        c.press('Up', *keys.to_pygame('Up'))
        z = c.save_recording({'name': 'Tester', 'seen': 'the sheet', 'right': 'DOS looked right'}, out, 'diff')
        names = zipfile.ZipFile(z).namelist()
        assert 'frames/step-0000-difference.png' in names and 'frames/step-0000-dos.png' in names and 'frames/step-0000-ours.png' in names, names
        text = zipfile.ZipFile(z).read('report.txt').decode()
        assert 'the sheet' in text and '1 of them left the two different' in text and 'DOS looked right' in text, text
        assert c.recorder.differences and not c.recorder.unsaved
    finally:
        c.close()
    # what the folder is for: "Send my edits" sends what is in it
    from core import pack_edits
    fake = tempfile.mkdtemp()
    os.makedirs(os.path.join(fake, 'packs', 'TheQuest'))
    os.makedirs(os.path.join(fake, 'Custom Maps', 'compare zips'))
    shutil.copy(z, os.path.join(fake, 'Custom Maps', 'compare zips'))
    files, report = pack_edits.gather(fake, False, None, os.path.join(fake, 'none.json'), '')
    assert any(arc.endswith('compare zips/' + os.path.basename(z)) for _, arc in files) and 'compare zips' in report, (report, files)
    print(f'compare: our game and the original in DOSBox, same save, same keys: {rolled} dice rolls and every picture alike; the recording replays the same: ok')


if __name__ == '__main__':
    pieces()
    loadouts_unit()
    if can_run_for_real():
        for_real()
    else:
        print('compare: the side-by-side run was skipped (it needs DOSBox, xdotool, ImageMagick and a display)')
    print('all compare checks passed')
