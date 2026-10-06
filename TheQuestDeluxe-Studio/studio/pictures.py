"""Pictures for the Studio's lists and views: thumbnails of the pack's sprites, cached, as Tk images."""
from __future__ import annotations

import pygame

from studio.art import Art, EGA, photo

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
        side = width
        s = pygame.Surface((100, 100))
        x0 = y0 = 101
        x1 = y1 = 0
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
                if wa or it or mo or de or go > 0:
                    x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
        if x1 - x0 < 9 or y1 - y0 < 9:                                  # nothing much on it: the whole level
            return photo(pygame.transform.scale(s, (side, side)))
        w, h = x1 - x0 + 1, y1 - y0 + 1                                 # a level made smaller than 100 x 100: just the part that is used
        k = side / max(w, h)
        crop = pygame.transform.scale(s.subsurface((x0 - 1, y0 - 1, w, h)), (max(1, int(w * k)), max(1, int(h * k))))
        out = pygame.Surface((side, side))
        out.fill((8, 10, 14))
        out.blit(crop, ((side - crop.get_width()) // 2, (side - crop.get_height()) // 2))
        return photo(out)

    def level_surface(self, sq, x0, y0, w, h, scale):
        """A part of a level drawn with the real pictures, `scale` pixels a square (a pygame surface)."""
        s = pygame.Surface((w * scale, h * scale))
        tile = self.art.tile
        for x in range(x0, x0 + w):
            col = sq[x]
            for y in range(y0, y0 + h):
                fl, wa, it, mo, go, de = col[y]
                for layer, v in (('floor', fl), ('deco', de), ('wall', wa), ('gold', go), ('item', it), ('mon', mo)):
                    if v and not (layer == 'gold' and v <= 0):
                        img = tile(layer, v, scale)
                        if img is not None:
                            s.blit(img, ((x - x0) * scale, (y - y0) * scale))
        return s

    @staticmethod
    def _tile_colour(table, v, default, wall=False):
        t = table.get(v)
        if t and t.get('map_colour'):
            c = t['map_colour'][0]
            return EGA[c % 16]
        if wall and t and not t.get('solid', True):
            return (140, 100, 40)
        return default
