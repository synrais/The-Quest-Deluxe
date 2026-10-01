"""FPS mode: the level seen through the hero's eyes, as a retro raycaster in the EGA colours.

The world is the same grid the map shows; only the view changes. Each square is drawn from its own
pictures:

  walls        'block'      a solid cube with the wall's picture on its four sides
               'billboard'  the picture standing up in the middle of the square (trees, boulders)
               'flat'       the picture lying on the ground (water)
  decorations  'billboard' or 'flat' (blood and bones lie flat)
  items        'small'      half size, standing on the ground
               'billboard'  full size (chests)
               'flat'       lying on the ground (stairs, teleporter pads)
  creatures    standing up, full size; gold: small

Left out, the look follows the picture: an opaque wall picture is a block, one with see-through
pixels a billboard. Floors can have a roof (a wall picture drawn overhead); elsewhere the sky shows.
The view is drawn at 200 x 200 and doubled, with dithered distance fog, like a 1990 PC game.
"""
from __future__ import annotations

import math

import pygame

from .bgi import EGA

RES = 200                                  # the view is drawn at RES x RES, then scaled up
PLANE = 0.66                               # half the width of the view plane: a 66 degree view
SCALE = RES / (2 * PLANE)                  # pixels per square at a distance of one square
T = 40                                     # picture size (a square's side in the ground image)
FACINGS = [(0, -1), (1, 0), (0, 1), (-1, 0)]          # north, east, south, west
FACING_NAMES = 'NESW'
FOG_STEPS = 8
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
FLAT_ITEMS = ('exit', 'teleporter', 'stairs', 'hole', 'jump_pad')
FULL_ITEMS = ('chest', 'ladder', 'rope')


def facing_angle(f: int) -> float:
    dx, dy = FACINGS[f % 4]
    return math.atan2(dy, dx)


def opaque(picture) -> bool:
    if picture is None:
        return True
    if not picture.get_flags() & pygame.SRCALPHA and picture.get_colorkey() is None:
        return True
    w, h = picture.get_size()
    return all(picture.get_at((x, y)).a >= 128 for x in range(w) for y in range(h))


class Scene:
    """What the view needs to know about a level. The game and the editor each fill one in.

    square(x, y) -> (floor, wall, item, creature, gold, decoration), or None off the map
    picture(kind, v) -> a 40 x 40 picture or None; kinds: floor, wall, deco, item, mon, gold
    """
    sky, fog, range = 9, 9, 10

    def __init__(self, tiles: dict, item_types: dict, picture, square, hidden=lambda mon: False,
                 mon_size=lambda x, y, mon: 1):
        self.picture, self.square, self.hidden = picture, square, hidden
        self.mon_size = mon_size                  # (x, y, creature) -> its size on its top-left square, 0 on its others
        self.walls = {r['id']: r for r in tiles.get('walls', [])}
        self.decos = {r['id']: r for r in tiles.get('decos', [])}
        self.floors = {r['id']: r for r in tiles.get('floors', [])}
        self.item_types = item_types              # id -> (type, view3d or None)
        self._looks = {}

    def look(self, kind: str, v: int) -> str:
        key = (kind, v)
        if key not in self._looks:
            if kind == 'wall':
                row = self.walls.get(v, {})
                self._looks[key] = row.get('view3d') or ('block' if opaque(self.picture('wall', v)) else 'billboard')
            elif kind == 'deco':
                self._looks[key] = self.decos.get(v, {}).get('view3d') or 'billboard'
            else:
                t, look = self.item_types.get(v, ('', None))
                self._looks[key] = look or ('flat' if t in FLAT_ITEMS else 'billboard' if t in FULL_ITEMS else 'small')
        return self._looks[key]

    def roof(self, floor: int) -> int:
        return self.floors.get(floor, {}).get('roof', 0)

    def forget(self):
        self._looks = {}


