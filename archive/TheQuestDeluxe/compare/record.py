"""Recording a comparison, so someone else can see exactly what you saw.

What is kept, and why that is enough (and small): both games are made to start from one save and the original's dice are put in ours before every key,
so the same start, the same keys and the same dice give the same game again, to the pixel. So the recording is
  * the start: the save the original loaded, the level and square, the setting for the original's bugs, and the dice it began with,
  * every key, with its time,
  * for every key a line of facts: the dice each side rolled, the number of pixels that differ, and a checksum of each picture (CRC-32 of its
    exact pixels), so a replay can prove it saw the same thing without storing a video,
  * the pictures themselves (lossless PNG, 16 colours so about 10 KB) only at the start, the end and wherever the two differed, both sides and
    the difference side by side,
  * a log (what our game said, where the hero stood, his life) and the answers to the questions.
It is one zip in `Custom Maps/compare zips`, which "Send my edits" sends with the rest.
"""
from __future__ import annotations

import csv
import io
import json
import os
import platform
import time
import zipfile
import zlib

QUESTIONS = [
    ('name', 'Your name', 'So we know who to ask.', 1),
    ('seen', 'What did you see that looked wrong?', 'A few words: "the sword is missing", "the imp walked through the tree".', 2),
    ('right', 'Which one looked right?', 'DOS, ours, or neither.', 1),
    ('how', 'How bad is it?', 'Only looks different, plays different, or the game crashed or stuck.', 1),
    ('doing', 'What were you doing?', 'Where you were and what you pressed: "walking up past the farm, then hit the imp".', 2),
    ('again', 'Does it happen every time?', 'Yes, sometimes, or you only tried once.', 1),
    ('more', 'Anything else we should know?', 'Optional.', 2),
]
CHOICES = {'right': ['DOS looked right', 'Ours looked right', 'Neither', 'Not sure'],
           'how': ['It only looks different', 'It plays different', 'The game crashed or got stuck', 'Not sure'],
           'again': ['Yes, every time', 'Sometimes', 'I only tried once']}


def quantised(surface) -> bytes:
    """A picture's pixels with the VGA's 6-bit colours squared up (DOSBox writes 80 where we write 84): what is compared and checksummed."""
    import pygame
    cut = bytes(v & 0xF8 for v in range(256))
    return pygame.image.tostring(surface, 'RGB').translate(cut)


def crc(surface) -> int:
    return zlib.crc32(quantised(surface)) & 0xFFFFFFFF


def png_bytes(surface) -> bytes:
    import pygame
    buf = io.BytesIO()
    pygame.image.save(surface, buf, 'x.png')
    return buf.getvalue()


