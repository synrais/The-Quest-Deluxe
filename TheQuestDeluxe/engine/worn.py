"""What the hero wears, drawn on him on the map, pixel by pixel.

The hero is a base picture (engine/assets/hero_base.png, or sprites/hero_base.png in a pack): a hooded figure wearing
nothing, 40 x 40, its hood in the colour of his class. On top of it:

  a CAPE (an item marked as one in the Items tab, or named cape, cloak, shawl or robe) is drawn BEHIND him, centred as the
    normal cape is; the heroes wear a cape in their class's colour until they put one on. A pixel-perfect copy of the
    normal cape in the item's colour, unless the item has a drawing of its own (sprites/worn/<item number>.png)
  armour and helmets go directly on his body and head
  an amulet colours the pixel under his chin that is yellow on the clasp
  a weapon is held upright in his right hand (the screen's left) and a shield on his left arm (the screen's right), a sword,
    dagger, rapier, club, staff, spear, mace, axe, bow or sling by its name, in the way the Knight and the NPCs hold theirs

The colour of an item is its `worn_colour` (an EGA colour, 0-15) or else the commonest colour of its bag picture. Any
item's drawing of its own, sprites/worn/<item number>.png (40 x 40, see-through), is used instead of the drawing made here,
and `show_on_hero: false` leaves an item off. No tkinter here: the editor shows the same drawings."""
from __future__ import annotations

import os
from collections import Counter

import pygame

from .bgi import BGI, EGA

TILE = 40
HERE = os.path.dirname(os.path.abspath(__file__))
BASE_COLOUR = (168, 0, 168)                                      # the base picture's hood: the Knight's purple
CLASP = (20, 12)                                                 # the yellow pixel of the clasp under his chin
ORDER = ('armour', 'helmet', 'amulet', 'weapon', 'shield')       # drawn on the base in this order
_base_cache: dict = {}


def base_hero(colour: int, path: str | None = None) -> pygame.Surface:
    """The hero wearing nothing (40 x 40, see-through), his hood in an EGA colour. path: a pack's own base picture."""
    key = (colour, path)
    if key not in _base_cache:
        src = pygame.image.load(path if path and os.path.exists(path) else os.path.join(HERE, 'assets', 'hero_base.png'))
        src = src.convert_alpha() if pygame.display.get_surface() else src
        layer = pygame.Surface(src.get_size(), pygame.SRCALPHA)
        layer.blit(src, (0, 0))
        for x in range(layer.get_width()):
            for y in range(layer.get_height()):
                if tuple(layer.get_at((x, y)))[:3] == BASE_COLOUR:
                    layer.set_at((x, y), (*EGA[colour], 255))
        _base_cache[key] = layer
    return _base_cache[key]


def cape_layer(colour: int) -> pygame.Surface:
    """The normal cape, drawn by the same calls as the original hero's (anim.draw_cape), in this colour: the 40 x 40
    layer that goes behind the hero."""
    from . import anim
    key = ('cape', colour)
    if key not in _base_cache:
        back = 2 if colour != 2 else 1                             # a colour the cape is not, to key out
        tmp = pygame.Surface((TILE, TILE))
        tmp.fill(EGA[back])
        anim.draw_cape(BGI(tmp), 0, 1, colour)                      # (the hero's square (1, 1) has its top at ii = 1)
        tmp.set_colorkey(EGA[back])
        layer = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        layer.blit(tmp, (0, 0))
        _base_cache[key] = layer
    return _base_cache[key]


