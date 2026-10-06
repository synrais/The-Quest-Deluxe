"""The Items page: weapons, armour, potions, treasure, ammunition and map pieces, and how a worn item sits on the hero."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import ui
from ..theme import C, px
from .tablepage import TablePage

STATS = ['req_str', 'req_int', 'atk', 'def', 'warm', 'marm', 'str', 'int', 'dex', 'acc', 'power', 'kind']
WORN = ('weapon', 'launcher', 'armour', 'shield', 'helmet', 'amulet')
FILTERS = [('all', 'All'), ('weapon', 'Weapons'), ('wear', 'Armour'), ('potion', 'Potions'), ('ammo', 'Ammo'), ('treasure', 'Treasure'),
           ('map', 'Map pieces')]
CATEGORY = {'weapon': 'weapon', 'launcher': 'weapon', 'armour': 'wear', 'shield': 'wear', 'helmet': 'wear', 'amulet': 'wear',
            'potion': 'potion', 'ammo': 'ammo', 'treasure': 'treasure', 'key': 'treasure', 'chest': 'treasure'}
GROUPS = {'weapon': 'Weapons', 'wear': 'Armour and charms', 'potion': 'Potions', 'ammo': 'Ammunition', 'treasure': 'Treasure and keys',
          'map': 'Map pieces'}
TYPE_NAMES = {'weapon': 'weapon', 'launcher': 'launcher', 'ammo': 'ammunition', 'armour': 'armour', 'shield': 'shield',
              'helmet': 'helmet', 'amulet': 'amulet', 'potion': 'potion', 'treasure': 'treasure', 'key': 'key', 'chest': 'chest',
              'teleporter': 'teleporter', 'exit': 'level exit', 'ladder': 'ladder', 'rope': 'rope', 'stairs': 'stairs', 'hole': 'hole',
              'jump_pad': 'jump pad'}
NEW_KINDS = [('weapon', 'Weapon', 'A sword, club or staff for the hero\'s hand.', 'sword',
              {'type': 'weapon', 'power': 6, 'atk': 5, 'price': 100}),
             ('launcher', 'Bow or sling', 'Shoots ammunition from a distance.', 'line',
              {'type': 'launcher', 'power': 3, 'atk': 0, 'price': 150, 'kind': 4}),
             ('shield', 'Shield', 'Held in the other hand: adds defence.', 'shield', {'type': 'shield', 'def': 5, 'warm': 1, 'price': 80}),
             ('helmet', 'Helmet', 'Worn on the head.', 'helmet', {'type': 'helmet', 'warm': 2, 'price': 80}),
             ('armour', 'Armour', 'Worn on the body: takes damage off every blow.', 'person', {'type': 'armour', 'warm': 4, 'price': 160}),
             ('amulet', 'Amulet', 'A charm that adds to his stats.', 'star', {'type': 'amulet', 'dex': 2, 'price': 120}),
             ('food', 'Food or herb', 'Used from the bag to heal.', 'heart', {'type': 'treasure', 'price': 10, 'use': {'life': 15}}),
             ('treasure', 'Treasure', 'A valuable thing to find and sell.', 'coin', {'type': 'treasure', 'price': 50})]


class ItemsPage(TablePage):
    key = 'items'
    title = 'Items'
    icon = 'sword'
    table = 'items'
    layer = 'item'
    noun = 'item'
    nouns = 'items'
    filters = FILTERS
    card = (94, 104)

    def build(self):
        self.dress = {'class': 1}
        self.hero_box = None
        super().build()
        ui.button(self.bar, 'New ammo…', self.new_ammo_kind, 'plus', 'TButton', 'Make ammunition of a new kind, in stacks of 1 to 20').pack(
            side='left', padx=px(6))
        t = self.schema.t
        t._check_water = lambda: None                # the Studio asks about water itself (below), in its own window

    # list ----------------------------------------------------------------------
    def category(self, row):
        return CATEGORY.get(row.get('type', ''), 'map' if row.get('type') else 'treasure')

    def group(self, row):
        return GROUPS[self.category(row)]

    def order(self, row):
        cats = list(GROUPS)
        return (cats.index(self.category(row)), row['id'])

    def thumb_image(self, row, size, bg='raised', frame=False):
        return self.s.pictures.bag_thumb(row['id'], size)

    def entry_sub(self, row):
        return TYPE_NAMES.get(row.get('type', ''), row.get('type', '')) + (f' · {row["price"]}g' if row.get('price') else '')

    def badges(self, row):
        out = [(f'#{row["id"]}', 'dim'), (TYPE_NAMES.get(row.get('type', ''), row.get('type') or 'item'), 'accent')]
        if row.get('price'):
            out.append((f'{row["price"]} gold', 'warn'))
        if row.get('quest'):
            out.append(('quest item', 'info'))
        return out

    def first_id(self):
        rows = sorted((r for r in self.rows() if r['id'] > 0), key=self.order)
        return rows[0]['id'] if rows else None

    # the hero ------------------------------------------------------------------
    def extra_cards(self, parent):
        self.sec = ui.Section(parent, 'How it looks on the hero', 'drag it into place', open_=True)
        self.sec.pack(fill='x', padx=px(20), pady=(px(8), 0))
        self.hero_holder = ttk.Frame(self.sec.body)
        self.hero_holder.pack(fill='x')

    def shown(self, row):
        self._previews(row)

    def _previews(self, row):
        from editor.hero_preview import HeroPreview, place_of, slot_for
        for w in self.hero_holder.winfo_children():
            w.destroy()
        self.hero_box = None
        worn = bool(place_of(row))
        if row.get('type') not in WORN or not worn:
            self.sec.pack_forget()
            return
        self.sec.pack(fill='x', padx=px(20), pady=(px(8), 0), before=self.inspector)
        box = HeroPreview(self.hero_holder, self.s.project, self.dress, self.place_on_hero)
        box.pack(side='left', anchor='n')
        box.show(row)
        self.hero_box = box
        if row.get('type') in ('weapon', 'launcher', 'shield'):
            from editor.fps_preview import FpsPreview
            fps = FpsPreview(self.hero_holder, self.s.project, box, self.place_on_hero)
            fps.pack(side='left', anchor='n', padx=px(14))
            fps.show(row)

    def place_on_hero(self, key, value, final=True):
        """The hero preview moved, flipped or turned the item: keep it on the item (0 or off leaves the key out)."""
        row = self.row()
        if row is None:
            return
        sch = self.schema
        drop = value is None or (key in ('worn_dx', 'worn_dy', 'fps_dx', 'fps_dy') and not value) or (key == 'worn_rotate' and not value)
        if sch.get(row, key, KeyError) is KeyError and drop:
            return
        with self.s.edit(f'Move {row.get("name", "it")} on the hero', 'items', merge=f'items:{row["id"]}:{key}', source=self.inspector):
            if drop:
                sch.drop(row, key)
            else:
                sch.put(row, key, value)
        if final:
            self.inspector.refresh()
            self._previews(row)

    def edited(self, row, key):
        if key == 'type':
            self._previews(row)
        if key == 'water_walk' and row.get('water_walk'):
            self.check_water()

    def check_water(self):
        walls = self.s.project.tiles.get('walls', [])
        if any(w.get('water') or w.get('freezes_to') for w in walls):
            return
        named = [w for w in walls if 'water' in (w.get('name') or '').lower()]
        if named:
            names = ', '.join(f'{w["id"]} {w.get("name")}' for w in named)
            if ui.confirm(self, 'Walks on water', f'No tile is marked as water yet, so this would walk on nothing. Mark these walls as water now?\n\n{names}', 'Mark them'):
                with self.s.edit('Mark walls as water', 'tiles'):
                    for w in named:
                        w['water'] = True
        else:
            ui.inform(self, 'Walks on water', 'No tile is marked as water yet. On the Tiles page, open the water wall and tick "Is water": '
                      'only then does this item walk on it.')

    # an item dragged from the list onto a slot of the hero ------------------------------
    def on_drag(self, key, phase, x, y):
        if phase == 'start':
            pic = self.s.project.picture('bag', key)
            if pic is not None:
                import pygame
                from editor.hero_preview import Ghost
                self._ghost = Ghost(self)
                flat = pygame.Surface(pic.get_size())
                flat.blit(pic, (0, 0))
                self._ghost.show(flat, x, y)
        elif phase == 'move':
            if getattr(self, '_ghost', None):
                self._ghost.move(x, y)
        elif phase == 'drop':
            ghost, self._ghost = getattr(self, '_ghost', None), None
            if ghost:
                ghost.close()
            if self.hero_box is not None and self.hero_box.winfo_exists():
                self.hero_box.drop_from_list(key, x, y)

    # new -------------------------------------------------------------------------
    def new(self):
        d = ui.Dialog(self, 'A new item', width=px(700))
        ttk.Label(d.body, text='What kind of item?', style='H2.TLabel').pack(anchor='w')
        cards = ui.ChoiceCards(d.body, [(k, t, tx, ic) for k, t, tx, ic, _ in NEW_KINDS], lambda k: None, NEW_KINDS[0][0], columns=2, width=300)
        cards.pack(fill='x', pady=(px(8), 0))
        r = ttk.Frame(d.body)
        r.pack(fill='x', pady=(px(10), 0))
        ttk.Label(r, text='Name').pack(side='left')
        name = tk.StringVar(value='New weapon')
        e = ttk.Entry(r, textvariable=name, width=30)
        e.pack(side='left', padx=px(10))
        cards.command = lambda k: name.set('New ' + next(t for kk, t, *_ in NEW_KINDS if kk == k).lower()) if name.get().startswith('New ') else None
        paint_now = tk.BooleanVar(value=True)
        ttk.Checkbutton(d.body, text='Open the painter afterwards, to draw its pictures', variable=paint_now).pack(anchor='w', pady=(px(8), 0))
        d.add_buttons([('Cancel', None, 'TButton'), ('Make it', 'make', 'Accent.TButton')], default='make')
        if d.run() != 'make':
            return
        kind = next(k for k in NEW_KINDS if k[0] == cards.value)
        p = self.s.project
        rid = p.next_id('items', 1001)
        row = {'id': rid, 'name': name.get().strip() or 'New item', **kind[4]}
        row['bag_name'] = row['name']
        if row['type'] in WORN:
            for k in STATS:
                row.setdefault(k, 0)
            if row['type'] == 'launcher':
                kinds = self.ammo_kinds()
                row['fires'] = kinds[:1]
        self.add_row(row, f'New item: {row["name"]}')
        if paint_now.get():
            self.after(200, lambda: self.paint('items', False, 'On the map'))

    def ammo_kinds(self):
        seen = []
        for r in self.rows():
            if r.get('type') == 'ammo' and r.get('ammo') not in seen:
                seen.append(r['ammo'])
        return seen

    def new_ammo_kind(self):
        name = ui.ask_text(self, 'New ammunition', 'Its name (for example Darts):')
        if not name:
            return
        if name.lower() in (k.lower() for k in self.ammo_kinds()):
            ui.inform(self, 'New ammunition', f'There is already ammunition called {name}.')
            return
        p = self.s.project
        first = p.next_id('items', 1001)
        while any(p.next_id('items', first + k) != first + k for k in range(20)):
            first += 1
        with self.s.edit(f'New ammunition: {name}', 'items'):
            for n in range(1, 21):
                row = {'id': first + n - 1, 'name': f'{name}-{n:02d}', 'type': 'ammo', 'ammo': name.lower(), 'count': n, 'bag_name': name}
                if n == 20:
                    row['price'] = 5
                self.rows().append(row)
            self.rows().sort(key=lambda r: r['id'])
        self.cat = 'all'
        self.seg.choose('all', run=False)
        self.fill()
        self.select(first + 19)
        ui.inform(self, 'New ammunition', f'Made {name} in stacks of 1 to 20 (items {first} to {first + 19}). Give the 20-stack a picture and a '
                  f'price, and tick {name} under Fires on the launchers that shoot it.')

    # pictures: every stack of one kind of ammunition shares its picture -----------
    def set_picture(self, rid, folder, surface, is_bag=False):
        row = self.s.row('items', rid)
        super().set_picture(rid, folder, surface, is_bag)
        if row and row.get('type') == 'ammo':
            p = self.s.project
            others = [r for r in self.rows() if r['id'] != rid and r.get('type') == 'ammo' and r.get('ammo') == row.get('ammo')]
            scopes = [('pic', f, r['id']) for r in others for f in ('items', 'bag')]
            with self.s.edit('Same picture for the whole kind', *scopes):
                for r in others:
                    for f in ('items', 'bag'):
                        img = p.picture(f, rid)
                        if img is not None:
                            p.set_picture(f, r['id'], img)
            self.fill()
