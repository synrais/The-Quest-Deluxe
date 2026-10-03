"""The player's settings: settings.ini in the TheQuestDeluxe folder.

    [play]
    fixes = on        ; the original's bugs: on = fix them all, off = keep them all, pack = as the quest pack says
    sound = on        ; the PC-speaker tones
    items_on_top = on ; gold and items drawn over the creatures and the hero (the original: under)
    floating_numbers = off ; FPS mode: damage, "miss" and the like rising off whoever took them
    render_quality = normal ; the whole game: normal, high or ultra (finer FPS view and smooth scaling)
    smooth_scaling = off ; scale the picture to the window smoothly (on) or in whole pixels (off)
    fps_quality = normal ; FPS mode: low, normal, high, ultra or max (how finely the view is drawn)
    fps_view_distance = level ; FPS mode: level (as each level says) or 2-30 squares (never less than the level's)
    fps_dither = ordered ; FPS mode, the fog: ordered, fine, smooth (a blend) or off
    fps_fog_start = 45 ; FPS mode: how far the fog fade starts, in percent of the view distance (100: only at the edge)
    fps_texture_filter = off ; FPS mode: average the far ground, walls and things (on) or skip pixels (off)
    fps_transition = on ; F: the map zooms in on the hero and drops into the FPS view (on), or it just switches (off)

Only a real game reads it (run_deluxe.py); a Game made without settings, as the tests make it, plays
the pack as it is, so a player's settings can't change what the tests check.
"""
from __future__ import annotations

import configparser
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the TheQuestDeluxe folder
PATH = os.path.join(ROOT, 'settings.ini')
CHOICES = {'fixes': ('on', 'off', 'pack'), 'sound': ('on', 'off'), 'items_on_top': ('on', 'off'),
           'floating_numbers': ('on', 'off'), 'fps_quality': ('low', 'normal', 'high', 'ultra', 'max'),
           'fps_dither': ('ordered', 'fine', 'smooth', 'off'), 'smooth_scaling': ('on', 'off'),
           'fps_texture_filter': ('on', 'off'), 'fps_transition': ('on', 'off'),
           'render_quality': ('normal', 'high', 'ultra')}
DEFAULTS = {'fixes': 'pack', 'sound': None, 'items_on_top': 'off',   # sound None: as sound.txt says
            'floating_numbers': 'off', 'fps_quality': 'normal', 'fps_dither': 'ordered',
            'fps_view_distance': 'level', 'smooth_scaling': 'off', 'render_quality': 'normal',
            'fps_texture_filter': 'off', 'fps_fog_start': 45, 'fps_transition': 'on'}
QUALITY_ORDER = ('low', 'normal', 'high', 'ultra', 'max')
RENDER_QUALITY = {'high': 'high', 'ultra': 'max'}                      # what each level of render_quality means


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
        v = cp.get('play', 'fps_view_distance', fallback='').strip().lower()
        if v.isdigit() and 2 <= int(v) <= 30:
            out['fps_view_distance'] = int(v)
        v = cp.get('play', 'fps_fog_start', fallback='').strip()
        if v.isdigit() and 0 <= int(v) <= 100:
            out['fps_fog_start'] = int(v)
    return resolve_quality(out)


def resolve_quality(out: dict) -> dict:
    """render_quality high and ultra draw the FPS view finer (never coarser than fps_quality asks). Smooth
    scaling to the window is its own switch (smooth_scaling): it blurs, so quality never turns it on."""
    asked = RENDER_QUALITY.get(out.get('render_quality'))
    if asked and QUALITY_ORDER.index(asked) > QUALITY_ORDER.index(out.get('fps_quality', 'normal')):
        out['fps_quality'] = asked
    return out


def fix_override(settings: dict | None):
    """What Pack.fixed() is told: True (fix all), False (fix none) or None (as the pack says)."""
    return {'on': True, 'off': False}.get((settings or {}).get('fixes'))
