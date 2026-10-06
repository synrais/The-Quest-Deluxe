"""Pictures for the Studio's lists and views: thumbnails of the pack's sprites, cached, as Tk images."""
from __future__ import annotations

import pygame

from editor.art import Art, EGA, photo

from .theme import C


def rgb(hexcolour: str) -> tuple:
    h = hexcolour.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Pictures:
    """Thumbnails and map drawing for a project (wraps editor.art.Art)."""

    def __init__(self, project):
        self.project = project
        self.art = Art(project)
        self._thumbs: dict = {}

    def reload(self):
        self.art.reload()
        self._thumbs.clear()

    def forget(self, layer: str, v: int):
        self.art.forget(layer, v)
        for k in [k for k in self._thumbs if k[0] == layer and k[1] == v]:
            del self._thumbs[k]

    def surface(self, layer: str, v: int, size: int):
        """The picture scaled to size (a pygame surface, or None)."""
        return self.art.tile(layer, v, size) if v or layer == 'gold' else None

    def thumb(self, layer: str, v: int, size: int = 40, bg: str | None = 'raised', frame=False):
        """A Tk image: the picture on a dark square. Floors are shown as the floor, others on the panel colour."""
        key = (layer, v, size, bg, frame, C['panel'])
        if key not in self._thumbs:
            s = pygame.Surface((size, size))
            s.fill(rgb(C[bg]) if bg else (0, 0, 0))
            if v or layer == 'gold':
                img = self.art.tile(layer, v, size)
                if img is not None:
                    s.blit(img, (0, 0))
                else:
                    pygame.draw.line(s, (120, 60, 60), (3, 3), (size - 4, size - 4), 2)
            else:
                pygame.draw.line(s, (200, 60, 60), (3, 3), (size - 4, size - 4), 2)
                pygame.draw.line(s, (200, 60, 60), (size - 4, 3), (3, size - 4), 2)
            if frame:
                pygame.draw.rect(s, rgb(C['line']), (0, 0, size, size), 1)
            self._thumbs[key] = photo(s)
        return self._thumbs[key]

    def bag_thumb(self, v: int, size: int = 40):
        key = ('bag', v, size, C['panel'])
        if key not in self._thumbs:
            img = self.project.picture('bag', v)
            s = pygame.Surface((size, size))
            s.fill(rgb(C['raised']))
            if img is not None:
                s.blit(pygame.transform.scale(img, (size, size)), (0, 0))
            self._thumbs[key] = photo(s)
        return self._thumbs[key]

    def colour_chip(self, ega: int, size: int = 16):
        key = ('chip', ega, size)
        if key not in self._thumbs:
            s = pygame.Surface((size, size))
            s.fill(EGA[ega % 16])
            pygame.draw.rect(s, rgb(C['line']), (0, 0, size, size), 1)
            self._thumbs[key] = photo(s)
        return self._thumbs[key]

    def level_thumb(self, grid, width: int = 160):
        """The whole 100 x 100 level as a small map: floors and walls in colour."""
        key = ('level', id(grid), width)
        side = width
        s = pygame.Surface((100, 100))
        floors = {f['id']: f for f in self.project.tiles.get('floors', [])}
        walls = {w['id']: w for w in self.project.tiles.get('walls', [])}
        for x in range(1, 101):
            for y in range(1, 101):
                fl, wa, it, mo, go, de = grid.sq[x][y]
                col = self._tile_colour(floors, fl, (0, 120, 0))
                if wa:
                    col = self._tile_colour(walls, wa, (110, 110, 110), wall=True)
                if mo > 0:
                    col = (230, 70, 70)
                elif it:
                    col = (250, 220, 80)
                s.set_at((x - 1, y - 1), col)
        return photo(pygame.transform.scale(s, (side, side)))

    @staticmethod
    def _tile_colour(table, v, default, wall=False):
        t = table.get(v)
        if t and t.get('map_colour'):
            c = t['map_colour'][0]
            return EGA[c % 16]
        if wall and t and not t.get('solid', True):
            return (140, 100, 40)
        return default
