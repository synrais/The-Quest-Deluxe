"""What the hero wears, drawn on him on the map, pixel by pixel.

The hero is a base picture (engine/assets/hero_base.png, or a class's sprites/heroes/<class number>.png): a hooded figure
wearing nothing, 40 x 40. On top of it, each item's own picture (the one in the bag or the one on the map, `worn_from`),
laid on pixel for pixel, moved as the item says (`worn_dx`, `worn_dy`, `worn_rotate`), behind him or in front (`worn_behind`,
a cape is behind). A weapon is in his RIGHT hand when it is in the weapon slot (the screen's left, as the inventory shows
it) and in his LEFT hand in the off-hand slot (the screen's right); an item in the hand it was not made for is drawn
flipped. A cape can turn his hood a colour (`hood_colour`). An amulet only colours the yellow pixel of the clasp under his
chin. An item's own Worn on the hero picture, sprites/worn/<item number>.png (40 x 40, see-through), is used instead of
its pictures, and `show_on_hero: false` leaves an item off. No tkinter here: the editor shows the same drawings."""
from __future__ import annotations

import os
from collections import Counter

import pygame

from .bgi import EGA

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


def cape_like(row: dict) -> bool:
    """An armour item that is a cape: marked `cape` true or false in the Items tab, else by its name (cape, cloak, shawl,
    robe, mantle). It starts out behind the hero, shown by its bag picture."""
    if row.get('cape') is not None:
        return row.get('type') == 'armour' and bool(row['cape'])
    name = f'{row.get("name", "")} {row.get("bag_name", "")}'.lower()
    return row.get('type') == 'armour' and has(name, 'cape', 'cloak', 'shawl', 'robe', 'mantle')


def hood_colour(row) -> int | None:
    """The colour a cape turns the hero's hood (`hood_colour`, 0-15), or None: his own."""
    if row and cape_like(row) and row.get('hood_colour') is not None:
        return int(row['hood_colour']) % 16
    return None


_hood = []


def hood_mask():
    """Where the hood is: the pixels of the base picture in the hood's colour."""
    if not _hood:
        src = pygame.image.load(os.path.join(HERE, 'assets', 'hero_base.png'))
        _hood.extend((x, y) for x in range(src.get_width()) for y in range(src.get_height())
                     if tuple(src.get_at((x, y)))[:3] == BASE_COLOUR)
    return _hood


def with_hood(picture, colour: int):
    """A copy of a hero's picture (painted, any class) with its hood in an EGA colour."""
    out = pygame.Surface(picture.get_size(), pygame.SRCALPHA)
    out.blit(picture, (0, 0))
    for x, y in hood_mask():
        if x < out.get_width() and y < out.get_height() and out.get_at((x, y))[3]:
            out.set_at((x, y), (*EGA[colour], 255))
    return out


def source_of(row: dict) -> str:
    """Which of an item's pictures is put on the hero: `worn_from` 'bag' (its inventory picture) or 'ground' (its picture on
    the map); not said: a cape by its bag picture, anything else by its picture on the ground."""
    return row['worn_from'] if row.get('worn_from') in ('bag', 'ground') else ('bag' if cape_like(row) else 'ground')


def behind_of(row: dict) -> bool:
    """Is the item drawn behind his body? `worn_behind` true / false; not said: a cape is, anything else is in front."""
    return bool(row['worn_behind']) if row.get('worn_behind') is not None else cape_like(row)


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


def has(name: str, *words) -> bool:
    return any(w in name for w in words)


def clasp_colour(row: dict, c: int) -> int:
    """The colour of the clasp under his chin: the amulet's `clasp_colour`, else its colour on the hero."""
    return int(row['clasp_colour']) % 16 if row.get('clasp_colour') is not None else (c if c != 0 else 8)


def draw_amulet(layer, row: dict, c: int):
    """The yellow pixel of the clasp under his chin takes the amulet's colour."""
    layer.set_at(CLASP, (*EGA[clasp_colour(row, c)], 255))


CLASP_WHEN = {'always': lambda s: True,
              'low_life': lambda s: s['mlife'] > 0 and s['life'] * 4 <= s['mlife'],
              'hurt': lambda s: s['life'] < s['mlife'],
              'poisoned': lambda s: s['poisoned'] > 0,
              'shielded': lambda s: s['shield'] > 0,
              'invisible': lambda s: s['invisible'] > 0,
              'powered': lambda s: s['powered'] > 0}


