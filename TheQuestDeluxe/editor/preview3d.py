"""The 3D preview: the level as FPS mode shows it, from the square last clicked on the map. Walk about
with the arrows (Up and Down walk, Left and Right turn, Q and E step sideways); walls block the way,
doors don't. Nothing in the level changes. Refresh (F5) picks up changed pictures and settings."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import pygame

from engine import view3d
from engine.formats import MAP_SIZE
from .art import photo

FOLDERS = {'floor': 'floors', 'wall': 'walls', 'deco': 'decos', 'item': 'items', 'mon': 'creatures'}


def project_scene(project, level: int) -> view3d.Scene:
    """A Scene over the editor's copy of a level (pictures not yet saved included)."""
    grid = project.grid(level)
    pictures = {}
    gold_path = project.path('sprites', 'gold.png')
    gold = pygame.image.load(gold_path) if os.path.exists(gold_path) else None

    def picture(kind, v):
        if kind == 'gold':
            return gold
        key = (kind, v)
        if key not in pictures:
            pictures[key] = project.picture(FOLDERS[kind], v)
        return pictures[key]

    def square(x, y):
        if not (1 <= x <= MAP_SIZE and 1 <= y <= MAP_SIZE):
            return None
        return tuple(grid.sq[x][y])

    invisible = {c['id'] for c in project.tables['creatures'] if c.get('invisible')}
    items = {r['id']: (r.get('type', ''), r.get('view3d')) for r in project.tables['items']}
    scene = view3d.Scene(project.tiles, items, picture, square, hidden=lambda m: m in invisible)
    dflt = project.quest.get('view3d', {})
    scene.sky = project.constant(level, 'SKY_3D', dflt.get('sky', view3d.Scene.sky))
    scene.fog = project.constant(level, 'FOG_3D', dflt.get('fog', scene.sky))
    scene.range = project.constant(level, 'RANGE_3D', dflt.get('range', view3d.Scene.range))
    return scene


class Preview3D(tk.Toplevel):
    def __init__(self, map_tab, at=None, facing=0):
        super().__init__(map_tab)
        self.map_tab = map_tab
        self.project = map_tab.app.project
        self.level = map_tab.level
        self.view = view3d.View3D()
        self.x, self.y = at or tuple(self.project.constant(self.level, 'START', (5, 5)))
        self.facing = facing
        self.image = ttk.Label(self)
        self.image.pack(padx=6, pady=6)
        self.info = ttk.Label(self, text='', foreground='#555')
        self.info.pack(anchor='w', padx=6)
        row = ttk.Frame(self)
        row.pack(fill='x', padx=6, pady=6)
        ttk.Button(row, text='Refresh (F5)', command=self.refresh).pack(side='left')
        ttk.Label(row, text='Up/Down walk, Left/Right turn, Q/E step sideways. Clicking the map moves here.',
                  foreground='#555').pack(side='left', padx=8)
        for key, fn in (('<Up>', lambda: self.walk(0)), ('<Down>', lambda: self.walk(2)),
                        ('<q>', lambda: self.walk(3)), ('<e>', lambda: self.walk(1)),
                        ('<comma>', lambda: self.walk(3)), ('<period>', lambda: self.walk(1)),
                        ('<Left>', lambda: self.turn(-1)), ('<Right>', lambda: self.turn(1)),
                        ('<F5>', self.refresh)):
            self.bind(key, lambda e, fn=fn: fn())
        self.refresh()
        self.focus_set()

    def refresh(self):
        self.level = self.map_tab.level
        self.scene = project_scene(self.project, self.level)
        self.view._ground_key = None
        self.draw()

    def goto(self, x, y):
        if self.map_tab.level != self.level:
            self.refresh()
        self.x, self.y = x, y
        self.draw()

    def turn(self, d):
        self.facing = (self.facing + d) % 4
        self.draw()

    def walk(self, way):
        dx, dy = view3d.FACINGS[(self.facing + way) % 4]
        q = self.scene.square(self.x + dx, self.y + dy)
        if q is None:
            return
        wall = self.scene.walls.get(q[1], {})
        if q[1] and wall.get('solid'):
            return
        self.x, self.y = self.x + dx, self.y + dy
        self.draw()

    def draw(self):
        frame = self.view.render(self.scene, (self.x + 0.5, self.y + 0.5, view3d.facing_angle(self.facing)))
        self._img = photo(pygame.transform.scale(frame, (2 * view3d.RES, 2 * view3d.RES)))
        self.image.config(image=self._img)
        self.title(f'3D view: level {self.level}')
        self.info.config(text=f'At {self.x}, {self.y}, looking {"north east south west".split()[self.facing]}')
