"""What the hero wears, shown on him on the map: each worn item's picture laid over the hero.

An item can have its own picture for it, sprites/worn/<item number>.png (40 x 40, see-through round the item, drawn
over the hero's own picture), made in the editor's painter. Without one, a small copy of the item's map picture is
placed where it is worn: a weapon in the right hand, a shield on the left arm, a helmet on the head, armour on the
chest, an amulet at the neck. An item with `show_on_hero: false` is left off."""
from __future__ import annotations

import pygame

TILE = 40
# item type -> (width, height, x, y) of the small copy on the 40 x 40 square
PLACE = {'weapon': (14, 16, 25, 19), 'launcher': (14, 16, 25, 19), 'shield': (12, 12, 1, 21),
         'helmet': (12, 10, 14, 0), 'armour': (16, 14, 12, 15), 'amulet': (6, 6, 17, 15)}
ORDER = ('armour', 'helmet', 'amulet', 'weapon', 'shield')        # drawn in this order, the last on top


def keyed(bag_picture) -> pygame.Surface:
    """A bag picture (a 40 x 40 cell: a one pixel frame round a plain background) with the frame and the background
    see-through, the background being the colour just inside the frame."""
    pic = bag_picture.convert_alpha() if pygame.display.get_surface() else bag_picture.copy()
    back = pic.get_at((4, 4))
    layer = pygame.Surface(pic.get_size(), pygame.SRCALPHA)
    layer.blit(pic, (0, 0))
    w, h = pic.get_size()
    for x in range(w):
        for y in range(h):
            if x in (0, w - 1) or y in (0, h - 1) or layer.get_at((x, y))[:3] == back[:3]:
                layer.set_at((x, y), (0, 0, 0, 0))
    return layer


def auto_overlay(kind: str, picture, bag_picture=None) -> pygame.Surface | None:
    """The 40 x 40 layer for an item worn in this place, small, from its bag picture (the upright icon, background
    removed) or else its map picture; None if there is no picture or no place."""
    place = PLACE.get(kind)
    if place is None:
        return None
    src = keyed(bag_picture) if bag_picture is not None else picture
    if src is None:
        return None
    w, h, x, y = place
    layer = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    src = src if src.get_size() == (TILE, TILE) else pygame.transform.scale(src, (TILE, TILE))
    layer.blit(pygame.transform.scale(src, (w, h)), (x, y))
    return layer


def slot_order(kind_of_slot: dict) -> list:
    """The slots that hold a wearable, in drawing order: kind_of_slot maps item type -> slot."""
    return [kind_of_slot[k] for k in ORDER if k in kind_of_slot]