def clasp_now(row: dict, c: int, state: dict, ticks: int) -> int:
    """The clasp's colour right now. `clasp_when` (always, low_life, hurt, poisoned, shielded, invisible, powered) says when
    it changes to `clasp_alt`: `clasp_mode` 'flash' alternates between the two (about three times a second), 'change'
    (the default) just shows the other colour while it holds. state: life, mlife, poisoned, shield, invisible, powered."""
    base = clasp_colour(row, c)
    when = CLASP_WHEN.get(row.get('clasp_when'))
    if when is None or row.get('clasp_alt') is None or not when(state):
        return base
    alt = int(row['clasp_alt']) % 16
    if row.get('clasp_mode') == 'flash' and (ticks // 160) % 2 == 0:
        return base
    return alt


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


def picture_layer(slot: str, row: dict, bag_picture, ground_picture) -> pygame.Surface | None:
    """An item's own picture laid on the hero pixel for pixel: the one the item says (source_of): its inventory (bag) picture
    or its picture on the ground. None if it has none (or it is an amulet, which only colours the clasp)."""
    if slot == 'amulet':
        return None
    if source_of(row) == 'bag':
        return keyed(bag_picture) if bag_picture is not None else None
    if ground_picture is None:
        return None
    layer = pygame.Surface(ground_picture.get_size(), pygame.SRCALPHA)
    layer.blit(ground_picture, (0, 0))
    return layer


def overlay(slot: str, row: dict, bag_picture, ground_picture=None) -> pygame.Surface | None:
    """The 40 x 40 layer for an item in a place ('armour', 'helmet', 'amulet', 'weapon', 'offhand', 'shield'): its own picture
    laid on pixel for pixel (see picture_layer), or for an amulet the clasp's pixel. The editor starts a Worn on the hero
    picture from this."""
    if slot == 'amulet':
        layer = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        draw_amulet(layer, row, colour_of(row, bag_picture))
        return layer
    return picture_layer(slot, row, bag_picture, ground_picture)


def slot_of(row: dict) -> str | None:
    """The place an item is worn, by its type: 'armour', 'helmet', 'amulet', 'weapon', 'shield' (or None)."""
    kind = row.get('type')
    return {'launcher': 'weapon'}.get(kind, kind) if kind in ('armour', 'weapon', 'launcher', 'shield', 'helmet', 'amulet') else None


PLACES = ('armour', 'helmet', 'amulet', 'weapon', 'shield')        # where an item can be worn (an offhand weapon: 'shield')


HANDS = {'weapon': 'right', 'shield': 'left'}      # the bag slots: the weapon slot is his RIGHT hand (the screen's left, where
                                                     # the inventory shows it), the off-hand slot his LEFT hand (the screen's right)


def natural_hand(row: dict) -> str | None:
    """The hand an item is made for: a weapon or launcher the right, a shield the left (None: not held)."""
    return {'weapon': 'right', 'launcher': 'right', 'shield': 'left'}.get(row.get('type'))


def mirrored(row: dict, place: str) -> bool:
    """Is the item in the other hand from the one it is made for? Then it is drawn flipped, where it was."""
    return place in HANDS and natural_hand(row) is not None and natural_hand(row) != HANDS[place]


def placed(layer, row: dict):
    """A layer moved as the item says: `worn_rotate` (90, 180 or 270 degrees clockwise) turns the picture about its own
    middle, then `worn_dx` and `worn_dy` slide it that many pixels (right and down). Untouched when the item says nothing."""
    if layer is None:
        return None
    dx, dy = int(row.get('worn_dx') or 0), int(row.get('worn_dy') or 0)
    turn = int(row.get('worn_rotate') or 0) % 360
    if not (dx or dy or turn):
        return layer
    src = layer
    if turn:
        box = layer.get_bounding_rect()
        if box.width and box.height:
            part = pygame.transform.rotate(layer.subsurface(box), -turn)        # (pygame turns anticlockwise)
            src = pygame.Surface(layer.get_size(), pygame.SRCALPHA)
            src.blit(part, part.get_rect(center=box.center))
    out = pygame.Surface(layer.get_size(), pygame.SRCALPHA)
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
    if row:                                                        # nothing on: nothing shown
        (behind if behind_of(row) else front).append(layer(item, row, 'armour'))
    for name in ('helmet', 'amulet', 'weapon', 'shield'):
        item, row = parts.get(name, (0, {}))
        if row:
            one = layer(item, row, ('shield' if row.get('type') == 'shield' else 'offhand') if name == 'shield' else name)
            if one is not None and mirrored(row, name):
                one = pygame.transform.flip(one, True, False)      # in the other hand: the same, the other way round
            (behind if behind_of(row) else front).append(one)
    return [b for b in behind if b is not None], [f for f in front if f is not None]


def dress(colour: int, parts: dict, picture_of, own_of=lambda item: None, base_path=None, base=None) -> pygame.Surface:
    """The whole hero wearing parts (see layers): a 40 x 40 picture, see-through round him. The editor's previews use it."""
    behind, front = layers(colour, parts, picture_of, own_of)
    hood = hood_colour(parts.get('armour', (0, {}))[1])
    if hood is not None:
        if base is not None:
            base = with_hood(base, hood)
        else:
            colour = hood
    out = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    for layer in behind:
        out.blit(layer, (0, 0))
    out.blit(base if base is not None else base_hero(colour, base_path), (0, 0))
    for layer in front:
        out.blit(layer, (0, 0))
    return out