def is_cape(row: dict) -> bool:
    """An armour-slot item that is a cape: marked `cape` in the Items tab, else by its name."""
    if row.get('cape') is not None:
        return bool(row['cape'])
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    return row.get('type') == 'armour' and has(name, 'cape', 'cloak', 'shawl', 'robe', 'mantle')


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
    """Directly on his head: over the hood's top down to his brow (his eyes are on row 8), in the item's colour."""
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    if has(name, 'halo'):
        pygame.draw.ellipse(layer, EGA[14], (15, 0, 11, 5), 1)                       # a ring over his head
        return
    c = c if c != 0 else 8
    dark = 8 if c != 8 else 0
    pygame.draw.ellipse(layer, EGA[c], (16, 2, 9, 7))                                # the dome over his hood
    rect(layer, c, 16, 5, 9, 2)                                                      # down to his brow
    rect(layer, dark, 16, 7, 9, 1)                                                   # the rim, above his eyes
    rect(layer, c, 17, 8, 1, 4)                                                      # cheek guards down the sides of his face
    rect(layer, c, 23, 8, 1, 4)
    rect(layer, 15 if c != 15 else 7, 18, 3, 3, 1)                                   # a shine
    if has(name, 'sheep', 'wool'):
        for px, py in ((17, 4), (20, 2), (23, 4), (18, 6), (22, 6)):
            layer.set_at((px, py), EGA[15])


def draw_amulet(layer, row: dict, c: int):
    """The yellow pixel of the clasp under his chin takes the amulet's colour."""
    layer.set_at(CLASP, (*EGA[c if c != 0 else 8], 255))


def draw_armour(layer, row: dict, c: int):
    """Directly on his body: his chest, shoulders and belt in the item's colour, plain, or a mesh for mail, or stitched leather."""
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    c = c if c != 0 else 8
    dark = 8 if c != 8 else 0
    light = 15 if c not in (15, 7) else 7
    rect(layer, c, 16, 13, 9, 2)                                                     # across his shoulders
    rect(layer, c, 17, 15, 7, 10)                                                    # his chest and belly
    rect(layer, dark, 17, 25, 7, 1)                                                  # a belt
    rect(layer, c, 17, 26, 7, 2)                                                     # down to his hips
    for y in (13, 14):
        layer.set_at((15, y), EGA[c])                                                # pauldrons
        layer.set_at((25, y), EGA[c])
    if has(name, 'chain', 'mail', 'ring'):
        for y in range(15, 25):                                                      # a mesh
            for x in range(17, 24):
                if (x + y) % 2:
                    layer.set_at((x, y), EGA[dark])
    elif has(name, 'leather'):
        rect(layer, dark, 20, 15, 1, 10)                                             # a seam down the front
        for y in (17, 20, 23):
            rect(layer, dark, 18, y, 2, 1)
            rect(layer, dark, 21, y, 2, 1)
    else:                                                                            # plate: a bright edge and a ridge
        rect(layer, light, 18, 15, 1, 9)
        rect(layer, dark, 20, 15, 1, 10)


def cloak_colour(armour_row, bag_picture):
    """The colour of a cape item (None if the item is not one)."""
    return None if not armour_row or not is_cape(armour_row) else colour_of(armour_row, bag_picture)


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


def picture_layer(slot: str, bag_picture, ground_picture) -> pygame.Surface | None:
    """An item's own pictures laid on the hero pixel for pixel: a CAPE takes its inventory (bag) picture, anything else its
    picture on the ground. None if it has none (or it is an amulet, which only colours the clasp)."""
    if slot == 'cape':
        return keyed(bag_picture) if bag_picture is not None else None
    if slot == 'amulet' or ground_picture is None:
        return None
    layer = pygame.Surface(ground_picture.get_size(), pygame.SRCALPHA)
    layer.blit(ground_picture, (0, 0))
    return layer


