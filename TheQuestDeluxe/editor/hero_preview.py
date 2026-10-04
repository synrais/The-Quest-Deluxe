"""A hero to try items on: the base hero in a class's colour, wearing the item being made (or looked at) and whatever else is
chosen to dress him, drawn exactly as the game draws him on the map (engine.worn)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pygame

from engine import worn

from .art import photo
from .uikit import tip

SCALE = 4
DEFAULT_COLOURS = {1: 5, 2: 4, 3: 8, 4: 15}                       # the four heroes: purple, red, grey, white
PLACES = [('armour', 'Cape or armour', ('armour',)), ('helmet', 'Helmet', ('helmet',)), ('amulet', 'Amulet', ('amulet',)),
          ('weapon', 'Weapon', ('weapon', 'launcher')), ('shield', 'Shield', ('shield',))]


def class_colour(project, cls: int) -> int:
    row = next((c for c in project.tables['classes'] if c['id'] == cls), {})
    return (row.get('look') or {}).get('colour', DEFAULT_COLOURS.get(cls, 5))


def pictures_of(project):
    """picture_of and own_of for engine.worn: an item's bag and ground pictures, and its Worn on the hero picture."""
    def picture_of(item):
        return project.picture('bag', item), project.picture('items', item)

    def own_of(item):
        img = project.picture('worn', item)
        return img.convert_alpha() if img is not None else None
    return picture_of, own_of


def dressed(project, colour: int, parts: dict, replace=None, cls=None) -> pygame.Surface:
    """The hero in a colour wearing parts {place: item number}. replace: {item number: a picture} to use instead of the
    stored Worn on the hero picture (the painter's work in progress)."""
    picture_of, own_of = pictures_of(project)
    base = project.picture('heroes', cls) if cls is not None else None       # the class's painted hero, else the base
    if base is not None:
        flat = pygame.Surface(base.get_size(), pygame.SRCALPHA)
        flat.blit(base, (0, 0))
        base = flat
    by_id = {r['id']: r for r in project.tables['items']}
    rows = {p: (i, by_id[i]) for p, i in parts.items() if i and i in by_id}
    return worn.dress(colour, rows, picture_of, (lambda item: replace[item] if replace and item in replace else own_of(item)),
                      base=base)


def place_of(row: dict):
    """Which place of the hero an item goes in ('armour', 'helmet', 'amulet', 'weapon', 'shield'), or None."""
    slot = worn.slot_of(row)
    return {'offhand': 'shield'}.get(slot, slot)


