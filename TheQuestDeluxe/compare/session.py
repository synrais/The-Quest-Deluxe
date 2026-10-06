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


def make_dos_save(out_dir: str, level: int, at, hero_file: str | None = None, cls: int = 1) -> str | None:
    """Run the save tool on the original pack. None when it worked, else what went wrong."""
    cmd = [sys.executable, '-m', 'compare.savetool', out_dir, str(level), str(at[0]), str(at[1]), '--class', str(cls)]
    if hero_file:
        cmd += ['--hero', hero_file]
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    env.pop('QUEST_PACK', None)
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    if 'READY' in r.stdout:
        return None
    if 'BLOCKED' in r.stdout:
        return 'That square is in a wall or has someone on it in the original. Pick another square.'
    return (r.stderr or r.stdout)[-400:]


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
                 fixes: str = 'off', dos_env=None, log=print):
        self.level, self.at, self.hero_file, self.cls, self.fixes = level, tuple(at), hero_file, cls, fixes
        self.pack_root = pack_root
        self.dos = dos.Dos(env=dos_env)
        self.log = log
        self.game = None
        self.window = None
        self.keys: list = []                # every key sent: [(name, seconds since the start)]
        self.reports: list = []
        self.t0 = time.time()
        self.seed_ok = False

    # ── starting both ───────────────────────────────────────────────────────
    def start_dos(self):
        game_dir = self.dos.prepare()
        problem = make_dos_save(os.path.join(game_dir, 'data'), self.level, self.at, self.hero_file, self.cls)
        if problem:
            raise RuntimeError(problem)
        self.dos.start()
        self.dos.wait_still(1.2, 20)                                               # the title has been drawn
        for k in ('Down', 'Return', 'Return'):                                      # Load Game, then the first save
            self.dos.key_and_wait(k)
        self.seed_ok = self.dos_memory_ok()
        if not self.seed_ok:
            self.log('The original game is laid out differently in memory than expected: the dice cannot be matched.')

    def start_ours(self, window, hero):
        from engine.game import Game
        self.window = window
        self.game = Game(window, settings={'fixes': self.fixes, 'sound': 'off'})
        state.start(self.game, self.level, self.at, hero=hero, cls=self.cls)
        self.sync_seed()

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
        """The same key on both, in step. Returns what happened on each side."""
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
        rep.pixels = self.pixel_difference()
        if rep.pixels:
            rep.notes.append(f'{rep.pixels} pixels differ between the two pictures.')
        self.reports.append(rep)
        return rep

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

    def pixel_difference(self, save_to: str | None = None) -> int:
        import pygame
        theirs = self.dos_picture()
        if theirs is None:
            return 0
        ours = self.game.renderer.screen
        if theirs.get_size() != ours.get_size():
            theirs = pygame.transform.scale(theirs, ours.get_size())
        w, h = ours.get_size()
        # DOSBox turns the VGA's 6-bit colours into 8 bits a little differently (84 or 80, 252 or 248): the top five bits are what counts
        cut = bytes(v & 0xF8 for v in range(256))
        a = pygame.image.tostring(ours, 'RGB').translate(cut)
        b = pygame.image.tostring(theirs, 'RGB').translate(cut)
        if a == b:
            return 0
        n = 0
        diff = pygame.Surface((w, h))
        for i in range(0, len(a), 3):
            if a[i:i + 3] != b[i:i + 3]:
                n += 1
                p = i // 3
                diff.set_at((p % w, p // w), (255, 0, 255))
        if save_to:
            sheet = pygame.Surface((w * 3, h))
            sheet.blit(ours, (0, 0))
            sheet.blit(theirs, (w, 0))
            sheet.blit(diff, (2 * w, 0))
            pygame.image.save(sheet, save_to)
        return n

    def mark(self, folder: str, why: str = '') -> str:
        """Save what both show now, the pictures side by side with the differences, and every key so far, for a bug report."""
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        base = os.path.join(folder, f'mismatch-{stamp}')
        n = self.pixel_difference(save_to=base + '.png')
        with open(base + '.txt', 'w', encoding='utf-8') as fh:
            fh.write(f'Level {self.level}, started at {self.at}. {why}\n')
            fh.write(f'Pixels that differ now: {n}\nKeys, in order: {" ".join(k for k, _ in self.keys)}\n\nWhat each key did:\n')
            for r in self.reports:
                fh.write(f'  {r.key:8} dice original {_n(r.dos_draws)} ours {_n(r.our_draws)} pixels {r.pixels}'
                         + ('   ' + ' '.join(r.notes) if r.notes else '') + '\n')
        return base

    def close(self):
        self.dos.stop()


def _n(v):
    return '?' if v is None else str(v)
