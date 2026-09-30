"""The player's settings: settings.ini in the TheQuestDeluxe folder.

    [play]
    fixes = on        ; the original's bugs: on = fix them all, off = keep them all, pack = as the quest pack says
    sound = on        ; the PC-speaker tones
    items_on_top = on ; gold and items drawn over the creatures and the hero (the original: under)

Only a real game reads it (run_deluxe.py); a Game made without settings, as the tests make it, plays
the pack as it is, so a player's settings can't change what the tests check.
"""
from __future__ import annotations

import configparser
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the TheQuestDeluxe folder
PATH = os.path.join(ROOT, 'settings.ini')
CHOICES = {'fixes': ('on', 'off', 'pack'), 'sound': ('on', 'off'), 'items_on_top': ('on', 'off')}
DEFAULTS = {'fixes': 'pack', 'sound': None, 'items_on_top': 'off'}   # sound None: as sound.txt says


def load(path: str = PATH) -> dict:
    """settings.ini's [play] section; a missing file, section or value, or one that isn't a choice, is the
    default."""
    out = dict(DEFAULTS)
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    try:
        cp.read(path, encoding='utf-8')
    except (OSError, configparser.Error):
        return out
    if cp.has_section('play'):
        for key, choices in CHOICES.items():
            v = cp.get('play', key, fallback='').strip().lower()
            if v in choices:
                out[key] = v
    return out


def fix_override(settings: dict | None):
    """What Pack.fixed() is told: True (fix all), False (fix none) or None (as the pack says)."""
    return {'on': True, 'off': False}.get((settings or {}).get('fixes'))
