"""What the hero wears, drawn on him on the map, in the style of the people and creatures that carry weapons.

The hero is the cloaked figure drawn by anim.draw_guy2 (a 40 x 40 square: hood and face at the top, his cloak widening
to the ground, the Knight's sword held upright at the screen's left and his round shield on the right). Worn things
are drawn in the same places, pixel by pixel:

  armour, a cloak, a robe   the hero's CLOAK takes the colour of the item (a purple cape: a purple cloak)
  a weapon                  upright in his right hand (the screen's left), as the Knight's sword: a sword, dagger,
                            rapier, club, staff, spear, pike, mace, axe or bow, by its name and kind
  a shield                  on his left arm (the screen's right), round, small or tall, in the item's colour
  a helmet                  over his hood, in the item's colour
  an amulet                 a pendant on a chain at his neck

The colour of an item is its `worn_colour` (an EGA colour, 0-15) or else the commonest colour of its bag picture. An item
can have a picture of its own, sprites/worn/<item number>.png (40 x 40, see-through, laid over the hero), which is used
instead; `show_on_hero: false` leaves an item off. No tkinter here: the editor shows the same drawings."""
from __future__ import annotations

from collections import Counter

import pygame

from .bgi import EGA

TILE = 40
ORDER = ('shield', 'weapon', 'helmet', 'amulet')                 # drawn in this order; armour is the cloak's colour


def ega_index(rgb) -> int:
    return min(range(16), key=lambda i: sum((a - b) ** 2 for a, b in zip(EGA[i], rgb[:3])))


def dominant(bag_picture, default: int = 7) -> int:
    """The commonest colour of a bag picture, leaving out its frame, its background and black."""
    if bag_picture is None:
        return default
    w, h = bag_picture.get_size()
    back = ega_index(bag_picture.get_at((min(4, w - 1), min(4, h - 1))))
    seen = Counter(ega_index(bag_picture.get_at((x, y))) for x in range(1, w - 1) for y in range(1, h - 1))
    for colour, _ in seen.most_common():
        if colour not in (0, back):
            return colour
    return default


def colour_of(row: dict, bag_picture) -> int:
    """An item's colour on the hero: its `worn_colour`, else the commonest colour of its bag picture."""
    if row.get('worn_colour') is not None:
        return int(row['worn_colour']) % 16
    return dominant(bag_picture)


def metal(c: int) -> int:
    """A blade is bright: brown, black and dark grey become light grey."""
    return 7 if c in (0, 6, 8) else c


def has(name: str, *words) -> bool:
    return any(w in name for w in words)


def weapon_style(row: dict) -> str:
    """sword, knife, dagger, rapier, club, staff, spear, mace, axe, bow or sling: by its name, then its kind."""
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    if row.get('type') == 'launcher' or has(name, 'bow', 'sling'):
        return 'sling' if 'sling' in name else 'bow'
    for style, words in (('knife', ('knife',)), ('dagger', ('dagger',)), ('rapier', ('rapier',)),
                         ('mace', ('mace', 'morning star', 'flail')), ('axe', ('axe',)), ('club', ('club', 'hammer')),
                         ('staff', ('staff', 'wand', 'rod')), ('spear', ('spear', 'pike', 'lance', 'trident')),
                         ('cutlass', ('cutlass', 'machet', 'scimitar', 'sabre')),
                         ('sword', ('sword', 'blade'))):
        if has(name, *words):
            return style
    return {'2': 'staff', '3': 'spear', '5': 'spear'}.get(str(row.get('kind')), 'sword')


def rect(layer, c, x, y, w, h):
    pygame.draw.rect(layer, EGA[c], (x, y, w, h))


