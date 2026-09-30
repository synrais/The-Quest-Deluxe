"""FPS mode: the hero's face in the panel (Deluxe), in the manner of Doom's status bar.

In the view from above the hero himself shows his state (guy2(): the eyes and the Shield rings); in FPS
mode he can't be seen, so a face beside the Map box shows it:

  - the eyes in guy2()'s colours and order: green when poisoned (and visible), dark red with the
    killer switch, light red under a Berserker potion, white otherwise; the face glances about;
  - hurt as life drops: blood at two thirds, more and a grimace at one third;
  - teeth bared while the weapon in view attacks;
  - the Shield spell's yellow ring and Shield of Fire's red one round the frame;
  - invisible: only the eyes;
  - the helmet or hood in the class colour.

Drawn in code in EGA colours at twice the size, so every pack has it.
"""
from __future__ import annotations

import pygame

from .bgi import EGA

BOX = (414, 280, 60, 92)          # left of the Map box: x, y, width, height (the frame inside it)
PX = 2                            # one face pixel is 2 x 2 screen pixels

# H helmet (class colour), S skin, o outline, B brow, N nostril, M mouth; eyes are drawn on top
FACE = [
    '......HHHHHHHHHHHH......',
    '....HHHHHHHHHHHHHHHH....',
    '...HHHHHHHHHHHHHHHHHH...',
    '..HHHHHHHHHHHHHHHHHHHH..',
    '..HHHHHHHHHHHHHHHHHHHH..',
    '..HHHoSSSSSSSSSSSSoHHH..',
    '..HHoSSSSSSSSSSSSSSoHH..',
    '..HoSSBBBBSSSSSBBBBSSoH.',
    '.ooSSSSSSSSSSSSSSSSSSoo.',
    '.oSSSSSSSSSSSSSSSSSSSSo.',
    '.oSSSSSSSSSSSSSSSSSSSSo.',
    '.oSSSSSSSSSSSSSSSSSSSSo.',
    '..oSSSSSSSSSSSSSSSSSSo..',
    '..oSSSSSSSSSSSSSSSSSSo..',
    '..oSSSSSSSNSSNSSSSSSSo..',
    '..oSSSSSSSSSSSSSSSSSSo..',
    '..oSSSSSSSSSSSSSSSSSSo..',
    '...oSSSSMMMMMMMMSSSSo...',
    '...oSSSSSSSSSSSSSSSSo...',
    '....oSSSSSSSSSSSSSSo....',
    '.....oSSSSSSSSSSSSo.....',
    '......ooSSSSSSSSoo......',
    '........oooooooo........',
]
EYES = ((4, 9), (15, 9))          # each eye: 5 wide, 3 high, from this corner
BLOOD = [(5, 5), (6, 6), (6, 7), (7, 8), (18, 13), (18, 14)]            # a cut over the eye, a graze
BLOOD_MORE = [(9, 3), (10, 4), (10, 5), (17, 6), (19, 10), (19, 11), (4, 15), (5, 16), (6, 16)]
COLOURS = {'S': 6, 'o': 0, 'B': 0, 'N': 0, 'M': 0}


def eye_colour(h, st) -> int:
    """guy2()'s eye colour, in its order."""
    if h.poisoned and h.invisible <= 0:
        return 10
    if st.killer:
        return 4
    if st.powboost > 0:
        return 12
    return 15


class Face:
    def __init__(self, pack):
        self.pack = pack
        self._last_life = None
        self._ouch_until = 0

    def state(self, game, now: int) -> tuple:
        p, st = game.player, game.status
        h = p.hero
        life = h.life / h.mlife if h.mlife else 1
        if self._last_life is not None and h.life < self._last_life:
            self._ouch_until = now + 450                     # just hurt: eyes shut tight
        self._last_life = h.life
        hurt = 0 if life > 2 / 3 else 1 if life > 1 / 3 else 2
        swing = getattr(game, 'swing', None)
        attacking = bool(swing) and 0 <= now - swing[1] < 400
        glance = (now // 1300) % 4                           # 0 ahead, 1 left, 2 ahead, 3 right
        look = self.pack.classes.get(h.type, {}).get('look', {})
        return (hurt, eye_colour(h, st), now < self._ouch_until, attacking, (0, -1, 0, 1)[glance],
                h.invisible > 0, st.Shield > 0, st.fShield > 0, look.get('colour', 8) or 8)

    def draw(self, game, scr, now: int):
        hurt, eyes, ouch, attacking, glance, invisible, shield, fire, helmet = self.state(game, now)
        x0, y0, w, h = BOX
        pygame.draw.rect(scr, EGA[0], (x0 - 3, y0 - 3, w + 6, h + 6))
        pygame.draw.rect(scr, EGA[6], (x0 - 3, y0 - 3, w + 6, h + 6), 3)         # brown, as the Map box
        pygame.draw.rect(scr, EGA[15], (x0 - 3, y0 - 3, w + 6, h + 6), 1)
        if shield:
            pygame.draw.rect(scr, EGA[14], (x0 - 1, y0 - 1, w + 2, h + 2), 2)
        if fire:
            pygame.draw.rect(scr, EGA[4], (x0 + 1, y0 + 1, w - 2, h - 2), 2)
        fx = x0 + (w - len(FACE[0]) * PX) // 2
        fy = y0 + (h - len(FACE) * PX) // 2

        def dot(cx, cy, colour):
            scr.fill(EGA[colour], (fx + cx * PX, fy + cy * PX, PX, PX))
        if not invisible:
            for y, row in enumerate(FACE):
                for x, c in enumerate(row):
                    if c == 'H':
                        dot(x, y, helmet)
                    elif c in COLOURS:
                        dot(x, y, COLOURS[c])
            for x, y in BLOOD * (hurt >= 1) + BLOOD_MORE * (hurt >= 2):
                dot(x, y, 4)
            if attacking or hurt >= 2:                       # teeth bared
                for x in range(8, 16):
                    dot(x, 17, 15)
                    dot(x, 18, 0)
                for x in range(8, 16, 2):
                    dot(x, 17, 0)
        for ex, ey in EYES:
            if ouch and not invisible:
                for x in range(ex, ex + 5):                  # screwed shut
                    dot(x, ey + 1, 0)
                continue
            for x in range(ex, ex + 5):
                for y in range(ey, ey + 3):
                    dot(x, y, eyes)
            if not invisible:
                px = ex + 2 + glance
                dot(px, ey + 1, 0)
                dot(px, ey + 2, 0)