class HeroPreview(ttk.LabelFrame):
    """The hero with the chosen item on, and boxes to put other items on him too (kept while the tab is open)."""

    def __init__(self, master, project, dress: dict, place=None):
        super().__init__(master, text='On a hero', padding=4)
        self.project, self.dress, self.row, self.place = project, dress, None, place
        self.classes = [(c['id'], c.get('name', str(c['id']))) for c in sorted(project.tables['classes'], key=lambda c: c['id'])]
        self.source = tk.StringVar(value='')
        if place:                                   # which picture he wears or holds, right beside the item's pictures
            pick = ttk.Frame(self)
            pick.pack(anchor='w', pady=(0, 4))
            ttk.Label(pick, text='He wears or holds its:').pack(side='left')
            for value, text, hint in (('', 'Automatic', 'A cape its picture in the bag, anything else its picture on the map.'),
                                      ('ground', 'Map picture', 'The picture it has lying on the map, laid on the hero pixel for pixel.'),
                                      ('bag', 'Bag picture', 'The picture it has in the bag (inventory), laid on the hero pixel for pixel.')):
                b = ttk.Radiobutton(pick, text=text, value=value, variable=self.source, command=self.chose_source)
                b.pack(side='left', padx=4)
                tip(b, hint)
        top = ttk.Frame(self)
        top.pack(anchor='w')
        self.image = ttk.Label(top)
        self.image.pack(side='left', padx=(0, 8))
        self.image.bind('<ButtonPress-1>', self.grab)
        self.image.bind('<B1-Motion>', self.drag)
        self.image.bind('<ButtonRelease-1>', self.drop)
        tip(self.image, 'Drag with the mouse to put the item where it sits on the hero (one pixel per step). '
                        'The arrow keys nudge it while the mouse is over it.')
        box = ttk.Frame(top)
        box.pack(side='left')
        ttk.Label(box, text='Hero').grid(row=0, column=0, sticky='w')
        self.hero = ttk.Combobox(box, state='readonly', width=18, values=[n for _, n in self.classes])
        self.hero.set(self.classes[min(len(self.classes), dress.get('class', 1)) - 1][1] if self.classes else '')
        self.hero.grid(row=0, column=1, sticky='w')
        self.hero.bind('<<ComboboxSelected>>', lambda e: self.chose_class())
        tip(self.hero, 'Which hero to try it on.')
        self.boxes = {}
        items = sorted(project.tables['items'], key=lambda r: r['id'])
        for k, (place, label, types) in enumerate(PLACES, start=1):
            ttk.Label(box, text=label).grid(row=k, column=0, sticky='w')
            chosen = [r for r in items if r.get('type') in types]
            ids = [0] + [r['id'] for r in chosen]
            names = ['(nothing)'] + [f'{r["id"]} {r.get("name", "")}' for r in chosen]
            cb = ttk.Combobox(box, state='readonly', width=22, values=names)
            cb.set(names[ids.index(dress[place])] if dress.get(place) in ids else names[0])
            cb.grid(row=k, column=1, sticky='w')
            cb.bind('<<ComboboxSelected>>', lambda e, p=place, cb=cb, ids=ids: self.dress_with(p, ids[cb.current()]))
            tip(cb, 'Put this on the hero as well, to see the item being made with it. (Not saved: only for looking.)')
            self.boxes[place] = cb
        if place:
            bar = ttk.Frame(box)
            bar.grid(row=len(PLACES) + 1, column=0, columnspan=2, sticky='w', pady=(4, 0))
            for text, cmd, hint in (('Flip', self.flip, 'Mirror the item left to right on the hero.'),
                                    ('In front', lambda: self.layer(False), 'Draw the item in front of the hero.'),
                                    ('Behind', lambda: self.layer(True), 'Draw the item behind the hero.'),
                                    ('Reset', self.reset, 'Put the item back where the game puts it.')):
                b = ttk.Button(bar, text=text, width=8, command=cmd)
                b.pack(side='left', padx=2)
                tip(b, hint)
            pad = ttk.Frame(box)
            pad.grid(row=len(PLACES) + 2, column=0, columnspan=2, sticky='w', pady=(4, 0))
            ttk.Label(pad, text='Position').grid(row=0, column=0, rowspan=2, padx=(0, 6))
            for text, (dx, dy), col, rw_, hint in (('\u25b2', (0, -1), 2, 0, 'Up one pixel.'), ('\u25c0', (-1, 0), 1, 1, 'Left one pixel.'),
                                                 ('\u25bc', (0, 1), 2, 1, 'Down one pixel.'), ('\u25b6', (1, 0), 3, 1, 'Right one pixel.')):
                b = ttk.Button(pad, text=text, width=3, command=lambda d=(dx, dy): self.nudge(*d))
                b.grid(row=rw_, column=col)
                tip(b, hint)
            self.where = ttk.Label(pad, text='')
            self.where.grid(row=0, column=4, rowspan=2, padx=8)
            self.image.bind('<Enter>', lambda e: self.image.focus_set())
            for key, (dx, dy) in (('Left', (-1, 0)), ('Right', (1, 0)), ('Up', (0, -1)), ('Down', (0, 1))):
                self.image.bind(f'<{key}>', lambda e, d=(dx, dy): self.nudge(*d))
        self.refresh()

    # ── placing the item being looked at ─────────────────────────────────────
    def mine(self):
        return self.place is not None and self.row is not None and place_of(self.row) is not None

    def grab(self, event):
        if self.mine():
            self._from = (event.x, event.y, int(self.row.get('worn_dx') or 0), int(self.row.get('worn_dy') or 0))

    def drag(self, event):
        if self.mine() and getattr(self, '_from', None):
            x, y, dx, dy = self._from
            self.moved(dx + round((event.x - x) / SCALE), dy + round((event.y - y) / SCALE), final=False)

    def drop(self, event):
        if self.mine() and getattr(self, '_from', None):
            self._from = None
            self.place('worn_dx', int(self.row.get('worn_dx') or 0))        # let the tab show the new numbers

    def moved(self, dx, dy, final=True):
        self.place('worn_dx', dx, final=False)
        self.place('worn_dy', dy, final=final)
        self.refresh()

    def nudge(self, dx, dy):
        if self.mine():
            self.moved(int(self.row.get('worn_dx') or 0) + dx, int(self.row.get('worn_dy') or 0) + dy, final=False)

    def flip(self):
        if self.mine():
            self.place('worn_flip', not self.row.get('worn_flip'))

    def layer(self, behind):
        if self.mine():
            self.place('worn_behind', behind)

    def chose_source(self):
        if self.mine():
            self.place('worn_from', self.source.get() or None)

    def reset(self):
        if self.mine():
            for key in ('worn_dx', 'worn_dy', 'worn_flip', 'worn_behind', 'worn_from'):
                self.place(key, None, final=False)
            self.place('worn_dx', 0)

    def chose_class(self):
        self.dress['class'] = self.classes[self.hero.current()][0]
        self.refresh()

    def dress_with(self, place, item):
        self.dress[place] = item
        self.refresh()

    def show(self, row):
        self.row = row
        self.source.set((row or {}).get('worn_from') or '')
        self.refresh()

    def parts(self) -> dict:
        parts = {p: self.dress.get(p, 0) for p, _, _ in PLACES}
        if self.row is not None and place_of(self.row):
            parts[place_of(self.row)] = self.row['id']            # the item being looked at is on him, whatever else
        return parts

    def refresh(self):
        if self.place and getattr(self, 'where', None) is not None and self.row is not None:
            self.where.config(text=f'{int(self.row.get("worn_dx") or 0):+d} across, {int(self.row.get("worn_dy") or 0):+d} down')
        colour = class_colour(self.project, self.dress.get('class', 1))
        hero = dressed(self.project, colour, self.parts(), cls=self.dress.get('class', 1))
        tile = pygame.Surface((40, 40))
        tile.fill((0, 168, 0))
        tile.blit(hero, (0, 0))
        self._photo = photo(pygame.transform.scale(tile, (40 * SCALE, 40 * SCALE)))
        self.image.config(image=self._photo)