def draw_weapon(layer, row: dict, c: int, dx: int = 0):
    """The weapon held upright in the right hand (the screen's left), in the Knight's place: blade at x 12-13, crossguard
    at y 20, hilt in the hand at y 21-23. dx moves it to the other hand."""
    style, b = weapon_style(row), metal(c)
    x = 12 + dx
    long_ = has(f'{row.get("name", "")}'.lower(), 'long', 'broad', 'great', 'battle', 'doom', 'darkness', 'swift')
    if style in ('sword', 'knife', 'dagger', 'rapier', 'cutlass'):
        top = {'knife': 13, 'dagger': 11, 'rapier': 4, 'cutlass': 8, 'sword': 5 if long_ else 8}[style]
        width = 1 if style in ('knife', 'rapier') else 3 if has(row.get('name', '').lower(), 'broad') else 2
        rect(layer, b, x - (1 if width == 3 else 0), top, width, 20 - top)           # the blade
        if style == 'cutlass':
            rect(layer, b, x + 2, top - 1, 1, 4)                                     # the curve at the tip
            rect(layer, b, x + 1, top, 1, 2)
        rect(layer, 15 if b != 15 else 7, x, top, 1, 1) if style != 'knife' else None  # a shine at the tip
        guard = (x - 2, 20, 6, 1) if style in ('sword', 'cutlass') else (x - 1, 20, 4, 1)
        rect(layer, 14 if style == 'rapier' else 8 if style in ('knife', 'dagger') else b, *guard)
        rect(layer, 0, x, 21, 2, 3)                                                  # the hilt in his hand
        rect(layer, 6, x, 24, 2, 1)
    elif style == 'club':
        rect(layer, c if c not in (0, 8) else 6, x - 2, 8, 5, 9)                    # the head
        rect(layer, 0, x - 2, 11, 5, 1)
        rect(layer, 0, x - 2, 14, 5, 1)
        rect(layer, 6, x, 17, 2, 5)
        rect(layer, 0, x, 22, 2, 2)
    elif style == 'staff':
        rect(layer, 6, x, 3, 1, 28)                                                  # a long pole beside him
        rect(layer, 6, x + 1, 3, 1, 28)
        rect(layer, c if c not in (0, 6) else 11, x - 1, 1, 4, 4)                    # a knob or an orb at the top
        rect(layer, 15, x, 2, 1, 1)
    elif style == 'spear':
        rect(layer, 0, x, 7, 1, 24)                                                  # a black pole, as the spearmen carry
        rect(layer, b, x, 3, 1, 4)                                                   # the head
        rect(layer, b, x - 1, 5, 3, 1)
        rect(layer, 15 if b != 15 else 7, x, 2, 1, 1)
        if has(row.get('name', '').lower(), 'lance'):
            rect(layer, 0, x - 1, 7, 3, 1)
    elif style == 'mace':
        rect(layer, 6, x, 12, 1, 12)
        rect(layer, 0, x, 22, 1, 2)
        pygame.draw.circle(layer, EGA[b], (x, 9), 3)                                 # a spiked ball
        for sx, sy in ((x - 4, 9), (x + 4, 9), (x, 5), (x - 3, 6), (x + 3, 6), (x - 3, 12), (x + 3, 12)):
            layer.set_at((sx, sy), EGA[b])
        rect(layer, 8, x - 1, 8, 2, 2)
    elif style == 'axe':
        rect(layer, 6, x, 8, 1, 16)
        rect(layer, b, x - 4, 8, 4, 6)                                               # the blade, a half moon to one side
        rect(layer, b, x - 5, 9, 1, 4)
        rect(layer, 8, x - 1, 8, 1, 6)
        rect(layer, 0, x, 22, 1, 2)
    elif style == 'bow':
        pts = [(x - 1 + dx * 0, 6), (x - 3, 8), (x - 4, 11), (x - 4, 17), (x - 3, 20), (x - 1, 22)]
        pygame.draw.lines(layer, EGA[6], False, pts, 2)                              # the limbs
        rect(layer, 15, x - 1, 6, 1, 17)                                             # the string
        rect(layer, 0, x - 5, 13, 2, 4)                                              # his hand on the grip
    else:                                                                            # sling: a thong and a pouch
        rect(layer, 6, x, 12, 1, 9)
        pygame.draw.circle(layer, EGA[6], (x + 1, 22), 2)
        rect(layer, 0, x, 23, 2, 2)