def diff_surface(ours, theirs):
    """Ours, the original's and the pixels that differ (pink), side by side."""
    import pygame
    w, h = ours.get_size()
    a, b = quantised(ours), quantised(theirs)
    sheet = pygame.Surface((w * 3, h))
    sheet.blit(ours, (0, 0))
    sheet.blit(theirs, (w, 0))
    diff = pygame.Surface((w, h))
    for i in range(0, len(a), 3):
        if a[i:i + 3] != b[i:i + 3]:
            p = i // 3
            diff.set_at((p % w, p // w), (255, 0, 255))
    sheet.blit(diff, (2 * w, 0))
    return sheet


class Recorder:
    def __init__(self, meta: dict, start_save: bytes | None = None, hero_save: bytes | None = None):
        self.meta = dict(meta)
        self.meta.setdefault('started', time.strftime('%Y-%m-%d %H:%M:%S'))
        self.meta['platform'] = platform.platform()
        self.start_save, self.hero_save = start_save, hero_save
        self.steps: list = []
        self.frames: dict[str, bytes] = {}          # name -> png
        self.log: list = []
        self.t0 = time.time()
        self.saved_at = 0                            # how many steps were in the last zip saved

    def note(self, text: str):
        self.log.append(f'{time.time() - self.t0:8.2f}  {text}')

    def first(self, ours, theirs):
        self.frames['start-ours.png'] = png_bytes(ours)
        if theirs is not None:
            self.frames['start-dos.png'] = png_bytes(theirs)
        self.meta['start_crc'] = {'ours': crc(ours), 'dos': crc(theirs) if theirs is not None else None}

    def step(self, key: str, report, ours, theirs, facts: dict):
        i = len(self.steps)
        row = {'n': i, 'key': key, 't': round(time.time() - self.t0, 2), 'dice_dos': report.dos_draws, 'dice_ours': report.our_draws,
               'pixels': report.pixels, 'crc_ours': crc(ours), 'crc_dos': crc(theirs) if theirs is not None else None,
               'same': bool(report.same)}
        row.update(facts)
        self.steps.append(row)
        if not report.same and theirs is not None:
            name = f'frames/step-{i:04d}'
            self.frames[name + '-ours.png'] = png_bytes(ours)
            self.frames[name + '-dos.png'] = png_bytes(theirs)
            self.frames[name + '-difference.png'] = png_bytes(diff_surface(ours, theirs))
        self.note(f'{i:3d} {key:8} dice {row["dice_dos"]}/{row["dice_ours"]} pixels {row["pixels"]}' + (' ' + ' '.join(report.notes) if report.notes else '')
                  + (f'  {facts.get("messages", "")}' if facts.get('messages') else ''))

    def last(self, ours, theirs):
        self.frames['end-ours.png'] = png_bytes(ours)
        if theirs is not None:
            self.frames['end-dos.png'] = png_bytes(theirs)

    @property
    def differences(self) -> list:
        return [s for s in self.steps if not s['same']]

    @property
    def unsaved(self) -> bool:
        return len(self.steps) > self.saved_at and bool(self.differences)

    # ── the zip ─────────────────────────────────────────────────────────────
    def report_text(self, answers: dict) -> str:
        m = self.meta
        lines = ['A COMPARISON TO THE QUEST DOS', '', f'Made {m["started"]} by {answers.get("name") or "(no name)"} on {m["platform"]}',
                 f'Level {m["level"]}, started at square {tuple(m["at"])}, hero: {m.get("hero", "a new hero")}',
                 f'Pack: {m.get("pack", "?")}   original bugs kept in ours: {m.get("fixes") == "off"}', '']
        for key, label, hint, rows in QUESTIONS:
            lines += [label.upper(), (answers.get(key) or '(not answered)').strip(), '']
        d = self.differences
        lines += [f'{len(self.steps)} keys pressed; {len(d)} of them left the two different.', '']
        for s in d[:40]:
            lines.append(f'  key {s["n"]} ({s["key"]}): dice DOS {s["dice_dos"]} ours {s["dice_ours"]}, {s["pixels"]} pixels differ  (frames/step-{s["n"]:04d}-*.png)')
        if len(d) > 40:
            lines.append(f'  ... and {len(d) - 40} more (see steps.csv)')
        lines += ['', 'TO SEE IT AGAIN: python run_compare.py --replay "<this zip>"   (it starts both from the same save, presses the same keys, and says '
                  'whether every picture and every dice roll came out the same).', '']
        if m.get('removed'):
            lines += ['LEFT OUT OF THE ORIGINAL (it does not have them): ' + m['removed'], '']
        return '\n'.join(lines)

    def save(self, folder: str, answers: dict, label: str = '') -> str:
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        who = ''.join(ch for ch in (answers.get('name') or '') if ch.isalnum())[:16]
        name = f'compare_{stamp}' + (f'_{who}' if who else '') + (f'_{label}' if label else '') + '.zip'
        path = os.path.join(folder, name)
        buf = io.StringIO()
        keys = sorted({k for s in self.steps for k in s})
        w = csv.DictWriter(buf, fieldnames=keys)
        w.writeheader()
        for s in self.steps:
            w.writerow(s)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('report.txt', self.report_text(answers))
            z.writestr('questions.json', json.dumps(answers, indent=1, ensure_ascii=False))
            z.writestr('meta.json', json.dumps(dict(self.meta, steps=len(self.steps), differences=len(self.differences)), indent=1, sort_keys=True))
            z.writestr('keys.txt', '\n'.join(f'{s["key"]} {s["t"]}' for s in self.steps) + '\n')
            z.writestr('steps.csv', buf.getvalue())
            z.writestr('steps.json', json.dumps(self.steps))
            z.writestr('log.txt', '\n'.join(self.log) + '\n')
            if self.start_save:
                z.writestr('start/save01.dat', self.start_save)
            if self.hero_save:
                z.writestr('start/hero.sav', self.hero_save)
            for n, data in sorted(self.frames.items()):
                z.writestr(n if '/' in n else f'frames/{n}', data)
        self.saved_at = len(self.steps)
        return path


def read(path: str) -> dict:
    """A recording back: {'meta', 'steps', 'answers', 'keys', 'start_save', 'hero_save'}."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        return {'meta': json.loads(z.read('meta.json')), 'steps': json.loads(z.read('steps.json')),
                'answers': json.loads(z.read('questions.json')) if 'questions.json' in names else {},
                'keys': [line.split()[0] for line in z.read('keys.txt').decode().splitlines() if line.strip()],
                'start_save': z.read('start/save01.dat') if 'start/save01.dat' in names else None,
                'hero_save': z.read('start/hero.sav') if 'start/hero.sav' in names else None}


def zips_folder() -> str:
    """Custom Maps/compare zips: inside the game folder, so a new game dragged over this one leaves them, and "Send my edits" finds them."""
    from engine import pack
    return os.environ.get('QUEST_COMPARE_DIR') or os.path.join(pack.CUSTOM_DIR, 'compare zips')
