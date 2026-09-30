"""FPS mode: the hero's weapon in view (Deluxe).

The weapon he holds (the bag's weapon cell) stands at the bottom right of the view, big and partly
off the edge: its bag picture with the cell's frame and grey cut away, tilted, and
scaled up in whole EGA pixels. An item's "fps_turn" turns its picture that many degrees (anticlockwise)
to stand it up; a pack can also draw its own: sprites/hands/<item>.png (upright, the grip at the
bottom). With nothing in hand, nothing shows.

It moves with the hero: a bob as he steps, and when he attacks a swing (swords, axes, clubs...), a
thrust (spears, pikes, lances: kind 3) or a draw and release (bows and slings). An item's
"fps_attack" ("swing", "thrust" or "shoot") overrides that. Only the picture moves: the rules don't
know about it.
"""
from __future__ import annotations

import math
import os

import pygame


SCALE = 5                 # whole pixels: the view is 400 x 400, a 40-pixel picture stands 200 high
GRIP = (300, 405)         # where the grip sits: the bottom right, just below the view's edge
TILT = -22                # degrees; a melee weapon leans in toward the middle
ATTACK_MS = {'swing': 280, 'thrust': 240, 'shoot': 320}
STEP_BOB = 7              # pixels up at the middle of a step
BAG_GREY = (84, 84, 84)


def attack_kind(item: dict) -> str:
    if item.get('fps_attack') in ATTACK_MS:
        return item['fps_attack']
    if item.get('type') == 'launcher':
        return 'shoot'
    return 'thrust' if item.get('kind') == 3 else 'swing'


def cut_out(cell: pygame.Surface) -> pygame.Surface:
    """A bag cell without its black frame and the grey around the item (inside a bow's string too),
    cropped to the item."""
    s = cell.convert_alpha()
    w, h = s.get_size()
    for x in range(w):
        for y in range(h):
            if x in (0, w - 1) or y in (0, h - 1):
                s.set_at((x, y), (0, 0, 0, 0))
    grey = pygame.mask.from_threshold(s, BAG_GREY + (255,), (1, 1, 1, 255))
    grey.to_surface(s, setcolor=(0, 0, 0, 0), unsetcolor=None)
    box = s.get_bounding_rect()
    return s.subsurface(box).copy() if box.w and box.h else s


class Hands:
    def __init__(self, pack, sprites):
        self.pack, self.sprites = pack, sprites
        self._pictures: dict[int, pygame.Surface | None] = {}

    def picture(self, item: int):
        """The weapon upright, grip at the bottom, at 1x (None: no picture)."""
        if item not in self._pictures:
            pic = None
            own = self.pack.path('sprites', 'hands', f'{item}.png')
            if os.path.exists(own):
                pic = pygame.image.load(own).convert_alpha()
            elif item in self.sprites.bag:
                pic = cut_out(self.sprites.bag[item])
                turn = self.pack.item(item).get('fps_turn')
                if turn is None and pic.get_width() > pic.get_height() * 1.3:
                    turn = 90                                          # plainly lying down
                if turn:
                    pic = pygame.transform.rotate(pic, turn)
            self._pictures[item] = pic
        return self._pictures[item]

    def pose(self, game, now: int):
        """(dx, dy, extra tilt) of the hand: the step's bob, then the attack."""
        dx = dy = da = 0.0
        cam = getattr(game.renderer, '_cam', None)
        if cam:
            t = (now - cam['t0']) / 140
            (x0, y0, _), (x1, y1, _) = cam['from'], cam['goal']
            if 0 <= t < 1 and (x0, y0) != (x1, y1):
                dy -= math.sin(t * math.pi) * STEP_BOB
                dx += math.sin(t * 2 * math.pi) * 3
        swing = getattr(game, 'swing', None)
        if swing:
            kind, t0 = swing
            u = (now - t0) / ATTACK_MS[kind]
            if 0 <= u < 1:
                s = math.sin(u * math.pi)
                if kind == 'swing':
                    da, dx, dy = da - 50 * s, dx - 120 * s, dy - 30 * s
                elif kind == 'thrust':
                    dx, dy = dx - 40 * s, dy - 70 * s
                else:                                       # shoot: drawn back, then let go
                    dy += 30 * s if u < 0.7 else -20 * math.sin((u - 0.7) / 0.3 * math.pi)
        return dx, dy, da

    def draw(self, game, scr, now: int):
        item = game.player.bag.get((12, 4), 0)
        pic = self.picture(item) if item else None
        if pic is None:
            return                                          # nothing in hand: nothing in view
        dx, dy, da = self.pose(game, now)
        shoot = attack_kind(self.pack.item(item)) == 'shoot'
        angle = (-8 if shoot else TILT) + da
        big = pygame.transform.scale(pic, (pic.get_width() * SCALE, pic.get_height() * SCALE))
        turned = pygame.transform.rotate(big, angle)
        # the grip (the bottom middle of the upright picture) lands on GRIP, moved by the pose
        a = math.radians(angle)
        vx, vy = 0, big.get_height() / 2                    # centre -> grip, before turning
        rx, ry = vx * math.cos(a) + vy * math.sin(a), -vx * math.sin(a) + vy * math.cos(a)
        gx, gy = GRIP[0] + dx - (40 if shoot else 0), GRIP[1] + dy
        scr.blit(turned, (gx - rx - turned.get_width() / 2, gy - ry - turned.get_height() / 2))
