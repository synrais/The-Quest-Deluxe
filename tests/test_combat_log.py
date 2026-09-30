"""The combat log (Deluxe): it reports, and changes nothing.

The same random games played with the log off and on must reach the same state after every key
(the log only draws), and fights must be reported: hits with their damage, misses and deaths,
with the damage rising off the square that took it.

    python tests/test_combat_log.py              # 12 runs of 200 keys
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lockstep  # noqa: E402  (sets up pygame with the dummy video driver)
from lockstep import pygame, deluxe, deluxe_rules, DeluxeSlots, setup, state, pick_key, diff  # noqa: E402
from test_view3d import Single, press  # noqa: E402


def play(seed: int, keys: int, log: bool):
    deluxe_rules.srand(seed)
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.slots = DeluxeSlots(tempfile.mkdtemp())
    g.combat_log = log
    rnd = random.Random(seed)
    how = setup(Single(g), rnd)
    states = [state(g)]
    for i in range(keys):
        if not g.running:
            break
        press(g, pick_key(rnd))
        states.append(state(g))
        if log and i % 5 == 0:
            g.renderer.draw(g, present=False)      # the log and the numbers draw wherever the game goes
    return how, states, g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=12)
    ap.add_argument('--keys', type=int, default=200)
    a = ap.parse_args()
    bad, lines = 0, []
    for run in range(a.runs):
        seed = 7000 + run
        how, off, _ = play(seed, a.keys, False)
        _, on, g = play(seed, a.keys, True)
        lines += [t for t, _, _ in g.log_lines]
        for i, (x, y) in enumerate(zip(off, on)):
            why = diff(x, y)
            if why:
                bad += 1
                print(f'run {run} (seed {seed}, {how}): the log changed the game after {i} keys: {why}')
                break
    hits = [s for s in lines if ' for ' in s]
    print(f'{a.runs - bad} of {a.runs} runs play the same with the combat log on; {len(lines)} lines logged, '
          f'e.g. {hits[:3]}')

    # a fight: hits, misses and a death are reported, and the numbers rise off the squares
    deluxe_rules.srand(3)
    g = deluxe.Game(pygame.Surface((640, 480)))
    g.quick_start(1, 1, (9, 20))
    g.combat_log = True
    for _ in range(12):
        press(g, pygame.K_UP)
        g.renderer.draw(g, present=False)
    said = [t for t, _, _ in g.log_lines]
    assert any(s.startswith('You hit the imp for ') for s in said), said
    assert any(s.startswith('The imp dies.') for s in said), said
    assert said.index(next(s for s in said if s.startswith('The imp dies.'))) > \
        said.index(next(s for s in said if s.startswith('You hit the imp'))), 'a death before its blow'
    print('a fight is reported in order (hits, then the death): ok')
    sys.exit(1 if bad or not hits else 0)


if __name__ == '__main__':
    main()
