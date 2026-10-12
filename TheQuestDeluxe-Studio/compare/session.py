"""Compare to The Quest DOS: our game and the original side by side, fed the same keys.

How they are made to agree:
  * both start from one save (made on the original pack, loaded by the original through its own Load Game, built into our game
    directly), so the hero, the place and what is around start the same, with no intro fade to put them out of step;
  * every key you press goes to both, one at a time, when both have finished the last;
  * the original's random numbers are read out of DOSBox's memory (the C library's rand() state) and put into our game before each
    key, so a monster rolls the same dice on both sides; afterwards the two states are compared, and a different number of rolls is
    reported as a difference;
  * the two pictures are compared pixel by pixel after each key (our drawing is exact to the original's).

Run it with run_compare.py. The original's own files are never touched (see compare/dos.py).
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field

from core import proc

from . import dos, state

ROOT = dos.ROOT
SEED_MARKER = b'Want to save'            # a string in the exe's data, to find where the exe sits in DOS memory
SEED_DELTA = 0x547B4 - 0x5284F           # from that string to rand()'s state (found by watching it change as monsters moved)


@dataclass
class Report:
    """What one key did on each side."""
    key: str
    dos_draws: int | None = None        # random numbers the original used for it (None: more than could be counted)
    our_draws: int | None = None
    pixels: int = 0                     # pixels that differ between the two pictures
    notes: list = field(default_factory=list)

    @property
    def same(self):
        return self.dos_draws == self.our_draws and self.pixels == 0


def make_dos_save(out_dir: str, level: int, at, hero_file: str | None = None, cls: int = 1, loadout: dict | None = None, story=None):
    """Run the save tool on the original pack. (None, what was left out) when it worked, else (what went wrong, '')."""
    cmd = [sys.executable, '-m', 'compare.savetool', out_dir, str(level), str(at[0]), str(at[1]), '--class', str(cls)]
    if hero_file:
        cmd += ['--hero', hero_file]
    if story is not None:
        cmd += ['--story', '%d,%d' % tuple(story)]
    gear_file = None
    if loadout:
        import json
        import tempfile
        fd, gear_file = tempfile.mkstemp(suffix='.json', prefix='quest_loadout_')
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(loadout, fh)
        cmd += ['--loadout', gear_file]
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    env.pop('QUEST_PACK', None)
    try:
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, **proc.quiet())
    finally:
        if gear_file:
            os.remove(gear_file)
    removed = next((line[len('REMOVED '):] for line in r.stdout.splitlines() if line.startswith('REMOVED ')), '')
    if 'READY' in r.stdout:
        return None, removed
    if 'BLOCKED' in r.stdout:
        return 'That square is in a wall or has someone on it in the original. Pick another square.', ''
    return (r.stderr or r.stdout)[-400:], ''


def count_draws(a: int, b: int, limit=4000):
    """How many rand() steps take state a to state b (None if more than limit)."""
    s = a
    for k in range(limit + 1):
        if s == b:
            return k
        s = dos.lcg(s)
    return None


class Compare:
    def __init__(self, level: int, at, pack_root: str | None = None, hero_file: str | None = None, cls: int = 1,
                 fixes: str = 'off', dos_env=None, log=print, same_things: bool = True, seed: int | None = None, hero_label: str = '', loadout: dict | None = None,
                 story=None):
        self.loadout, self.story = loadout, story
        self.level, self.at, self.hero_file, self.cls, self.fixes = level, tuple(at), hero_file, cls, fixes
        self.pack_root = pack_root
        self.dos = dos.Dos(env=dos_env)
        self.log = log
        self.game = None
        self.window = None
        self.same_things, self.seed, self.hero_label = same_things, seed, hero_label
        self.removed = ''
        self.recorder = None
        self.keys: list = []                # every key sent: [(name, seconds since the start)]
        self.reports: list = []
        self.t0 = time.time()
        self.seed_ok = False
        self.talks: list = []              # every message the original and ours showed: (the words, pixels that differed)
        self.current = None                # the key being sent now

    # ── starting both ───────────────────────────────────────────────────────
    progress = staticmethod(lambda text: None)               # told what is happening while it starts (the window shows it)

    def start_dos(self):
        self.progress('Making the save the original loads ...')
        game_dir = self.dos.prepare()
        problem, self.removed = make_dos_save(os.path.join(game_dir, 'data'), self.level, self.at, self.hero_file, self.cls, self.loadout, self.story)
        if problem:
            raise RuntimeError(problem)
        with open(os.path.join(game_dir, 'data', 'save01.dat'), 'rb') as fh:
            self.start_save = fh.read()
        self.progress('Starting the original in DOSBox ...')
        self.dos.start()
        self.after_dos_window()
        self.dos.wait_still(1.2, 20)                                               # the title has been drawn
        self.progress('Loading the saved game in the original ...')
        for k in ('Down', 'Return', 'Return'):                                      # Load Game, then the first save
            self.dos.key_and_wait(k)
            self.after_dos_window()
        self.progress('Finding the original\'s dice ...')
        self.seed_ok = self.dos_memory_ok()
        if not self.seed_ok:
            self.log('The original game is laid out differently in memory than expected: the dice cannot be matched.')
        else:
            self.fix_seed()

    after_dos_window = staticmethod(lambda: None)            # called when DOSBox's window exists, and after each step of loading (the window is locked into ours)

    def start_ours(self, window, hero):
        self.begin_ours(window, hero)
        self.finish_ours()

    def begin_ours(self, window, hero):
        """Our game, on its level and square with its hero: shown at once, while the original is still starting."""
        from engine.game import Game
        from . import hero as hero_mod
        self.window = window
        self.game = Game(window, settings={'fixes': self.fixes, 'sound': 'off'})
        self.game.renderer.wait_talk = self.talk_wait
        if hero is not None and self.same_things:             # the original cannot hold what it has not got: neither does ours
            gone = hero_mod.strip_unknown(hero)
            if gone and not self.removed:
                self.removed = hero_mod.describe(gone)
        self.starting = True
        try:
            state.start(self.game, self.level, self.at, hero=hero, cls=self.cls, loadout=self.loadout, story=self.story)
        finally:
            self.starting = False

    def finish_ours(self):
        """Once the original is ready: our dice are set from its, and the recording begins with both pictures."""
        from . import record
        self.sync_seed()
        hero_bytes = None
        if self.hero_file:
            with open(self.hero_file, 'rb') as fh:
                hero_bytes = fh.read()
        meta = {'level': self.level, 'at': list(self.at), 'fixes': self.fixes, 'hero': self.hero_label or ('a new hero of class %d' % self.cls),
                'class': self.cls, 'pack': os.environ.get('QUEST_PACK') or 'The Quest', 'removed': self.removed,
                'seed': self.dos_seed(), 'dos_dice_matched': bool(self.seed_ok), 'dosbox': os.path.basename(self.dos.exe or ''),
                'same_things': self.same_things, 'engine': engine_fingerprint(), 'loadout': self.loadout, 'story': self.story}
        self.recorder = record.Recorder(meta, getattr(self, 'start_save', None), hero_bytes)
        self.draw()
        self.recorder.first(self.game.renderer.screen.copy(), self.dos_picture())

    # ── the dice ────────────────────────────────────────────────────────────
    def dos_memory_ok(self) -> bool:
        """Find the exe's data in the emulated memory and, from it, the original's random number state."""
        for _ in range(24):                                    # DOSBox may still be setting its memory up
            try:
                if self.dos.locate_text(SEED_MARKER):
                    self.seed_address = self.dos.marker_at + SEED_DELTA
                    return True
            except (OSError, RuntimeError, ValueError):
                self.dos._mem = None
            self.dos._sleep(0.25)
        return False

    def fix_seed(self):
        """Give the original a dice state of our choosing (the one a recording began with, or a new one) so a replay is the same game."""
        import random
        want = self.seed if self.seed is not None else random.Random().getrandbits(32)
        self.dos.write(self.seed_address, struct.pack('<I', want & 0xFFFFFFFF))

    def dos_seed(self) -> int | None:
        if not self.seed_ok:
            return None
        return struct.unpack('<I', self.dos.read(self.seed_address, 4))[0]

    def our_seed(self) -> int:
        from engine import rules
        return rules._seed[0]

    def sync_seed(self):
        s = self.dos_seed()
        if s is not None:
            from engine import rules
            rules._seed[0] = s

    # ── waiting for the original ────────────────────────────────────────────
    def settle(self, quiet=0.45, limit=8.0, at_least=0.0):
        """Wait until the original is idle, waiting for a key: its random number state and its picture have both stopped changing
        (and at least `at_least` seconds from now have passed: it has had time to start on the key)."""
        t = time.time()
        last, since = None, time.time()
        while time.time() - t < limit:
            cur = (self.dos_seed() if self.seed_ok else None, self.dos.picture_bytes())
            if cur != last:
                last, since = cur, time.time()
            elif time.time() - since >= quiet and time.time() - t >= at_least:
                return
            time.sleep(0.02)

    # ── one key on both ─────────────────────────────────────────────────────
    pending = None                       # (the report, the original's dice before the key, when it was sent): a key whose result has not been looked at yet
    HEARD = 0.2                          # seconds the original is given to start on a key before it can count as idle again

    def press(self, xname: str, pygame_key: int, unicode: str = '') -> Report:
        """The same key on both, in step, and what happened on each side (it is recorded). Waits for the result; the window uses send() and poll() so that a key never waits."""
        self.send(xname, pygame_key, unicode)
        return self.complete()

    def send(self, xname: str, pygame_key: int, unicode: str = ''):
        """The same key on both, at once. How it went is looked at afterwards (poll or complete). The one before it is finished first: the original must be at rest."""
        import pygame
        self.complete()
        rep = self.current = Report(xname)
        before = self.dos_seed()
        self.sync_seed()
        self.keys.append((xname, round(time.time() - self.t0, 2)))
        self.dos.key(xname)
        self.game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame_key, unicode=unicode, mod=0))        # (a message in it waits for Space: see talk_wait)
        self.current = None
        self.draw()
        self.pending = (rep, before, time.time())
        self._watch = (None, time.time(), 0.0)

    def poll(self):
        """Called often while the window is idle: when the original has finished with the last key, its result (a Report), else None. Never waits."""
        if self.pending is None:
            return None
        now = time.time()
        last, since, checked = self._watch
        if now - checked < 0.1:
            return None
        cur = (self.dos_seed() if self.seed_ok else None, self.dos.picture_bytes())
        if cur != last:
            self._watch = (cur, now, time.time())
            return None
        self._watch = (last, since, time.time())
        if now - since >= 0.45 and now - self.pending[2] >= self.HEARD:
            return self.complete()
        return None

    def complete(self):
        """Wait (if need be) for the original to finish with the last key sent, then say how it went. None when no key is waiting."""
        if self.pending is None:
            return None
        rep, before, sent = self.pending
        self.settle(at_least=max(0.0, self.HEARD - (time.time() - sent)))
        self.pending = None
        xname = rep.key
        after = self.dos_seed()
        if before is not None and after is not None:
            rep.dos_draws = count_draws(before, after)
            rep.our_draws = count_draws(before, self.our_seed())
            if rep.dos_draws != rep.our_draws:
                rep.notes.append(f'The original rolled the dice {_n(rep.dos_draws)} times for this key, ours {_n(rep.our_draws)}.')
                self.sync_seed()
        ours = self.game.renderer.screen.copy()
        theirs = self.dos_picture()
        end = self.pixel_difference(theirs=theirs)
        rep.pixels += end
        if end:
            rep.notes.append(f'{end} pixels differ between the two pictures.')
        self.reports.append(rep)
        if self.recorder is not None:
            self.recorder.step(xname, rep, ours, theirs, self.facts())
        return rep

    def wait_for_message(self, ours, limit=8.0):
        """The original shows the message only after its spell effects (a second or two): wait until its message strip is like ours
        (or the limit passes: then the two are said to differ), and for the picture to be still."""
        import pygame
        from . import record
        strip = (0, 410, 640, 70)
        want = record.quantised(ours.subsurface(strip))
        t = time.time()
        while time.time() - t < limit:
            pic = self.dos_picture()
            if pic is not None:
                got = record.quantised(pic.subsurface(strip))
                if sum(1 for i in range(0, len(want), 3) if want[i:i + 3] != got[i:i + 3]) < 400:
                    break
            self.dos._sleep(0.1)
        self.dos.wait_still(0.3, 4)

    starting = False
    on_talk = None                       # the window's wait for the person's Space (called with the game and the words); None: Space is pressed for them

    def talk_wait(self, game, text, fast=False):
        """talk() in the original draws a message and waits for Space (getch) before anything else happens, so ours does too, and that
        Space goes to the original as well. (A key typed meanwhile is lost in both.) The two pictures, with the message on, are compared."""
        if self.starting:                                                    # a scene walked through to make the starting screen: nobody waits
            return
        from engine.ui import TalkBox
        game.renderer.draw(game, present=False)
        TalkBox(text).draw(game.renderer, game.renderer.screen)
        if self.dos.window is not None:
            self.wait_for_message(game.renderer.screen)
        theirs = self.dos_picture()
        n = self.pixel_difference(theirs=theirs)
        self.talks.append((text, n))
        if n and self.recorder is not None and theirs is not None:          # both pictures with the message on, kept where they differ
            from . import record
            name = f'frames/step-{len(self.recorder.steps):04d}-message-{len(self.talks)}'
            ours = game.renderer.screen
            self.recorder.frames[name + '-ours.png'] = record.png_bytes(ours)
            self.recorder.frames[name + '-dos.png'] = record.png_bytes(theirs)
            self.recorder.frames[name + '-difference.png'] = record.png_bytes(record.diff_surface(ours, theirs))
        if self.current is not None and n:
            self.current.notes.append(f'{n} pixels differ while the message is shown.')
            self.current.pixels += n
        game.renderer.present()
        if self.on_talk is not None:
            self.on_talk(game, text)
        self.dos.key('space')

    def facts(self) -> dict:
        """What our game says about itself after a key (for the log: the original has no such window into it)."""
        g = self.game
        p = g.player
        try:
            msgs = ' | '.join(str(m) for m in g.messages[-3:])
        except Exception:                                                  # noqa: BLE001 - a log line is never worth a crash
            msgs = ''
        return {'x': p.X, 'y': p.Y, 'life': p.hero.life, 'mana': p.hero.mana, 'hero_level': p.hero.level, 'overlay': type(g.overlay).__name__ if g.overlay else '',
                'messages': msgs, 'seed_ours': self.our_seed(), 'seed_dos': self.dos_seed()}

    def draw(self):
        self.game.renderer.draw(self.game)

    # ── the pictures ────────────────────────────────────────────────────────
    def dos_picture(self):
        """The original's screen as a pygame surface (None when it can't be taken)."""
        import pygame
        if dos.WINDOWS:                                                    # (no file in between: that is slow)
            shot = self.dos.picture_surface()
            size = dos._CAPTURE['size']
            if shot is not None and size not in (None, (640, 480)) and not getattr(self, '_said_size', False):
                self._said_size = True
                self.log(f'The original\'s window is {size[0]} x {size[1]}, not 640 x 480: Windows is stretching it, so many pixels will differ.')
            return shot
        path = os.path.join(self.dos.scratch, 'shot.png')
        if not self.dos.screenshot(path):
            return None
        try:
            return pygame.image.load(path).convert()
        except (pygame.error, FileNotFoundError):
            return None

    def pixel_difference(self, theirs=None, save_to: str | None = None) -> int:
        """How many pixels differ between ours and the original's now (their top five bits: DOSBox writes the VGA's colours as 80 or 248, ours as 84 or 252)."""
        import pygame
        from . import record
        theirs = theirs if theirs is not None else self.dos_picture()
        if theirs is None:
            return 0
        ours = self.game.renderer.screen
        if theirs.get_size() != ours.get_size():
            theirs = pygame.transform.scale(theirs, ours.get_size())
        a, b = record.quantised(ours), record.quantised(theirs)
        if a == b:
            return 0
        n = sum(1 for i in range(0, len(a), 3) if a[i:i + 3] != b[i:i + 3])
        if save_to:
            pygame.image.save(record.diff_surface(ours, theirs), save_to)
        return n

    def finish(self):
        """The last pictures go into the recording."""
        self.complete()
        if self.recorder is not None:
            self.recorder.last(self.game.renderer.screen.copy(), self.dos_picture())

    def save_recording(self, answers: dict, folder: str | None = None, label: str = '') -> str:
        from . import record
        self.finish()
        return self.recorder.save(folder or record.zips_folder(), answers, label)

    def close(self):
        self.dos.stop()


def engine_fingerprint() -> str:
    """A short checksum of the game's engine files, so a recording says which engine it was made with."""
    import hashlib
    h = hashlib.sha1()
    d = os.path.join(ROOT, 'engine')
    for f in sorted(os.listdir(d)):
        if f.endswith('.py'):
            with open(os.path.join(d, f), 'rb') as fh:
                h.update(fh.read().replace(b'\r\n', b'\n'))
    return h.hexdigest()[:12]


def _n(v):
    return '?' if v is None else str(v)
