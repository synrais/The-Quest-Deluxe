"""The map: a level drawn as the game draws it, with tools to paint, rub out, fill, select, copy and paste, and markers."""
from __future__ import annotations

import base64
import io
import random
import tkinter as tk
from tkinter import ttk

import pygame

from editor.art import EGA, FIELD, photo
from editor.project import SIZE

from . import icons, levelmeta, theme
from .theme import C, px

DRAW_ORDER = ('floor', 'deco', 'wall', 'gold', 'item', 'mon')
LAYER_NAMES = {'floor': 'Ground', 'deco': 'Decoration', 'wall': 'Walls', 'gold': 'Gold', 'item': 'Items', 'mon': 'Creatures'}
ZOOMS = [5, 6, 8, 12, 16, 24, 32, 40, 56]
CLIP = {'rows': None}                       # what was copied (shared by every level and quest)
MARKER_TOOLS = ('start', 'exit', 'link', 'entry', 'respawn', 'peaceful', 'dark', 'shop')


def blank(layer):
    """What an erased square holds: no wall, item, creature, gold or decoration; the floor goes back to the plain one."""
    return 1 if layer == 'floor' else 0


class Brush:
    """What painting puts down: a layer, one or more values (several are mixed at random), and a size."""

    def __init__(self, layer='floor', values=(1,), size=1):
        self.layer, self.values, self.size = layer, list(values), size

    def pick(self):
        return random.choice(self.values) if len(self.values) > 1 else self.values[0]