def draw_shield(layer, row: dict, c: int):
    """The shield on his left arm (the screen's right), round as the Knight's, or tall; the item's colour inside a white rim."""
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    face, rim = (c if c not in (0, 15) else 4), 15 if c != 15 else 7
    if has(name, 'tower'):
        rect(layer, rim, 23, 11, 9, 19)
        rect(layer, face, 24, 12, 7, 17)
        rect(layer, rim, 27, 14, 1, 13)
    elif has(name, 'kite'):
        pygame.draw.polygon(layer, EGA[rim], [(23, 12), (31, 12), (31, 20), (27, 29), (23, 20)])
        pygame.draw.polygon(layer, EGA[face], [(24, 13), (30, 13), (30, 20), (27, 27), (24, 20)])
        rect(layer, rim, 27, 14, 1, 10)
    else:
        r = 3 if has(name, 'buckler') else 4 if has(name, 'small') else 5
        pygame.draw.circle(layer, EGA[rim], (26, 20), r)
        pygame.draw.circle(layer, EGA[face], (26, 20), r - 1)
        layer.set_at((26, 20), EGA[rim])
        if r >= 4:
            layer.set_at((26, 19), EGA[rim])
            layer.set_at((26, 21), EGA[rim])
            layer.set_at((25, 20), EGA[rim])
            layer.set_at((27, 20), EGA[rim])
        if has(name, 'bash'):                                                        # a spike in the middle
            rect(layer, 7, 25, 19, 2, 2)


def draw_helmet(layer, row: dict, c: int):
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    if has(name, 'halo'):
        pygame.draw.ellipse(layer, EGA[14], (15, 0, 12, 5), 1)                       # a ring over his head
        return
    c = c if c != 0 else 8
    pygame.draw.ellipse(layer, EGA[c], (16, 1, 10, 6))                               # the dome over his hood
    rect(layer, c, 16, 4, 10, 3)                                                     # down to his brow, above his eyes
    rect(layer, 8 if c != 8 else 0, 16, 6, 10, 1)                                    # the rim
    rect(layer, 15 if c != 15 else 7, 18, 2, 3, 1)                                   # a shine
    rect(layer, 8 if c != 8 else 0, 20, 4, 2, 2)                                     # a ridge down the front
    if has(name, 'sheep', 'wool'):
        for px, py in ((16, 3), (19, 2), (22, 2), (25, 3), (17, 5), (24, 5)):
            layer.set_at((px, py), EGA[15])


def draw_amulet(layer, row: dict, c: int):
    """A pendant on a chain from the clasp at his neck."""
    c = c if c != 0 else 8
    chain = 14 if c != 14 else 7
    for px, py in ((17, 12), (18, 13), (19, 14), (22, 14), (23, 13), (24, 12), (20, 15), (21, 15)):
        layer.set_at((px, py), EGA[chain])
    rect(layer, c, 19, 16, 3, 3)
    layer.set_at((20, 16), EGA[15 if c != 15 else 7])


def cloak_colour(armour_row, bag_picture):
    """The colour of the hero's cloak while he wears this armour (None: his own)."""
    return None if not armour_row else colour_of(armour_row, bag_picture)


def overlay(slot: str, row: dict, bag_picture) -> pygame.Surface | None:
    """The 40 x 40 layer for an item worn in a place ('weapon', 'offhand', 'shield', 'helmet', 'amulet'), or None. The editor
    starts a Worn on the hero picture from this."""
    layer = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    c = colour_of(row, bag_picture)
    if slot == 'weapon':
        draw_weapon(layer, row, c)
    elif slot == 'offhand':
        if row.get('type') in ('weapon', 'launcher'):
            draw_weapon(layer, row, c, dx=15)
        else:
            draw_shield(layer, row, c)
    elif slot == 'shield':
        draw_shield(layer, row, c)
    elif slot == 'helmet':
        draw_helmet(layer, row, c)
    elif slot == 'amulet':
        draw_amulet(layer, row, c)
    else:
        return None
    return layer


def auto_overlay(kind: str, picture=None, bag_picture=None, row: dict | None = None):
    """Compatibility for the editor: the layer for an item type's place from its row."""
    slot = {'launcher': 'weapon'}.get(kind, kind)
    return overlay(slot, row or {'type': kind}, bag_picture)
