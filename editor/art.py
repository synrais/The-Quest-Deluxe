"""The pack's pictures for the editor: map views and palette icons are composed with pygame (as the
game draws them: floor, decoration, wall, gold, item, creature) and handed to Tk as PPM images."""
from __future__ import annotations

import os
import tkinter as tk

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame  # noqa: E402

pygame.init()

EGA = [(0, 0, 0), (0, 0, 168), (0, 168, 0), (0, 168, 168), (168, 0, 0), (168, 0, 168), (168, 84, 0),
       (168, 168, 168), (84, 84, 84), (84, 84, 252), (84, 252, 84), (84, 252, 252), (252, 84, 84),
       (252, 84, 252), (252, 252, 84), (252, 252, 252)]
ORDER = ('floor', 'deco', 'wall', 'gold', 'item', 'mon')          # draw order, bottom to top
FIELD = {'floor': 0, 'wall': 1, 'item': 2, 'mon': 3, 'gold': 4, 'deco': 5}


def photo(surface: pygame.Surface) -> tk.PhotoImage:
    w, h = surface.get_size()
    return tk.PhotoImage(data=b'P6 %d %d 255\n' % (w, h) + pygame.image.tobytes(surface, 'RGB'), format='PPM')


class Art:
    def __init__(self, project):
        self.project = project
        self._src: dict = {}
        self._scaled: dict = {}
        self._icons: dict = {}

    def reload(self):
        self._src.clear()
        self._scaled.clear()
        self._icons.clear()

    def source(self, layer: str, v: int):
        key = (layer, v)
        if key not in self._src:
            if layer == 'gold':
                p = self.project.path('sprites', 'gold.png')
                p = p if os.path.exists(p) else None
            else:
                p = self.project.sprite(layer, v)
            self._src[key] = pygame.image.load(p) if p else None
        return self._src[key]

    def tile(self, layer: str, v: int, size: int):
        key = (layer, v, size)
        if key not in self._scaled:
            img = self.source(layer, v)
            if img is None:
                img = self._placeholder(layer, v)
            if img is not None and img.get_width() != size:
                img = pygame.transform.scale(img, (size, size))
            self._scaled[key] = img
        return self._scaled[key]

    @staticmethod
    def _placeholder(layer, v):
        """What the game draws when a picture is missing."""
        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        if layer == 'wall':
            pygame.draw.rect(s, EGA[8], (2, 2, 36, 36))
        elif layer == 'item':
            pygame.draw.circle(s, EGA[14], (20, 20), 6)
        elif layer == 'mon':
            pygame.draw.circle(s, EGA[12] if v > 0 else EGA[11], (20, 20), 12)
        else:
            return None
        return s

    def draw_square(self, surf, px, py, sq, size):
        surf.fill((0, 0, 0), (px, py, size, size))
        for layer in ORDER:
            v = sq[FIELD[layer]]
            if v and (layer != 'gold' or v > 0):
                img = self.tile(layer, v, size)
                if img is not None:
                    surf.blit(img, (px, py))

    def icon(self, layer: str, v: int, size: int = 24) -> tk.PhotoImage:
        """A palette icon: the picture on dark grey (floors as they are)."""
        key = (layer, v, size)
        if key not in self._icons:
            s = pygame.Surface((size, size))
            s.fill((40, 40, 40))
            if v:
                img = self.tile(layer, v, size)
                if img is not None:
                    s.blit(img, (0, 0))
            else:
                pygame.draw.line(s, (200, 60, 60), (3, 3), (size - 4, size - 4), 2)
                pygame.draw.line(s, (200, 60, 60), (size - 4, 3), (3, size - 4), 2)
            self._icons[key] = photo(s)
        return self._icons[key]
