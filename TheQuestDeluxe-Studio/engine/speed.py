"""Game speed: 1x (the original's pace), 2x, 4x or 8x.

Only the waiting is sped up: the animations (a blow, a spell, a missile, the Death Bringer's earthquake), the
delays between a key loop's pictures, the FPS view's glide from square to square and the weapon in the hero's
hand. The rules, the dice and what a turn does are the same at every speed, so a game played at 8x is the same
game, only quicker.

ticks() is pygame's clock run at the game's speed: everything in the renderer that times itself (a glide, a swing,
a zoom) reads it, so a change of speed in the middle of one only changes how fast the rest of it goes.
"""
from __future__ import annotations

import pygame

STEPS = (1, 2, 4, 8)            # the speeds + and - go through
MUTE_FROM = 4                   # the PC-speaker tones at 4x and more would only be clicks: they are left out

_speed = 1
_real = 0                       # pygame's clock when the speed last changed ...
_virtual = 0                    # ... and the game's clock then (the two are the same until the speed is first changed)


def get() -> int:
    return _speed


def use(n) -> int:
    """Play at n times the pace (1, 2, 4 or 8; anything else is the nearest one). Returns the speed now."""
    global _speed, _real, _virtual
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 1
    n = min(STEPS, key=lambda s: abs(s - n))
    if n != _speed:
        now = pygame.time.get_ticks()
        _virtual, _real, _speed = int(_virtual + (now - _real) * _speed), now, n          # the time so far counts at the old speed
    return _speed


def faster() -> int:
    """The next speed up (8x stays 8x)."""
    return use(next((s for s in STEPS if s > _speed), STEPS[-1]))


def slower() -> int:
    """The next speed down (1x stays 1x)."""
    return use(next((s for s in reversed(STEPS) if s < _speed), STEPS[0]))


def ticks() -> int:
    """Milliseconds on the game's clock: pygame.time.get_ticks(), but running `speed` times as fast. At 1x, never changed, it IS pygame's clock."""
    return int(_virtual + (pygame.time.get_ticks() - _real) * _speed)


def real_ms(ms: float) -> float:
    """How long to really wait for `ms` of the original's time."""
    return ms / _speed


def silent() -> bool:
    return _speed >= MUTE_FROM
