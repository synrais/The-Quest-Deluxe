"""Replaying a recording: both games start from the recording's save and dice, the same keys are pressed, and every dice roll and picture is
checked against what was recorded."""
from __future__ import annotations

import os
import tempfile

from . import keys, record, session


def replay(path: str, window, log=print, delay: float = 0.0, only_first: int | None = None, dos_env=None):
    """Run the recording. Returns (differences, compare): the steps that came out different from the recording [(n, key, what)]; the Compare is closed."""
    rec = record.read(path)
    meta = rec['meta']
    hero_file = None
    hero = None
    tmp = tempfile.mkdtemp(prefix='quest_replay_')
    if rec['hero_save']:
        from engine import savefile
        hero_file = os.path.join(tmp, 'hero.sav')
        with open(hero_file, 'wb') as fh:
            fh.write(rec['hero_save'])
        hero = savefile.from_bytes(rec['hero_save'])
    c = session.Compare(meta['level'], tuple(meta['at']), hero_file=hero_file, cls=meta.get('class', 1), fixes=meta.get('fixes', 'off'),
                        same_things=meta.get('same_things', True), seed=meta.get('seed'), log=log, dos_env=dos_env)
    bad = []
    try:
        c.start_dos()
        c.start_ours(window, hero)
        c.draw()
        want = rec['steps'][:only_first] if only_first else rec['steps']
        for step in want:
            k, u = keys.to_pygame(step['key'])
            r = c.press(step['key'], k, u)
            got = c.recorder.steps[-1]
            what = []
            if got['dice_dos'] != step['dice_dos']:
                what.append(f'dice DOS {got["dice_dos"]} (recorded {step["dice_dos"]})')
            if got['crc_ours'] != step['crc_ours']:
                what.append('our picture is not what was recorded')
            if step.get('crc_dos') is not None and got['crc_dos'] != step['crc_dos']:
                what.append('the original\'s picture is not what was recorded')
            if what:
                bad.append((step['n'], step['key'], '; '.join(what)))
            if delay:
                import time
                time.sleep(delay)
            del r
    finally:
        c.close()
    return bad, c