class View3D:
    def __init__(self):
        self.frame = pygame.Surface((RES, RES))
        self._cols: dict = {}
        self._fog: dict = {}
        self._ground_key = None
        self.sprite_rects: dict = {}              # (x, y) of each creature drawn -> its rect in the view

    # ── helpers ─────────────────────────────────────────────────────────────
    def fog_pattern(self, colour: int, level: int) -> pygame.Surface:
        """level/FOG_STEPS of the pixels in the fog colour, in a 4x4 ordered dither; the rest clear."""
        key = (colour, level)
        if key not in self._fog:
            n = level * 16 // FOG_STEPS
            c = (*EGA[colour], 255) if colour >= 0 else (0, 0, 0, 255)
            tile = pygame.Surface((4, 4), pygame.SRCALPHA)
            tile.fill((0, 0, 0, 0))
            for y in range(4):
                for x in range(4):
                    if BAYER[y][x] < n:
                        tile.set_at((x, y), c)
            s = pygame.Surface((RES, RES), pygame.SRCALPHA)
            for y in range(0, RES, 4):
                for x in range(0, RES, 4):
                    s.blit(tile, (x, y))
            self._fog[key] = s
        return self._fog[key]

    def fog_level(self, scene, d: float) -> int:
        start = scene.range * 0.45
        if d <= start:
            return 0
        return min(FOG_STEPS, int((d - start) / (scene.range - start) * FOG_STEPS) + 1)

    def columns(self, tex):
        key = id(tex)
        got = self._cols.get(key)
        if got is None or got[0] is not tex:
            w, h = tex.get_size()
            got = (tex, [tex.subsurface((x, 0, 1, h)) for x in range(w)])
            self._cols[key] = got
        return got[1]

    # ── the frame ───────────────────────────────────────────────────────────
    def render(self, scene: Scene, cam) -> pygame.Surface:
        """cam = (x, y, angle): the eye's position in squares (a square's middle is x + 0.5) and the
        direction it looks (radians, 0 = east, pi/2 = south)."""
        cx, cy, a = cam
        f = self.frame
        ground, roof = self.ground(scene, cx, cy)
        key = (cam, self._ground_key, id(scene))
        if key == getattr(self, '_frame_key', None):
            return f                                      # nothing moved: the last frame stands
        self._frame_key = key
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy * PLANE, dx * PLANE
        horizon = RES // 2
        f.fill(EGA[scene.sky], (0, 0, RES, horizon))
        f.fill(EGA[scene.fog], (0, horizon, RES, RES - horizon))
        self.cast_ground(scene, f, ground, cx, cy, a, below=True)
        if roof is not None:
            self.cast_ground(scene, f, roof, cx, cy, a, below=False)
        zbuf = self.walls(scene, f, cx, cy, dx, dy, px, py)
        self.billboards(scene, f, zbuf, cx, cy, dx, dy, px, py)
        return f

    # ── ground and roofs: a top-down picture of the squares around, turned so the eye looks up it ─
    def ground(self, scene, cx, cy):
        R = int(scene.range * 1.25) + 2
        x0, y0 = int(math.floor(cx)), int(math.floor(cy))
        cells = []
        for i in range(-R, R + 1):
            for j in range(-R, R + 1):
                cells.append(scene.square(x0 + i, y0 + j))
        key = (x0, y0, R, tuple(cells))
        if key == self._ground_key:
            return self._ground, self._roof
        S = (2 * R + 1) * T
        g = pygame.Surface((S, S))
        g.fill(EGA[scene.fog])                     # off the map: only fog
        roof = None
        k = 0
        for i in range(2 * R + 1):
            for j in range(2 * R + 1):
                q = cells[k]
                k += 1
                if q is None:
                    continue
                fl, wa, it, mo, go, de = q
                at = (i * T, j * T)
                pic = scene.picture('floor', fl)
                if pic is not None:
                    g.blit(pic, at)
                else:
                    g.fill(EGA[2], (*at, T, T))
                if de and scene.look('deco', de) == 'flat':
                    pic = scene.picture('deco', de)
                    if pic is not None:
                        g.blit(pic, at)
                if wa and scene.look('wall', wa) == 'flat':
                    pic = scene.picture('wall', wa)
                    if pic is not None:
                        g.blit(pic, at)
                if it and scene.look('item', it) == 'flat':
                    pic = scene.picture('item', it)
                    if pic is not None:
                        g.blit(pic, at)
                r = scene.roof(fl) or (wa and self._roofed_wall(scene, cells, i, j, R))
                if r:
                    if roof is None:
                        roof = pygame.Surface((S, S), pygame.SRCALPHA)
                        roof.fill((0, 0, 0, 0))
                    pic = scene.picture('wall', r)
                    if pic is not None:
                        roof.blit(pic, at)
                    else:
                        roof.fill((*EGA[8], 255), (*at, T, T))
        self._ground_key, self._ground, self._roof = key, (g, R), (roof, R) if roof is not None else None
        return self._ground, self._roof

    @staticmethod
    def _roofed_wall(scene, cells, i, j, R):
        """A building's wall carries the roof of the room next to it (no sky between them)."""
        q = cells[i * (2 * R + 1) + j]
        if scene.look('wall', q[1]) != 'block':
            return 0
        n = 2 * R + 1
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if 0 <= a < n and 0 <= b < n:
                o = cells[a * n + b]
                if o is not None and scene.roof(o[0]) and not (o[1] and scene.look('wall', o[1]) == 'block'):
                    return scene.roof(o[0])
        return 0

    def project(self, cam, x: float, y: float):
        """Where a point on the ground shows: (screen x, screen y, a square's size there), or None
        when it is behind the eye."""
        cx, cy, a = cam
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy * PLANE, dx * PLANE
        inv = 1 / (px * dy - dx * py)
        sx, sy = x - cx, y - cy
        depth = inv * (-py * sx + px * sy)
        if depth < 0.3:
            return None
        side = inv * (dy * sx - dx * sy)
        s = SCALE / depth
        return RES / 2 * (1 + side / (depth * PLANE)), RES / 2 + 0.5 * s, s

    def cast_ground(self, scene, f, img, cx, cy, a, below):
        g, R = img
        S = g.get_width()
        theta = math.degrees(a) + 90                     # turn the picture so the eye looks up it
        turned = pygame.transform.rotate(g, theta)
        tw, th = turned.get_size()
        vx = (R + cx - math.floor(cx)) * T - S / 2
        vy = (R + cy - math.floor(cy)) * T - S / 2
        t = math.radians(theta)
        ex = tw / 2 + vx * math.cos(t) + vy * math.sin(t)
        ey = th / 2 - vx * math.sin(t) + vy * math.cos(t)
        horizon = RES // 2
        rows = range(horizon, RES) if below else range(0, horizon)
        fog_c = scene.fog
        for y in rows:
            p = (y - horizon + 0.5) if below else (horizon - y - 0.5)
            d = 0.5 * SCALE / p
            if d > scene.range:
                if not below:
                    continue
                f.fill(EGA[fog_c], (0, y, RES, 1))
                continue
            half = PLANE * d * T
            sx, sy = int(ex - half), int(ey - d * T)
            w = max(1, int(2 * half))
            if sy < 0 or sy >= th or sx < 0 or sx + w > tw:
                continue
            line = pygame.transform.scale(turned.subsurface((sx, sy, w, 1)), (RES, 1))
            f.blit(line, (0, y))
            lv = self.fog_level(scene, d)
            if lv:
                f.blit(self.fog_pattern(fog_c, lv), (0, y), (0, y, RES, 1))

    # ── walls: one ray per column ───────────────────────────────────────────
    def walls(self, scene, f, cx, cy, dx, dy, px, py):
        zbuf = [float('inf')] * RES
        horizon = RES / 2
        rng = scene.range
        for x in range(RES):
            cam = 2 * (x + 0.5) / RES - 1
            rx, ry = dx + px * cam, dy + py * cam
            mx, my = int(math.floor(cx)), int(math.floor(cy))
            ddx = abs(1 / rx) if rx else 1e30
            ddy = abs(1 / ry) if ry else 1e30
            if rx < 0:
                stx, sdx = -1, (cx - mx) * ddx
            else:
                stx, sdx = 1, (mx + 1 - cx) * ddx
            if ry < 0:
                sty, sdy = -1, (cy - my) * ddy
            else:
                sty, sdy = 1, (my + 1 - cy) * ddy
            wall = None
            while True:
                if sdx < sdy:
                    sdx += ddx
                    mx += stx
                    side = 0
                else:
                    sdy += ddy
                    my += sty
                    side = 1
                d = (sdx - ddx) if side == 0 else (sdy - ddy)
                if d > rng:
                    break
                q = scene.square(mx, my)
                if q is None:
                    break
                if q[1] and scene.look('wall', q[1]) == 'block':
                    wall = q[1]
                    break
            if wall is None:
                continue
            zbuf[x] = d
            tex = scene.picture('wall', wall)
            if side == 0:
                wx = cy + d * ry
            else:
                wx = cx + d * rx
            wx -= math.floor(wx)
            h = SCALE / d
            top = horizon - h / 2
            if tex is None:
                pygame.draw.line(f, EGA[8 if side else 7], (x, max(0, top)), (x, min(RES - 1, top + h)))
            else:
                tw, tht = tex.get_size()
                tx = min(tw - 1, int(wx * tw))
                if (side == 0 and rx > 0) or (side == 1 and ry < 0):
                    tx = tw - 1 - tx
                col = self.columns(tex)[tx]
                v0 = max(0.0, (0 - top) / h * tht)
                v1 = min(float(tht), (RES - top) / h * tht)
                r0, r1 = int(v0), min(tht, int(math.ceil(v1)))
                if r1 <= r0:
                    continue
                piece = col.subsurface((0, r0, 1, r1 - r0))
                ph = max(1, int(round((r1 - r0) * h / tht)))
                f.blit(pygame.transform.scale(piece, (1, ph)), (x, int(round(top + r0 * h / tht))))
            y0, y1 = max(0, int(top)), min(RES, int(top + h) + 1)
            if side == 1:
                f.blit(self.fog_pattern(-1, 2), (x, y0), (x, y0, 1, y1 - y0))      # the shaded sides
            lv = self.fog_level(scene, d)
            if lv:
                f.blit(self.fog_pattern(scene.fog, lv), (x, y0), (x, y0, 1, y1 - y0))
        return zbuf

    # ── things standing up: trees, creatures, items ─────────────────────────
    def billboards(self, scene, f, zbuf, cx, cy, dx, dy, px, py):
        self.sprite_rects = {}
        rng = scene.range
        inv = 1 / (px * dy - dx * py)
        things = []
        x0, y0 = int(math.floor(cx)), int(math.floor(cy))
        R = int(rng) + 1
        for i in range(-R, R + 1):
            for j in range(-R, R + 1):
                q = scene.square(x0 + i, y0 + j)
                if q is None:
                    continue
                fl, wa, it, mo, go, de = q
                sx, sy = x0 + i + 0.5 - cx, y0 + j + 0.5 - cy
                depth = inv * (-py * sx + px * sy)
                if depth < 0.3 or depth > rng:
                    continue
                side = inv * (dy * sx - dx * sy)
                n = 0
                msz = scene.mon_size(x0 + i, y0 + j, mo) if mo else 1
                # on one square, back to front: what stands there, the creature, then gold and items
                # in front of it
                for kind, v, size, cond in (('deco', de, 1.0, de and scene.look('deco', de) == 'billboard'),
                                            ('wall', wa, 1.0, wa and scene.look('wall', wa) == 'billboard'),
                                            ('mon', mo, 1.0, mo and msz == 1 and not scene.hidden(mo)),
                                            ('gold', 0, 0.45, go > 0),
                                            ('item', it, 0.5, it and scene.look('item', it) == 'small'),
                                            ('item', it, 0.9, it and scene.look('item', it) == 'billboard')):
                    if cond:
                        things.append((depth, -n, side, kind, v, size, (x0 + i, y0 + j)))
                        n += 1
                if msz > 1 and not scene.hidden(mo):          # a big creature: one picture, over all its squares
                    mx, my = x0 + i + msz / 2 - cx, y0 + j + msz / 2 - cy
                    d2 = inv * (-py * mx + px * my)
                    if 0.3 <= d2 <= rng:
                        things.append((d2, -n, inv * (dy * mx - dx * my), 'mon', mo, float(msz), (x0 + i, y0 + j)))
        things.sort(reverse=True)
        horizon = RES / 2
        for depth, _, side, kind, v, size, at in things:
            pic = scene.picture(kind, v)
            s = SCALE / depth
            w = int(s * size)
            if w < 1:
                continue
            mid = RES / 2 * (1 + side / (depth * PLANE))
            bottom = horizon + 0.5 * s
            left, top = int(mid - w / 2), int(bottom - w)
            if left >= RES or left + w <= 0:
                continue
            if pic is None:
                img = pygame.Surface((w, w), pygame.SRCALPHA)
                img.fill((0, 0, 0, 0))
                pygame.draw.circle(img, (*EGA[12 if kind == 'mon' else 14], 255), (w // 2, w // 2), max(1, w // 4))
            else:
                img = pygame.transform.scale(pic, (w, w))
            lv = self.fog_level(scene, depth)
            if lv:
                img = img.convert_alpha() if pygame.display.get_surface() else img.copy()
                mask = pygame.mask.from_surface(img)
                pat = self.fog_pattern(scene.fog, lv)
                layer = pygame.Surface((w, w), pygame.SRCALPHA)
                layer.blit(pat, (0, 0), (left % 4, top % 4, w, w))     # the dither lines up with the screen
                img.blit(mask.to_surface(setsurface=layer, unsetcolor=(0, 0, 0, 0)), (0, 0))
            # only the columns in front of the walls
            run = None
            for x in range(max(0, left), min(RES, left + w) + 1):
                visible = x < min(RES, left + w) and depth < zbuf[x]
                if visible and run is None:
                    run = x
                elif not visible and run is not None:
                    f.blit(img, (run, top), (run - left, 0, x - run, w))
                    run = None
            if kind == 'mon':
                self.sprite_rects[at] = pygame.Rect(left, top, w, w)
