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


def make_dos_save(out_dir: str, level: int, at, hero_file: str | None = None, cls: int = 1):
    """Run the save tool on the original pack. (None, what was left out) when it worked, else (what went wrong, '')."""
    cmd = [sys.executable, '-m', 'compare.savetool', out_dir, str(level), str(at[0]), str(at[1]), '--class', str(cls)]
    if hero_file:
        cmd += ['--hero', hero_file]
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    env.pop('QUEST_PACK', None)
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
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
                 fixes: str = 'off', dos_env=None, log=print, same_things: bool = True, seed: int | None = None, hero_label: str = ''):
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

    # ── starting both ───────────────────────────────────────────────────────
    def start_dos(self):
        game_dir = self.dos.prepare()
        problem, self.removed = make_dos_save(os.path.join(game_dir, 'data'), self.level, self.at, self.hero_file, self.cls)
        if problem:
            raise RuntimeError(problem)
        with open(os.path.join(game_dir, 'data', 'save01.dat'), 'rb') as fh:
            self.start_save = fh.read()
        self.dos.start()
        self.dos.wait_still(1.2, 20)                                               # the title has been drawn
        for k in ('Down', 'Return', 'Return'):                                      # Load Game, then the first save
            self.dos.key_and_wait(k)
        self.seed_ok = self.dos_memory_ok()
        if not self.seed_ok:
            self.log('The original game is laid out differently in memory than expected: the dice cannot be matched.')
        else:
            self.fix_seed()

    def start_ours(self, window, hero):
        from engine.game import Game
        from . import hero as hero_mod, record
        self.window = window
        self.game = Game(window, settings={'fixes': self.fixes, 'sound': 'off'})
        if hero is not None and self.same_things:             # the original cannot hold what it has not got: neither does ours
            gone = hero_mod.strip_unknown(hero)
            if gone and not self.removed:
                self.removed = hero_mod.describe(gone)
        state.start(self.game, self.level, self.at, hero=hero, cls=self.cls)
        self.sync_seed()
        hero_bytes = None
        if self.hero_file:
            with open(self.hero_file, 'rb') as fh:
                hero_bytes = fh.read()
        meta = {'level': self.level, 'at': list(self.at), 'fixes': self.fixes, 'hero': self.hero_label or ('a new hero of class %d' % self.cls),
                'class': self.cls, 'pack': os.environ.get('QUEST_PACK') or 'The Quest', 'removed': self.removed,
                'seed': self.dos_seed(), 'dos_dice_matched': bool(self.seed_ok), 'dosbox': os.path.basename(self.dos.exe or ''),
                'same_things': self.same_things, 'engine': engine_fingerprint()}
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
            time.sleep(0.25)
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
    def settle(self, quiet=0.45, limit=8.0):
        """Wait until the original is idle, waiting for a key: its random number state and its picture have both stopped changing."""
        t = time.time()
        last, since = None, time.time()
        while time.time() - t < limit:
            cur = (self.dos_seed() if self.seed_ok else None, self.dos.picture_bytes())
            if cur != last:
                last, since = cur, time.time()
            elif time.time() - since >= quiet:
                return
            time.sleep(0.05)

    # ── one key on both ─────────────────────────────────────────────────────
    def press(self, xname: str, pygame_key: int, unicode: str = '') -> Report:
        """The same key on both, in step. Returns what happened on each side (and it is recorded)."""
        import pygame
        rep = Report(xname)
        self.settle()
        before = self.dos_seed()
        self.sync_seed()
        self.keys.append((xname, round(time.time() - self.t0, 2)))
        self.dos.key(xname)
        self.game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame_key, unicode=unicode, mod=0))
        self.draw()
        time.sleep(0.25)
        self.settle()
        after = self.dos_seed()
        if before is not None and after is not None:
            rep.dos_draws = count_draws(before, after)
            rep.our_draws = count_draws(before, self.our_seed())
            if rep.dos_draws != rep.our_draws:
                rep.notes.append(f'The original rolled the dice {_n(rep.dos_draws)} times for this key, ours {_n(rep.our_draws)}.')
                self.sync_seed()
        ours = self.game.renderer.screen.copy()
        theirs = self.dos_picture()
        rep.pixels = self.pixel_difference(theirs=theirs)
        if rep.pixels:
            rep.notes.append(f'{rep.pixels} pixels differ between the two pictures.')
        self.reports.append(rep)
        if self.recorder is not None:
            self.recorder.step(xname, rep, ours, theirs, self.facts())
        return rep

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
