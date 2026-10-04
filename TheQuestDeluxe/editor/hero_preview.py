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
# the inventory's layout: (place, caption, what fits, grid row, grid column). The weapon slot is on the screen's left: his
# RIGHT hand; the off-hand slot on the screen's right: his LEFT hand.
SLOTS = [('helmet', 'Helmet', ('helmet',), 0, 1),
         ('weapon', 'RIGHT hand', ('weapon', 'launcher'), 1, 0), ('armour', 'Cape or armour', ('armour',), 1, 1),
         ('shield', 'LEFT hand', ('shield', 'weapon', 'launcher'), 1, 2),
         ('amulet', 'Amulet', ('amulet',), 2, 1)]
PLACES = [(p, c, t) for p, c, t, _, _ in SLOTS]


class Ghost:
    """A little picture that follows the mouse while an item is dragged."""

    def __init__(self, master):
        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        self.label = tk.Label(self.top, borderwidth=0)
        self.label.pack()
        self.top.withdraw()
        self._photo = None

    def show(self, surface, x, y):
        self._photo = photo(surface)
        self.label.config(image=self._photo)
        self.top.geometry(f'+{x + 8}+{y + 8}')
        self.top.deiconify()
        self.top.lift()

    def move(self, x, y):
        self.top.geometry(f'+{x + 8}+{y + 8}')

    def close(self):
        self.top.destroy()


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
    """Which place of the hero an item goes in ('armour', 'helmet', 'amulet', 'weapon', 'shield'), or None: a weapon in his
    right hand (the weapon slot), a shield in his left (the off-hand slot)."""
    slot = worn.slot_of(row)
    return {'offhand': 'shield'}.get(slot, slot)


def slot_for(row: dict, dress: dict):
    """Where the item being looked at is put on him: its own place, or for a weapon or shield the hand chosen to see it in."""
    if row is None:
        return None
    if worn.natural_hand(row):
        hand = dress.get('hand') if dress.get('hand_for') == row['id'] else worn.natural_hand(row)
        return 'weapon' if hand == 'right' else 'shield'
    return place_of(row)


