"""FPS mode: the hero's bust in the panel (Deluxe).

In the view from above the hero himself shows his state (guy2(): the eye colours); in FPS mode he can't
be seen, so his bust stands in the panel, right of the coins and just above the right-hand key, with no
frame. The picture is engine/assets/bust.png (a pack can have its own: sprites/bust.png), scaled up in
whole pixels, and three of its colours stand for something:

  - red (EGA 4), the hood: the class colour;
  - white (EGA 15), the eyes: guy2()'s eye colour (green when poisoned, dark red with the killer
    switch, light red under a Berserker potion, white otherwise); invisible, only the eyes show;
  - yellow (EGA 14), the necklace: the colour of the amulet he wears (black, unseen, without one).
"""
from __future__ import annotations

import os
from collections import Counter

import pygame

from .bgi import EGA

SCALE = 3
# right of the coins (which end at x 550) and above the right-hand key (its ring's top is y 214);
# centred over that key and evenly spaced between the gold's number (to y 172) and the key
AT = (597, 193)                   # the middle of the bust
HOOD, EYES, NECKLACE = 4, 15, 14
BAG_BACK = {(84, 84, 84), (0, 0, 0)}


def eye_colour(h, st) -> int:
    """guy2()'s eye colour, in its order."""
    if h.poisoned and h.invisible <= 0:
        return 10
    if st.killer:
        return 4
    if st.powboost > 0:
        return 12
    return 15


def ega_index(rgb) -> int | None:
    return next((n for n, c in enumerate(EGA) if tuple(c[:3]) == tuple(rgb[:3])), None)


class Face:
    def __init__(self, pack, sprites):
        self.pack, self.sprites = pack, sprites
        path = pack.sprite('bust.png') or os.path.join(os.path.dirname(__file__), 'assets', 'bust.png')
        self.picture = pygame.image.load(path).convert_alpha()
        self._amulets: dict[int, int] = {}
        self._cache_key, self._cache = None, None

    def amulet_colour(self, item: int) -> int:
        """The colour an amulet is drawn in: the commonest colour of its bag picture that isn't the
        cell's grey or black, white only when there's nothing else (the Pearl Necklace)."""
        if item not in self._amulets:
            cell = self.sprites.bag.get(item)
            colour = NECKLACE
            if cell is not None:
                seen = Counter(tuple(cell.get_at((x, y)))[:3] for x in range(1, cell.get_width() - 1)
                               for y in range(1, cell.get_height() - 1))
                ranked = [c for c, _ in seen.most_common() if c not in BAG_BACK]
                coloured = [c for c in ranked if c != tuple(EGA[15][:3])]
                pick = (coloured or ranked or [None])[0]
                colour = ega_index(pick) if pick else NECKLACE
            self._amulets[item] = colour if colour is not None else NECKLACE
        return self._amulets[item]

    def state(self, game) -> tuple:
        p, st = game.player, game.status
        h = p.hero
        amulet = p.bag.get((14, 6), 0)
        return (self.pack.classes.get(h.type, {}).get('look', {}).get('colour', HOOD),
                eye_colour(h, st), self.amulet_colour(amulet) if amulet else 0, h.invisible > 0)

    def render(self, hood, eyes, necklace, invisible) -> pygame.Surface:
        src = self.picture
        out = pygame.Surface(src.get_size(), pygame.SRCALPHA)
        swap = {HOOD: hood, EYES: eyes, NECKLACE: necklace}
        for x in range(src.get_width()):
            for y in range(src.get_height()):
                c = src.get_at((x, y))
                if c.a == 0:
                    continue
                n = ega_index(c)
                if invisible and n != EYES:
                    continue                                 # invisible: only the eyes
                out.set_at((x, y), EGA[swap.get(n, n)] if n is not None else c)
        return pygame.transform.scale(out, (src.get_width() * SCALE, src.get_height() * SCALE))

    def draw(self, game, scr):
        key = self.state(game)
        if key != self._cache_key:
            self._cache_key, self._cache = key, self.render(*key)
        pic = self._cache
        scr.blit(pic, (AT[0] - pic.get_width() // 2, AT[1] - pic.get_height() // 2))