def line_points(a, b):
    """Squares on the straight line from a to b (Bresenham), both ends included."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    out = []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class MapView(ttk.Frame):
    """host: the page around it. It is asked for: on_hover(x, y), on_pick(layer, value), on_marker(tool, x, y),
    on_selection(rect|None), on_view_changed()."""

    def __init__(self, master, session, host):
        super().__init__(master, style='Bg.TFrame')
        self.s, self.host = session, host
        self.level = 1
        self.zoom = 24
        self.ox = self.oy = 0
        self.hidden: set = set()
        self.locked: set = set()
        self.show_grid = True
        self.show_markers = True
        self.tool = 'brush'
        self.brush = Brush()
        self.hollow = False
        self.sel = None
        self.hover = None
        self.ghost = None
        self._drag = None
        self._space = False
        self._frame = None
        self._job = None
        self._marks = None
        self._font = None
        self.canvas = tk.Canvas(self, bg=C['canvas'], highlightthickness=0, bd=0, cursor='crosshair')
        self.hbar = ttk.Scrollbar(self, orient='horizontal', command=self._xview)
        self.vbar = ttk.Scrollbar(self, orient='vertical', command=self._yview)
        self.hbar.pack(side='bottom', fill='x')
        self.vbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor='nw')
        self.cursor_id = self.canvas.create_rectangle(0, 0, 0, 0, outline=C['accent'], width=2, state='hidden')
        self.rubber_id = self.canvas.create_rectangle(0, 0, 0, 0, outline=C['accent'], width=2, dash=(5, 3), state='hidden')
        self.line_id = self.canvas.create_line(0, 0, 0, 0, fill=C['accent'], width=3, state='hidden')
        self.sel_id = self.canvas.create_rectangle(0, 0, 0, 0, outline='#ffffff', width=2, dash=(6, 4), state='hidden')
        self.ghost_id = self.canvas.create_image(0, 0, anchor='nw', state='hidden')
        self.brush_id = self.canvas.create_image(0, 0, anchor='nw', state='hidden')
        self._brush_cache = {}
        c = self.canvas
        c.bind('<Configure>', lambda e: self._resized())
        c.bind('<ButtonPress-1>', self._press)
        c.bind('<B1-Motion>', self._motion)
        c.bind('<ButtonRelease-1>', self._release)
        c.bind('<Double-Button-1>', self._double)                # a fast second click is still a click
        c.bind('<Triple-Button-1>', self._press)
        c.bind('<ButtonPress-3>', self._right)
        c.bind('<ButtonPress-2>', self._pan_start)
        c.bind('<B2-Motion>', self._pan_move)
        c.bind('<Motion>', self._moved)
        c.bind('<Leave>', self._left)
        c.bind('<Enter>', lambda e: c.focus_set())
        c.bind('<MouseWheel>', self._wheel)
        c.bind('<Button-4>', lambda e: self._wheel(e, 1))
        c.bind('<Button-5>', lambda e: self._wheel(e, -1))
        c.bind('<KeyPress-space>', lambda e: self._set_space(True))
        c.bind('<KeyRelease-space>', lambda e: self._set_space(False))
        for key, tool in (('b', 'brush'), ('e', 'eraser'), ('r', 'rect'), ('l', 'line'), ('g', 'fill'), ('i', 'pick'),
                          ('s', 'select')):
            c.bind(f'<KeyPress-{key}>', lambda e, t=tool: self.host.choose_tool(t))
        c.bind('<Delete>', lambda e: self.clear_selection())
        c.bind('<BackSpace>', lambda e: self.clear_selection())
        c.bind('<Escape>', lambda e: self.cancel())
        c.bind('<Control-c>', lambda e: self.copy())
        c.bind('<Control-x>', lambda e: self.copy(cut=True))
        c.bind('<Control-v>', lambda e: self.paste())
        c.bind('<Control-a>', lambda e: self.select_all())
        c.bind('<KeyPress-plus>', lambda e: self.zoom_by(1))
        c.bind('<KeyPress-equal>', lambda e: self.zoom_by(1))
        c.bind('<KeyPress-minus>', lambda e: self.zoom_by(-1))
        c.bind('<Left>', lambda e: self.nudge(-1, 0))
        c.bind('<Right>', lambda e: self.nudge(1, 0))
        c.bind('<Up>', lambda e: self.nudge(0, -1))
        c.bind('<Down>', lambda e: self.nudge(0, 1))
        self.s.on('map', self._map_changed)
        self.s.on('pictures', lambda sc, src: self.refresh())
        self.s.on('script', self._script_changed)
        for t in ('items', 'creatures', 'tiles'):
            self.s.on(t, lambda sc, src: self.refresh())

    # ── the level shown ─────────────────────────────────────────────────────
    @property
    def grid(self):
        return self.s.project.grid(self.level)

    def set_level(self, n, center=None):
        self.level = n
        self.sel = None
        self._marks = None
        self.cancel()
        if center:
            self.center_on(*center)
        else:
            self._clamp()
        self.refresh()
        self._fire_selection()

    def refresh(self):
        self._marks = None
        self.schedule()

    def _map_changed(self, scope, source):
        if scope[1] == self.level and source is not self:
            self.schedule()

    def _script_changed(self, scope, source):
        if scope[1] == self.level:
            self._marks = None
            self.schedule()

    # ── geometry ────────────────────────────────────────────────────────────
    def view_size(self):
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def plane(self):
        return SIZE * self.zoom

    def _clamp(self):
        w, h = self.view_size()
        total = self.plane()
        self.ox = max(0, min(self.ox, max(0, total - w)))
        self.oy = max(0, min(self.oy, max(0, total - h)))

    def sq_at(self, ex, ey):
        x = (ex + self.ox) // self.zoom + 1
        y = (ey + self.oy) // self.zoom + 1
        return x, y

    def inside(self, x, y):
        return 1 <= x <= SIZE and 1 <= y <= SIZE

    def center_on(self, x, y):
        w, h = self.view_size()
        self.ox = int((x - 0.5) * self.zoom - w / 2)
        self.oy = int((y - 0.5) * self.zoom - h / 2)
        self._clamp()

    def zoom_to(self, z, around=None):
        z = max(ZOOMS[0], min(ZOOMS[-1], z))
        if z == self.zoom:
            return
        w, h = self.view_size()
        ax, ay = around if around else (w // 2, h // 2)
        sx, sy = (self.ox + ax) / self.zoom, (self.oy + ay) / self.zoom        # the square under that point
        self.zoom = z
        self.ox, self.oy = int(sx * z - ax), int(sy * z - ay)
        self._clamp()
        self.schedule()
        self.host.on_view_changed()

    def zoom_by(self, d, around=None):
        i = min(range(len(ZOOMS)), key=lambda k: abs(ZOOMS[k] - self.zoom))
        self.zoom_to(ZOOMS[max(0, min(len(ZOOMS) - 1, i + d))], around)

    def zoom_fit(self):
        w, h = self.view_size()
        z = max(ZOOMS[0], min(w, h) // SIZE)
        self.zoom, self.ox, self.oy = z, 0, 0
        self.schedule()
        self.host.on_view_changed()

    def _xview(self, *a):
        self._scroll_bar('x', a)

    def _yview(self, *a):
        self._scroll_bar('y', a)

    def _scroll_bar(self, axis, a):
        w, h = self.view_size()
        total, view = self.plane(), (w if axis == 'x' else h)
        cur = self.ox if axis == 'x' else self.oy
        if a[0] == 'moveto':
            cur = int(float(a[1]) * total)
        elif a[0] == 'scroll':
            cur += int(a[1]) * (self.zoom * (3 if a[2] == 'units' else 10))
        if axis == 'x':
            self.ox = cur
        else:
            self.oy = cur
        self._clamp()
        self.schedule()

    def _bars(self):
        w, h = self.view_size()
        total = self.plane()
        self.hbar.set(self.ox / total, min(1.0, (self.ox + w) / total))
        self.vbar.set(self.oy / total, min(1.0, (self.oy + h) / total))

    def _resized(self):
        self._clamp()
        self.schedule()

    # ── drawing ─────────────────────────────────────────────────────────────
    def schedule(self):
        if self._job is None:
            self._job = self.after(14, self._draw)

    def _draw(self):
        self._job = None
        if not self.winfo_exists():
            return
        w, h = self.view_size()
        if w < 8 or h < 8:
            return
        z = self.zoom
        pic = self.s.pictures
        grid = self.grid
        surf = pygame.Surface((w, h))
        surf.fill(self._rgb(C['canvas']))
        x0, x1 = max(1, self.ox // z + 1), min(SIZE, (self.ox + w) // z + 1)
        y0, y1 = max(1, self.oy // z + 1), min(SIZE, (self.oy + h) // z + 1)
        order = [l for l in DRAW_ORDER if l not in self.hidden]
        big = {c['id']: int(c.get('size') or 1) for c in self.s.project.tables['creatures'] if (c.get('size') or 1) > 1}
        tile = pic.art.tile
        sq = grid.sq
        later = []
        for x in range(x0, x1 + 1):
            px_ = (x - 1) * z - self.ox
            col = sq[x]
            for y in range(y0, y1 + 1):
                py_ = (y - 1) * z - self.oy
                cell = col[y]
                for layer in order:
                    v = cell[FIELD[layer]]
                    if not v or (layer == 'gold' and v <= 0):
                        continue
                    if layer == 'mon' and v in big:
                        later.append((px_, py_, v))
                        continue
                    img = tile(layer, v, z)
                    if img is not None:
                        surf.blit(img, (px_, py_))
        for px_, py_, v in later:
            n = big[v]
            img = tile('mon', v, z * n)
            if img is not None:
                surf.blit(img, (px_, py_))
        self._overlays(surf, w, h, x0, x1, y0, y1)
        self._frame = photo(surf)
        self.canvas.itemconfigure(self.image_id, image=self._frame)
        self._bars()
        self._refresh_cursor()

    @staticmethod
    def _rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def marks(self):
        if self._marks is None:
            self._marks = levelmeta.landmarks(self.s, self.level)
        return self._marks

    def _overlays(self, surf, w, h, x0, x1, y0, y1):
        z = self.zoom
        accent = self._rgb(C['accent'])
        if self.show_grid and z >= 12:
            lines = pygame.Surface((w, h), pygame.SRCALPHA)
            col = (0, 0, 0, 70 if z < 24 else 110)
            for x in range(x0, x1 + 2):
                xx = (x - 1) * z - self.ox
                pygame.draw.line(lines, col, (xx, 0), (xx, h))
            for y in range(y0, y1 + 2):
                yy = (y - 1) * z - self.oy
                pygame.draw.line(lines, col, (0, yy), (w, yy))
            surf.blit(lines, (0, 0))
        marks = self.marks() if self.show_markers else None
        # screens
        wide = 2 if z >= 12 else 1
        for k in range(0, 11):
            xx = k * 10 * z - self.ox
            yy = k * 10 * z - self.oy
            pygame.draw.line(surf, (255, 255, 255), (xx, 0), (xx, h), wide)
            pygame.draw.line(surf, (255, 255, 255), (0, yy), (w, yy), wide)
        if marks:
            for kind, colour in (('peaceful', (80, 200, 255)), ('dark', (110, 110, 255))):
                for sx, sy in marks[kind]:
                    r = pygame.Rect((sx - 1) * 10 * z - self.ox, (sy - 1) * 10 * z - self.oy, 10 * z, 10 * z)
                    if kind == 'dark':
                        shade = pygame.Surface(r.size, pygame.SRCALPHA)
                        shade.fill((0, 0, 40, 120))
                        surf.blit(shade, r)
                    pygame.draw.rect(surf, colour, r.inflate(-4, -4), 3)
            for (sx, sy), k in marks['shops'].items():
                self._badge(surf, (sx - 1) * 10 * z - self.ox + 6, (sy - 1) * 10 * z - self.oy + 6, f'Shop {k}', (0, 0, 160))
        if z >= 5 and z < 16:                                         # screen numbers when zoomed out
            f = self._get_font(max(10, min(28, z * 3)))
            for sx in range(1, 11):
                for sy in range(1, 11):
                    t = f.render(f'{sx},{sy}', True, (255, 255, 255))
                    t.set_alpha(110)
                    surf.blit(t, ((sx - 1) * 10 * z - self.ox + 6, (sy - 1) * 10 * z - self.oy + 4))
        if marks:
            self._marker(surf, marks['start'], 'flag', (255, 255, 255), 'Start', accent)
            for x, y, item in marks['exits']:
                dest = (marks['links_map'].get((x, y)))
                text = f'→ {dest[0]}' if dest else '→'
                self._marker(surf, (x, y), 'door', (255, 255, 255), text, (230, 80, 60))
            for x, y, item in marks['links']:
                dest = marks['links_map'].get((x, y))
                self._marker(surf, (x, y), 'link', (255, 255, 255), f'→ {dest[0]}' if dest else '?', (255, 160, 0))
            for name, (x, y) in marks['entries'].items():
                self._marker(surf, (x, y), 'star', (255, 255, 255), name, (60, 200, 110))
            if marks['respawn']:
                self._marker(surf, tuple(marks['respawn']), 'heart', (255, 255, 255), 'Wake', (230, 90, 160))
            for x, y, item in marks['teleporters']:
                self._marker(surf, (x, y), 'sparkle', (255, 255, 255), '', (150, 100, 255))

    def _get_font(self, size):
        if self._font is None or self._font[0] != size:
            self._font = (size, pygame.font.Font(None, size))
        return self._font[1]

    def _badge(self, surf, x, y, text, colour):
        f = self._get_font(max(14, min(22, self.zoom)))
        t = f.render(text, True, (255, 255, 255), colour)
        surf.blit(t, (x, y))

    def _marker(self, surf, sq, icon, fg, text, colour):
        z = self.zoom
        x, y = sq
        px_, py_ = (x - 1) * z - self.ox, (y - 1) * z - self.oy
        if px_ < -z * 4 or py_ < -z or px_ > surf.get_width() or py_ > surf.get_height():
            return
        r = pygame.Rect(px_, py_, z, z)
        pygame.draw.rect(surf, colour, r, max(2, z // 12))
        size = max(8, min(z - 2, 26))
        ic = icons.surface(icon, colour, size)
        bg = pygame.Surface((size + 2, size + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        surf.blit(bg, (px_ + 1, py_ + 1))
        surf.blit(ic, (px_ + 2, py_ + 2))
        if text and z >= 12:
            f = self._get_font(max(14, min(20, z)))
            t = f.render(text, True, (255, 255, 255), colour)
            surf.blit(t, (px_ + z + 2, py_ + 1))

    # ── mouse ───────────────────────────────────────────────────────────────
    def _set_space(self, on):
        self._space = on
        self.canvas.configure(cursor='fleur' if on else self._cursor_for())

    def _cursor_for(self):
        return {'pick': 'target', 'select': 'tcross', 'fill': 'spraycan'}.get(self.tool, 'crosshair')

    def set_tool(self, tool):
        self.tool = tool
        self.cancel(keep_tool=True)
        self.canvas.configure(cursor=self._cursor_for())
        self._refresh_cursor()

    def _event_sq(self, e):
        return self.sq_at(e.x, e.y)

    def _moved(self, e):
        x, y = self._event_sq(e)
        self.hover = (x, y) if self.inside(x, y) else None
        self.host.on_hover(*(self.hover or (0, 0)), self.hover is not None)
        self._refresh_cursor()
        if self.ghost:
            self._place_ghost(x, y)

    def _left(self, e):
        self.hover = None
        self.canvas.itemconfigure(self.cursor_id, state='hidden')
        self.canvas.itemconfigure(self.brush_id, state='hidden')
        self.host.on_hover(0, 0, False)

    def _brush_ghost(self):
        """The picture the brush would put down, faint under the pointer."""
        c = self.canvas
        b = self.brush
        if self.tool != 'brush' or self.hover is None or self.ghost or not b.values or b.layer in self.locked or self._drag:
            c.itemconfigure(self.brush_id, state='hidden')
            return
        z, n = self.zoom, b.size
        v = b.values[0]
        key = (b.layer, v, z, n)
        img = self._brush_cache.get(key)
        if img is None:
            tile = self.s.pictures.art.tile(b.layer, v, z) if (v or b.layer == 'gold') else None
            if tile is None:
                c.itemconfigure(self.brush_id, state='hidden')
                return
            surf = pygame.Surface((z * n, z * n), pygame.SRCALPHA)
            for i in range(n):
                for j in range(n):
                    surf.blit(tile, (i * z, j * z))
            surf.fill((255, 255, 255, 140), special_flags=pygame.BLEND_RGBA_MULT)
            buf = io.BytesIO()
            pygame.image.save(surf, buf, 'x.png')
            img = tk.PhotoImage(data=base64.b64encode(buf.getvalue()), format='png')
            if len(self._brush_cache) > 40:
                self._brush_cache.clear()
            self._brush_cache[key] = img
        x, y = self.hover
        a = n // 2
        c.itemconfigure(self.brush_id, image=img, state='normal')
        c.coords(self.brush_id, (x - a - 1) * z - self.ox, (y - a - 1) * z - self.oy)
        c.tag_lower(self.brush_id, self.cursor_id)

    def _refresh_cursor(self):
        c = self.canvas
        self._brush_ghost()
        if self.hover is None or self.ghost or self.tool in ('select',) and self._drag:
            c.itemconfigure(self.cursor_id, state='hidden')
        else:
            x, y = self.hover
            n = self.brush.size if self.tool in ('brush', 'eraser') else 1
            a = n // 2
            x0, y0 = x - a, y - a
            z = self.zoom
            c.coords(self.cursor_id, (x0 - 1) * z - self.ox, (y0 - 1) * z - self.oy,
                     (x0 - 1 + n) * z - self.ox, (y0 - 1 + n) * z - self.oy)
            c.itemconfigure(self.cursor_id, state='normal')
            c.tag_raise(self.cursor_id)
        self._draw_selection()

    def _draw_selection(self):
        c = self.canvas
        if self.sel:
            x0, y0, x1, y1 = self.sel
            z = self.zoom
            c.coords(self.sel_id, (x0 - 1) * z - self.ox, (y0 - 1) * z - self.oy, x1 * z - self.ox, y1 * z - self.oy)
            c.itemconfigure(self.sel_id, state='normal')
            c.tag_raise(self.sel_id)
        else:
            c.itemconfigure(self.sel_id, state='hidden')

    def _wheel(self, e, direction=None):
        d = direction if direction is not None else (1 if e.delta > 0 else -1)
        if e.state & 0x4:                                  # Ctrl: zoom about the pointer
            self.zoom_by(d, (e.x, e.y))
        elif e.state & 0x1:                                # Shift: sideways
            self.ox -= d * self.zoom * 3
            self._clamp()
            self.schedule()
        else:
            self.oy -= d * self.zoom * 3
            self._clamp()
            self.schedule()
        return 'break'

    def _pan_start(self, e):
        self._pan = (e.x, e.y, self.ox, self.oy)
        self.canvas.configure(cursor='fleur')

    def _pan_move(self, e):
        if getattr(self, '_pan', None):
            x, y, ox, oy = self._pan
            self.ox, self.oy = ox - (e.x - x), oy - (e.y - y)
            self._clamp()
            self.schedule()

    def _double(self, e):
        self._press(e)
        x, y = self._event_sq(e)
        if self.inside(x, y) and self.tool not in MARKER_TOOLS and not self.ghost:
            self._release(e)                       # the stroke ends here: a window is about to open
            self.host.on_double(x, y)

    def _right(self, e):
        if self.ghost:
            self.cancel()
            return
        x, y = self._event_sq(e)
        if self.inside(x, y):
            self.pick_at(x, y)

    def _press(self, e):
        self.canvas.focus_set()
        if self._space:
            self._pan_start(e)
            return
        x, y = self._event_sq(e)
        t = self.tool
        if self.inside(x, y):
            self.host.on_click(x, y)
        if self.ghost:
            if self.inside(x, y):
                self.commit_paste(x, y)
            return
        if t in MARKER_TOOLS:
            if self.inside(x, y):
                self.host.on_marker(t, x, y)
            return
        if not self.inside(x, y) and t not in ('select',):
            return
        if t == 'pick':
            self.pick_at(x, y)
        elif t in ('brush', 'eraser'):
            if self.brush.layer in self.locked:
                self.host.say_locked(self.brush.layer)
                return
            self._drag = {'kind': t, 'last': (x, y), 'before': self.s.begin_stroke(('map', self.level)), 'changed': 0}
            self._stroke_to(x, y, e.state & 0x1)
        elif t in ('rect', 'line'):
            if self.brush.layer in self.locked:
                self.host.say_locked(self.brush.layer)
                return
            self._drag = {'kind': t, 'start': (x, y), 'end': (x, y)}
            self._rubber()
        elif t == 'fill':
            if self.brush.layer in self.locked:
                self.host.say_locked(self.brush.layer)
                return
            self.flood(x, y, replace_all=bool(e.state & 0x4))
        elif t == 'select':
            x = max(1, min(SIZE, x))
            y = max(1, min(SIZE, y))
            if self.sel and self.sel[0] <= x <= self.sel[2] and self.sel[1] <= y <= self.sel[3]:
                self._drag = {'kind': 'move', 'start': (x, y)}
            else:
                self.sel = None
                self._drag = {'kind': 'select', 'start': (x, y), 'end': (x, y)}
                self._draw_selection()

    def _motion(self, e):
        if getattr(self, '_pan', None) and (self._space or not self._drag):
            self._pan_move(e)
            return
        x, y = self._event_sq(e)
        self.hover = (x, y) if self.inside(x, y) else None
        self.host.on_hover(x, y, self.hover is not None)
        d = self._drag
        if not d:
            return
        k = d['kind']
        if k in ('brush', 'eraser'):
            if self.inside(x, y) or d['last']:
                self._stroke_to(max(1, min(SIZE, x)), max(1, min(SIZE, y)), e.state & 0x1)
        elif k in ('rect', 'line'):
            d['end'] = (max(1, min(SIZE, x)), max(1, min(SIZE, y)))
            self._rubber()
        elif k == 'select':
            d['end'] = (max(1, min(SIZE, x)), max(1, min(SIZE, y)))
            x0, x1 = sorted((d['start'][0], d['end'][0]))
            y0, y1 = sorted((d['start'][1], d['end'][1]))
            self.sel = (x0, y0, x1, y1)
            self._draw_selection()
        self._refresh_cursor()

    def _release(self, e):
        if getattr(self, '_pan', None):
            self._pan = None
            self.canvas.configure(cursor=self._cursor_for())
        d, self._drag = self._drag, None
        if not d:
            return
        k = d['kind']
        if k in ('brush', 'eraser'):
            if d['changed']:
                label = 'Paint' if k == 'brush' else 'Erase'
                self.s.end_stroke(f'{label} on level {self.level}', d['before'], source=self)
                self.host.map_edited()
        elif k in ('rect', 'line'):
            self.canvas.itemconfigure(self.rubber_id, state='hidden')
            self.canvas.itemconfigure(self.line_id, state='hidden')
            self._shape(d)
        elif k == 'select':
            self._fire_selection()
        elif k == 'move':
            x, y = self._event_sq(e)
            dx, dy = x - d['start'][0], y - d['start'][1]
            if dx or dy:
                self.move_selection(dx, dy)
        self._refresh_cursor()

    # ── painting ────────────────────────────────────────────────────────────
    def _stroke_to(self, x, y, shift=False):
        d = self._drag
        for pt in line_points(d['last'], (x, y)):
            self._dab(pt[0], pt[1], d['kind'] == 'eraser', shift)
        d['last'] = (x, y)
        self.schedule()

    def _dab(self, x, y, erase, everything=False):
        n = self.brush.size
        a = n // 2
        sq = self.grid.sq
        for i in range(x - a, x - a + n):
            for j in range(y - a, y - a + n):
                if not self.inside(i, j):
                    continue
                cell = sq[i][j]
                if erase:
                    layers = [l for l in FIELD if l not in self.locked] if everything else [self.brush.layer]
                    for l in layers:
                        if cell[FIELD[l]] != blank(l):
                            cell[FIELD[l]] = blank(l)
                            self._drag['changed'] = self._drag.get('changed', 0) + 1
                else:
                    f = FIELD[self.brush.layer]
                    v = self.brush.pick()
                    if cell[f] != v:
                        cell[f] = v
                        self._drag['changed'] = self._drag.get('changed', 0) + 1

    def _apply(self, label, squares, erase=False):
        """Paint or erase a list of squares as one undoable step."""
        before = self.s.begin_stroke(('map', self.level))
        self._drag = {'changed': 0}
        for x, y in squares:
            if self.inside(x, y):
                self._dab_one(x, y, erase)
        changed = self._drag['changed']
        self._drag = None
        if changed:
            self.s.end_stroke(label, before, source=self)
            self.host.map_edited()
            self.schedule()
        return changed

    def _dab_one(self, x, y, erase):
        cell = self.grid.sq[x][y]
        f = FIELD[self.brush.layer]
        v = blank(self.brush.layer) if erase else self.brush.pick()
        if cell[f] != v:
            cell[f] = v
            self._drag['changed'] += 1

    def _shape(self, d):
        a, b = d['start'], d['end']
        if d['kind'] == 'line':
            sq = line_points(a, b)
        else:
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            sq = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
                  if not self.hollow or x in (x0, x1) or y in (y0, y1)]
        n = self.brush.size if d['kind'] == 'line' else 1
        if n > 1:
            a2 = n // 2
            sq = list({(x + i, y + j) for x, y in sq for i in range(-a2, n - a2) for j in range(-a2, n - a2)})
        self._apply(f'Draw a {d["kind"]}', sq, erase=self.tool == 'eraser')

    def _rubber(self):
        d = self._drag
        z = self.zoom
        a, b = d['start'], d['end']
        c = self.canvas
        if d['kind'] == 'line':
            c.coords(self.line_id, (a[0] - 0.5) * z - self.ox, (a[1] - 0.5) * z - self.oy,
                     (b[0] - 0.5) * z - self.ox, (b[1] - 0.5) * z - self.oy)
            c.itemconfigure(self.line_id, state='normal')
        else:
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            c.coords(self.rubber_id, (x0 - 1) * z - self.ox, (y0 - 1) * z - self.oy, x1 * z - self.ox, y1 * z - self.oy)
            c.itemconfigure(self.rubber_id, state='normal')

    def flood(self, x, y, replace_all=False):
        f = FIELD[self.brush.layer]
        sq = self.grid.sq
        old = sq[x][y][f]
        if replace_all:
            squares = [(i, j) for i in range(1, SIZE + 1) for j in range(1, SIZE + 1) if sq[i][j][f] == old]
        else:
            seen, stack = {(x, y)}, [(x, y)]
            while stack:
                i, j = stack.pop()
                for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    if 1 <= a <= SIZE and 1 <= b <= SIZE and (a, b) not in seen and sq[a][b][f] == old:
                        seen.add((a, b))
                        stack.append((a, b))
            squares = list(seen)
        if len(squares) > 600 and not self.host.confirm_big(len(squares)):
            return
        self._apply('Fill', squares)

    def pick_at(self, x, y):
        cell = self.grid.sq[x][y]
        for layer in ('mon', 'item', 'gold', 'wall', 'deco', 'floor'):
            if layer in self.hidden:
                continue
            v = cell[FIELD[layer]]
            if v:
                self.host.on_pick(layer, v)
                return
        self.host.on_pick('floor', 0)

    # ── selection, copy, paste ──────────────────────────────────────────────
    def _fire_selection(self):
        self.host.on_selection(self.sel)

    def select_all(self):
        self.sel = (1, 1, SIZE, SIZE)
        self._refresh_cursor()
        self._fire_selection()

    def select_screen(self, sx, sy):
        self.sel = ((sx - 1) * 10 + 1, (sy - 1) * 10 + 1, sx * 10, sy * 10)
        self._refresh_cursor()
        self._fire_selection()

    def cancel(self, keep_tool=False):
        self.ghost = None
        self._drag = None
        for i in (self.ghost_id, self.rubber_id, self.line_id):
            self.canvas.itemconfigure(i, state='hidden')
        self.host.on_view_changed()

    def selection_rows(self):
        if not self.sel:
            return None
        x0, y0, x1, y1 = self.sel
        sq = self.grid.sq
        return [[list(sq[x][y]) for y in range(y0, y1 + 1)] for x in range(x0, x1 + 1)]

    def copy(self, cut=False):
        rows = self.selection_rows()
        if not rows:
            return
        CLIP['rows'] = rows
        self.host.say(f'Copied {len(rows)} x {len(rows[0])} squares.' if not cut else 'Cut.')
        if cut:
            self.clear_selection('Cut')

    def clear_selection(self, label='Clear'):
        if not self.sel:
            return
        x0, y0, x1, y1 = self.sel
        before = self.s.begin_stroke(('map', self.level))
        sq = self.grid.sq
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for f in range(6):
                    if FIELD_NAMES[f] not in self.locked:
                        sq[x][y][f] = 0 if f != 0 else 1
        self.s.end_stroke(f'{label} squares on level {self.level}', before, source=self)
        self.host.map_edited()
        self.schedule()

    def paste(self):
        rows = CLIP['rows']
        if not rows:
            self.host.say('Nothing copied yet: select squares (S), then Ctrl+C.')
            return
        self.ghost = rows
        z = self.zoom
        w, h = len(rows) * z, len(rows[0]) * z
        surf = pygame.Surface((w, h))
        tmp = pygame.Surface((z, z))
        pic = self.s.pictures
        for i, col in enumerate(rows):
            for j, cell in enumerate(col):
                tmp.fill((0, 0, 0))
                for layer in DRAW_ORDER:
                    v = cell[FIELD[layer]]
                    if v and (layer != 'gold' or v > 0):
                        img = pic.art.tile(layer, v, z)
                        if img is not None:
                            tmp.blit(img, (0, 0))
                surf.blit(tmp, (i * z, j * z))
        rgba = pygame.Surface((w, h), pygame.SRCALPHA)
        rgba.blit(surf, (0, 0))
        rgba.fill((255, 255, 255, 175), special_flags=pygame.BLEND_RGBA_MULT)
        buf = io.BytesIO()
        pygame.image.save(rgba, buf, 'x.png')
        self._ghost_img = tk.PhotoImage(data=base64.b64encode(buf.getvalue()), format='png')
        self.canvas.itemconfigure(self.ghost_id, image=self._ghost_img, state='normal')
        if self.hover:
            self._place_ghost(*self.hover)
        self.host.say('Click where to put it (Esc cancels).')

    def _place_ghost(self, x, y):
        z = self.zoom
        self.canvas.coords(self.ghost_id, (x - 1) * z - self.ox, (y - 1) * z - self.oy)
        self.canvas.tag_raise(self.ghost_id)

    def commit_paste(self, x, y):
        rows = self.ghost
        before = self.s.begin_stroke(('map', self.level))
        sq = self.grid.sq
        for i, col in enumerate(rows):
            for j, cell in enumerate(col):
                if self.inside(x + i, y + j):
                    for f in range(6):
                        if FIELD_NAMES[f] not in self.locked:
                            sq[x + i][y + j][f] = cell[f]
        self.s.end_stroke(f'Paste on level {self.level}', before, source=self)
        self.sel = (x, y, min(SIZE, x + len(rows) - 1), min(SIZE, y + len(rows[0]) - 1))
        self.cancel()
        self.host.map_edited()
        self.schedule()
        self._fire_selection()

    def move_selection(self, dx, dy):
        rows = self.selection_rows()
        if not rows:
            return
        x0, y0, x1, y1 = self.sel
        before = self.s.begin_stroke(('map', self.level))
        sq = self.grid.sq
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for f in range(6):
                    sq[x][y][f] = 0 if f != 0 else 1
        for i, col in enumerate(rows):
            for j, cell in enumerate(col):
                if self.inside(x0 + dx + i, y0 + dy + j):
                    sq[x0 + dx + i][y0 + dy + j][:] = cell
        self.sel = (max(1, x0 + dx), max(1, y0 + dy), min(SIZE, x1 + dx), min(SIZE, y1 + dy))
        self.s.end_stroke(f'Move squares on level {self.level}', before, source=self)
        self.host.map_edited()
        self.schedule()
        self._fire_selection()

    def nudge(self, dx, dy):
        if self.sel:
            self.move_selection(dx, dy)
        else:
            self.ox += dx * self.zoom
            self.oy += dy * self.zoom
            self._clamp()
            self.schedule()
        return 'break'

    def scroll_to_screen(self, sx, sy):
        z = self.zoom
        w, h = self.view_size()
        self.center_on((sx - 1) * 10 + 5.5, (sy - 1) * 10 + 5.5)
        self.schedule()

    def flash(self, x, y):
        """Ring a square for a moment, so the eye finds it."""
        z = self.zoom
        c = self.canvas
        item = c.create_oval((x - 1) * z - self.ox - z, (y - 1) * z - self.oy - z, x * z - self.ox + z, y * z - self.oy + z,
                             outline=C['accent'], width=3)

        def step(k=0):
            if not self.winfo_exists():
                return
            if k >= 6:
                c.delete(item)
                return
            c.itemconfigure(item, state='hidden' if k % 2 else 'normal')
            self.after(140, lambda: step(k + 1))
        step()

    def visible_screens(self):
        z = self.zoom
        w, h = self.view_size()
        return ((self.ox // z) // 10 + 1, (self.oy // z) // 10 + 1)


FIELD_NAMES = {v: k for k, v in FIELD.items()}