class HeroPreview(ttk.LabelFrame):
    """The inventory's layout with the hero beside it: slots to drop items into (drag from the list on the left, or from one
    slot to another; drag one a little way off to take it away), and the item being looked at on him, placed by dragging."""

    def __init__(self, master, project, dress: dict, place=None):
        super().__init__(master, text='On a hero: the inventory', padding=4)
        self.project, self.dress, self.row, self.place = project, dress, None, place
        self.classes = [(c['id'], c.get('name', str(c['id']))) for c in sorted(project.tables['classes'], key=lambda c: c['id'])]
        self.source = tk.StringVar(value='')
        self.hand = tk.StringVar(value='right')
        self.ghost = None
        self.slots = {}
        if place:                                   # which picture he wears or holds, right beside the item's pictures
            pick = ttk.Frame(self)
            pick.pack(anchor='w', pady=(0, 2))
            ttk.Label(pick, text='He wears or holds its:').pack(side='left')
            for value, text, hint in (('', 'Automatic', 'A cape its picture in the bag, anything else its picture on the map.'),
                                      ('ground', 'Map picture', 'The picture it has lying on the map, laid on the hero pixel for pixel.'),
                                      ('bag', 'Bag picture', 'The picture it has in the bag (inventory), laid on the hero pixel for pixel.')):
                b = ttk.Radiobutton(pick, text=text, value=value, variable=self.source, command=self.chose_source)
                b.pack(side='left', padx=4)
                tip(b, hint)
            self.hands = ttk.Frame(self)
            self.hands.pack(anchor='w', pady=(0, 4))
            ttk.Label(self.hands, text='Show it in his:').pack(side='left')
            for value, text, hint in (('right', 'RIGHT hand (screen left)', 'The weapon slot: the hand on the left of the screen, as the inventory shows it.'),
                                      ('left', 'LEFT hand (screen right)', 'The off-hand slot: the hand on the right of the screen. The item is the same, flipped.')):
                b = ttk.Radiobutton(self.hands, text=text, value=value, variable=self.hand, command=self.chose_hand)
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
        box.pack(side='left', anchor='n')
        ttk.Label(box, text='Hero').grid(row=0, column=0, sticky='e')
        self.hero = ttk.Combobox(box, state='readonly', width=14, values=[n for _, n in self.classes])
        self.hero.set(self.classes[min(len(self.classes), dress.get('class', 1)) - 1][1] if self.classes else '')
        self.hero.grid(row=0, column=1, columnspan=2, sticky='w')
        self.hero.bind('<<ComboboxSelected>>', lambda e: self.chose_class())
        tip(self.hero, 'Which hero to try it on.')
        grid = ttk.Frame(box)
        grid.grid(row=1, column=0, columnspan=3, pady=(4, 0))
        for slot, caption, types, r, c in SLOTS:
            unit = ttk.Frame(grid)
            unit.grid(row=r, column=c, padx=4, pady=2)
            ttk.Label(unit, text=caption, font=('TkDefaultFont', 8, 'bold' if 'hand' in caption else 'normal')).pack()
            cv = tk.Canvas(unit, width=48, height=48, bg='#3a3a3a', highlightthickness=2, highlightbackground='#777777')
            cv.pack()
            cv.bind('<ButtonPress-1>', lambda e, s=slot: self.pick_up(s, e))
            cv.bind('<B1-Motion>', lambda e, s=slot: self.carry(s, e))
            cv.bind('<ButtonRelease-1>', lambda e, s=slot: self.put_down(s, e))
            cv.bind('<ButtonPress-3>', lambda e, s=slot: self.take_off(s))
            tip(cv, f'{caption}: drag an item here from the list on the left to put it on the hero (it only fits what goes '
                    'there). Drag it a little way off to take it away, or right-click. Only for looking: nothing is saved.')
            self.slots[slot] = cv
        if place:
            bar = ttk.Frame(self)
            bar.pack(anchor='w', pady=(4, 0))
            for text, cmd, hint in (('Rotate', self.rotate, 'Turn the item 45 degrees clockwise about its middle, each click (right-click: the other way).'),
                                    ('In front', lambda: self.layer(False), 'Draw the item in front of the hero.'),
                                    ('Behind', lambda: self.layer(True), 'Draw the item behind the hero.'),
                                    ('Reset', self.reset, 'Put the item back where the game puts it.')):
                b = ttk.Button(bar, text=text, width=8, command=cmd)
                b.pack(side='left', padx=2)
                if text == 'Rotate':
                    b.bind('<Button-3>', lambda e: self.rotate(-45))
                tip(b, hint)
            pad = ttk.Frame(self)
            pad.pack(anchor='w', pady=(4, 0))
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

    # ── the slots: what is on him ────────────────────────────────────────────
    def fits(self, slot, row) -> bool:
        return any(s == slot and row.get('type') in types for s, _, types, _, _ in SLOTS)

    def row_of(self, item):
        return next((r for r in self.project.tables['items'] if r['id'] == item), None)

    def slot_at(self, x_root, y_root):
        for slot, cv in self.slots.items():
            if cv.winfo_rootx() <= x_root < cv.winfo_rootx() + cv.winfo_width() and \
               cv.winfo_rooty() <= y_root < cv.winfo_rooty() + cv.winfo_height():
                return slot
        return None

    def subject_slot(self):
        return slot_for(self.row, self.dress) if self.row is not None and place_of(self.row) else None

    def bag_picture(self, item):
        img = self.project.picture('bag', item)
        if img is None:
            return None
        flat = pygame.Surface(img.get_size())
        flat.blit(img, (0, 0))
        return flat

    def drop_from_list(self, item, x_root, y_root) -> bool:
        """An item from the list was let go at a place on the screen: put it on him if that is a slot it fits."""
        slot, row = self.slot_at(x_root, y_root), self.row_of(item)
        if slot is None or row is None or slot == self.subject_slot():
            return False
        if not self.fits(slot, row):
            return False
        self.dress_with(slot, item)
        return True

    def pick_up(self, slot, event):
        item = self.parts().get(slot, 0)
        if not item or slot == self.subject_slot():
            self._carry = None                         # (the item being made is not dragged off: it is the subject)
            return
        self._carry = (slot, item, event.x_root, event.y_root, False)

    def carry(self, slot, event):
        if not getattr(self, '_carry', None):
            return
        s, item, x, y, moving = self._carry
        if not moving and abs(event.x_root - x) + abs(event.y_root - y) > 6:
            moving = True
            pic = self.bag_picture(item)
            if pic is not None:
                self.ghost = self.ghost or Ghost(self)
                self.ghost.show(pic, event.x_root, event.y_root)
            self._carry = (s, item, x, y, True)
        if moving and self.ghost:
            self.ghost.move(event.x_root, event.y_root)

    def put_down(self, slot, event):
        if self.ghost:
            self.ghost.close()
            self.ghost = None
        carried, self._carry = getattr(self, '_carry', None), None
        if not carried or not carried[4]:
            return
        _, item, _, _, _ = carried
        target = self.slot_at(event.x_root, event.y_root)
        row = self.row_of(item)
        if target == slot:
            return
        if target is not None and row is not None and self.fits(target, row) and target != self.subject_slot():
            self.dress[slot] = 0
            self.dress_with(target, item)
        elif target is None:
            self.take_off(slot)                         # dragged a bit off: taken away

    def take_off(self, slot):
        if slot != self.subject_slot() and self.dress.get(slot):
            self.dress[slot] = 0
            self.refresh()

    # ── placing the item being looked at ─────────────────────────────────────
    def mine(self):
        return self.place is not None and self.row is not None and place_of(self.row) is not None

    def mirror(self) -> int:
        """-1 when the item is shown in the hand it is not made for (its sideways moves are mirrored), else 1."""
        slot = self.subject_slot()
        return -1 if slot and worn.mirrored(self.row, slot) else 1

    def grab(self, event):
        if self.mine():
            self._from = (event.x, event.y, int(self.row.get('worn_dx') or 0), int(self.row.get('worn_dy') or 0))

    def drag(self, event):
        if self.mine() and getattr(self, '_from', None):
            x, y, dx, dy = self._from
            self.moved(dx + self.mirror() * round((event.x - x) / SCALE), dy + round((event.y - y) / SCALE), final=False)

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
            self.moved(int(self.row.get('worn_dx') or 0) + self.mirror() * dx, int(self.row.get('worn_dy') or 0) + dy, final=False)

    def rotate(self, step=45):
        if self.mine():
            turn = int(self.row.get('worn_rotate') or 0)
            self.place('worn_rotate', (turn + step * self.mirror()) % 360 or None)       # (as it looks: clockwise)

    def layer(self, behind):
        if self.mine():
            self.place('worn_behind', behind)

    def chose_source(self):
        if self.mine():
            self.place('worn_from', self.source.get() or None)

    def chose_hand(self):
        if self.row is not None:
            self.dress['hand'], self.dress['hand_for'] = self.hand.get(), self.row['id']
            self.refresh()

    def reset(self):
        if self.mine():
            for key in ('worn_dx', 'worn_dy', 'worn_rotate', 'worn_behind', 'worn_from'):
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
        if row is not None and worn.natural_hand(row):
            self.hand.set('left' if slot_for(row, self.dress) == 'shield' else 'right')
            self.hands.pack(anchor='w', pady=(0, 4)) if self.place else None
        elif self.place:
            self.hands.pack_forget()
        self.refresh()

    def parts(self) -> dict:
        parts = {p: self.dress.get(p, 0) for p, _, _ in PLACES}
        slot = self.subject_slot()
        if slot:
            parts[slot] = self.row['id']                          # the item being looked at is on him, whatever else
        return parts

    def refresh(self):
        if self.place and getattr(self, 'where', None) is not None and self.row is not None:
            self.where.config(text=f'{int(self.row.get("worn_dx") or 0):+d} across, {int(self.row.get("worn_dy") or 0):+d} down')
        parts = self.parts()
        self._slot_photos = {}
        for slot, cv in self.slots.items():
            cv.delete('all')
            pic = self.bag_picture(parts.get(slot, 0)) if parts.get(slot) else None
            if pic is not None:
                self._slot_photos[slot] = photo(pic)
                cv.create_image(26, 26, image=self._slot_photos[slot])
            cv.config(highlightbackground='#ffd400' if slot == self.subject_slot() else '#777777')
        colour = class_colour(self.project, self.dress.get('class', 1))
        hero = dressed(self.project, colour, parts, cls=self.dress.get('class', 1))
        tile = pygame.Surface((40, 40))
        tile.fill((0, 168, 0))
        tile.blit(hero, (0, 0))
        self._photo = photo(pygame.transform.scale(tile, (40 * SCALE, 40 * SCALE)))
        self.image.config(image=self._photo)