def overlay(slot: str, row: dict, bag_picture, ground_picture=None) -> pygame.Surface | None:
    """The 40 x 40 layer for an item in a place ('cape', 'armour', 'helmet', 'amulet', 'weapon', 'offhand', 'shield'), or
    None: the item's own pictures laid on pixel for pixel (a cape its inventory picture, anything else its picture on the
    ground), or where it has none a drawing made here (the weapon and the shield where the Knight's sword and shield are,
    one row down: the original hero's drawing starts at row 1). The editor starts a Worn on the hero picture from this."""
    own = picture_layer('shield' if slot == 'offhand' and row.get('type') == 'shield' else slot, bag_picture, ground_picture)
    if own is not None:
        return own
    layer = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    c = colour_of(row, bag_picture)
    if slot == 'cape':
        return cape_layer(c)
    if slot in ('weapon', 'offhand', 'shield'):
        hands = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        if slot == 'weapon' or (slot == 'offhand' and row.get('type') in ('weapon', 'launcher')):
            draw_weapon(hands, row, c, dx=15 if slot == 'offhand' else 0)
        else:
            draw_shield(hands, row, c)
        layer.blit(hands, (0, 1))
        return layer
    if slot == 'armour':
        draw_armour(layer, row, c)
    elif slot == 'helmet':
        draw_helmet(layer, row, c)
    elif slot == 'amulet':
        draw_amulet(layer, row, c)
    else:
        return None
    return layer


def slot_of(row: dict) -> str | None:
    """The place an item is worn, by its type: 'cape', 'armour', 'helmet', 'amulet', 'weapon', 'shield' (or None)."""
    kind = row.get('type')
    if kind == 'armour':
        return 'cape' if is_cape(row) else 'armour'
    return {'launcher': 'weapon'}.get(kind, kind) if kind in ('weapon', 'launcher', 'shield', 'helmet', 'amulet') else None


PLACES = ('armour', 'helmet', 'amulet', 'weapon', 'shield')        # where an item can be worn (an offhand weapon: 'shield')


def placed(layer, row: dict):
    """A layer moved as the item says: `worn_flip` mirrors it across the hero (left hand for right), then `worn_dx` and
    `worn_dy` slide it that many pixels (right and down). Untouched when the item says nothing."""
    if layer is None:
        return None
    dx, dy = int(row.get('worn_dx') or 0), int(row.get('worn_dy') or 0)
    flip = bool(row.get('worn_flip'))
    if not (dx or dy or flip):
        return layer
    size = layer.get_size()
    src = pygame.transform.flip(layer, True, False) if flip else layer
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.blit(src, (dx, dy))
    return out


def layers(colour: int, parts: dict, picture_of, own_of=lambda item: None):
    """What goes on the hero, as (behind, front) lists of 40 x 40 layers. parts: {'armour': (item, row), 'helmet': ...,
    'amulet': ..., 'weapon': ..., 'shield': ...} for what he wears (an armour-slot item may be a cape). picture_of(item)
    gives (bag picture, ground picture); own_of(item) an item's own Worn on the hero picture, if it has one. Behind him
    goes his cape (the one he wears, or the cape of his class's colour), in front of him his armour, helmet, the clasp, his
    weapon and his shield."""
    def layer(item, row, place):
        own = own_of(item)
        if own is None:
            bag, ground = picture_of(item)
            own = overlay(place, row, bag, ground)
        return placed(own, row)
    behind, front = [], []
    item, row = parts.get('armour', (0, {}))
    place = slot_of(row) if row else None
    if place == 'cape':
        behind.append(layer(item, row, 'cape'))
    else:
        behind.append(cape_layer(colour))                          # nothing on: the cape of his class
        if place == 'armour':
            (behind if row.get('worn_behind') else front).append(layer(item, row, 'armour'))
    for name in ('helmet', 'amulet', 'weapon', 'shield'):
        item, row = parts.get(name, (0, {}))
        if row:
            one = layer(item, row, ('shield' if row.get('type') == 'shield' else 'offhand') if name == 'shield' else name)
            (behind if row.get('worn_behind') else front).append(one)
    return [b for b in behind if b is not None], [f for f in front if f is not None]


def dress(colour: int, parts: dict, picture_of, own_of=lambda item: None, base_path=None) -> pygame.Surface:
    """The whole hero wearing parts (see layers): a 40 x 40 picture, see-through round him. The editor's previews use it."""
    behind, front = layers(colour, parts, picture_of, own_of)
    out = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    for layer in behind:
        out.blit(layer, (0, 0))
    out.blit(base_hero(colour, base_path), (0, 0))
    for layer in front:
        out.blit(layer, (0, 0))
    return out
