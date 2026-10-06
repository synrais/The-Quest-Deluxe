"""The Shops page: what each shop sells, laid out on its shelves as the game shows them."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import levelmeta, theme, ui, worldgen
from ..gallery import Entry, Gallery
from ..theme import C, px
from .base import Page

COLS, ROWS, CELL = 4, 10, 60


def wares(text: str) -> list:
    return [int(v) for v in text.split()][:COLS * ROWS]


def text_of(items: list) -> str:
    return '\n'.join(' '.join(str(v) for v in items[k:k + COLS]) for k in range(0, len(items), COLS)) + '\n'


class ShopsPage(Page):
    key = 'shops'
    title = 'Shops'
    icon = 'coin'

    def build(self):
        self.shop = None                                  # (level, number)
        self.cat = 'all'
        self._imgs = []
        left = ttk.Frame(self, width=px(300))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        head = ttk.Frame(left)
        head.pack(fill='x', padx=px(14), pady=(px(14), px(6)))
        ttk.Label(head, text='Shops', style='H2.TLabel').pack(side='left')
        ui.button(head, 'New', self.new_shop, 'plus', 'Accent.TButton', 'Make a shop on a level').pack(side='right')
        self.list = Gallery(left, on_select=self._pick, list_mode=True)
        self.list.pack(fill='both', expand=True)
        mid = ttk.Frame(self)
        mid.pack(side='left', fill='y', padx=px(20))
        self.empty = ui.EmptyState(self, 'coin', 'No shops yet.', 'Make a shop', self.new_shop)
        self.title_label = ttk.Label(mid, text='', style='H1.TLabel')
        self.title_label.pack(anchor='w', pady=(px(16), 0))
        self.where = ttk.Label(mid, text='', style='Dim.TLabel')
        self.where.pack(anchor='w')
        self.canvas = tk.Canvas(mid, width=COLS * (CELL + 4) + 4, height=ROWS * (CELL + 4) + 4, bg=C['canvas'], highlightthickness=1,
                                highlightbackground=C['line'])
        self.canvas.pack(pady=px(10))
        self.canvas.bind('<Button-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.canvas.bind('<Motion>', self._hover)
        self.canvas.bind('<Leave>', lambda e: self._info_default())
        self.info = ttk.Label(mid, text='', style='Dim.TLabel', wraplength=COLS * (CELL + 4))
        self.info.pack(anchor='w')
        bar = ttk.Frame(mid)
        bar.pack(anchor='w', pady=px(8))
        ui.button(bar, 'Suggest wares', self.suggest, 'sparkle', 'TButton', 'Fill the shelves with potions and gear that suit this level').pack(side='left')
        ui.button(bar, 'Sort by price', self.sort, 'list', 'TButton').pack(side='left', padx=px(6))
        ui.button(bar, 'Clear', self.clear, 'eraser', 'TButton').pack(side='left')
        ui.button(bar, '', self.delete, 'trash', 'Tool.TButton', 'Delete this shop').pack(side='left', padx=px(6))
        self.right = ttk.Frame(self)
        self.right.pack(side='left', fill='both', expand=True)
        ui.vsep(self).pack(side='left', fill='y', before=self.right)
        ttk.Label(self.right, text='Things to sell', style='H2.TLabel').pack(anchor='w', padx=px(14), pady=(px(14), px(6)))
        ttk.Label(self.right, text='Click one to put it on the next shelf. Only items with a price are listed.', style='Dim.TLabel').pack(anchor='w', padx=px(14))
        self.cats = ui.Segmented(self.right, [('all', 'All'), ('weapon', 'Weapons'), ('wear', 'Armour'), ('potion', 'Potions'), ('other', 'Other')],
                                 self._cat, 'all')
        self.cats.pack(anchor='w', padx=px(14), pady=px(8))
        self.search_box = ui.SearchBox(self.right, lambda t: self.picker.filter(t), 'Search', width=26)
        self.search_box.pack(fill='x', padx=px(14))
        self.picker = Gallery(self.right, on_select=self._add, card=(90, 96))
        self.picker.pack(fill='both', expand=True, pady=px(6))
        self.s.on('shops', self._changed)
        self.s.on('script', lambda sc, src: self._fill_list())
        self.s.on('quest', lambda sc, src: self._fill_list())
        self.s.on('items', lambda sc, src: self._fill_picker())

    # the list --------------------------------------------------------------------
    def _all(self):
        out = []
        for n in range(1, self.s.levels + 1):
            for k in sorted(self.s.project.shops.get(n, {})):
                out.append((n, k))
        return out

    def _fill_list(self):
        if not self.built:
            return
        entries = []
        for n, k in self._all():
            screens = [f'({a}, {b})' for (a, b), kk in (levelmeta.get(self.s, n, 'SHOPS', {}) or {}).items() if kk == k]
            count = len(wares(self.s.project.shops[n][k]))
            entries.append(Entry((n, k), f'Level {n}, shop {k}', f'{count} things' + (f' · screen {screens[0]}' if screens else ' · on no screen yet'),
                                 self.s.pictures.thumb('item', wares(self.s.project.shops[n][k])[0], 40) if count else None,
                                 group=levelmeta.title(self.s, n)))
        self.list.set_items(entries)
        self.list.select(self.shop, scroll=False)

    def _pick(self, key):
        self.shop = key
        self._show()

    def _changed(self, scope, source):
        if source is self:
            return
        self._fill_list()
        if self.shop and self.shop[1] not in self.s.project.shops.get(self.shop[0], {}):
            self.shop = None
        self._show()

    # the shelves -----------------------------------------------------------------
    def stock(self):
        if not self.shop:
            return []
        return wares(self.s.project.shops.get(self.shop[0], {}).get(self.shop[1], ''))

    def _show(self):
        if self.shop is None:
            all_ = self._all()
            self.shop = all_[0] if all_ else None
        if self.shop is None:
            self.title_label.configure(text='No shops yet')
            self.where.configure(text='')
            self._draw()
            return
        n, k = self.shop
        self.list.select(self.shop, scroll=True)
        self.title_label.configure(text=f'Level {n}, shop {k}')
        screens = [f'({a}, {b})' for (a, b), kk in (levelmeta.get(self.s, n, 'SHOPS', {}) or {}).items() if kk == k]
        self.where.configure(text=(f'Sold on screen {", ".join(screens)} of level {n}.' if screens else
                                   'No screen has this shop yet: use the Shop tool on the World page.'))
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete('all')
        self._imgs = []
        stock = self.stock()
        pic = self.s.pictures
        for k in range(COLS * ROWS):
            x, y = 4 + (k % COLS) * (CELL + 4), 4 + (k // COLS) * (CELL + 4)
            c.create_rectangle(x, y, x + CELL, y + CELL, fill='#000000', outline=C['line'])
            if k < len(stock):
                img = pic.bag_thumb(stock[k], CELL - 4)
                self._imgs.append(img)
                c.create_image(x + 2, y + 2, image=img, anchor='nw')
        self._info_default()

    def _info_default(self):
        stock = self.stock()
        total = sum((self.s.row('items', v) or {}).get('price', 0) or 0 for v in stock)
        self.info.configure(text=f'{len(stock)} of {COLS * ROWS} shelves filled; everything costs {total} gold together.' if self.shop else '')

    def _cell(self, e):
        col, row = (e.x - 4) // (CELL + 4), (e.y - 4) // (CELL + 4)
        k = row * COLS + col
        return k if 0 <= col < COLS and 0 <= row < ROWS else None

    def _hover(self, e):
        k, stock = self._cell(e), self.stock()
        if k is not None and k < len(stock):
            r = self.s.row('items', stock[k]) or {}
            self.info.configure(text=f'Shelf {k + 1}: {r.get("name", stock[k])}, {r.get("price", 0)} gold.  Click to take it off, drag to move it.')
        else:
            self._info_default()

    def _press(self, e):
        k = self._cell(e)
        self._grab = k if k is not None and k < len(self.stock()) else None

    def _drag(self, e):
        pass

    def _release(self, e):
        grab, self._grab = getattr(self, '_grab', None), None
        k, stock = self._cell(e), self.stock()
        if grab is None:
            return
        if k == grab:                                      # a click: take it off
            del stock[grab]
        elif k is not None:                                # dragged: move it there
            item = stock.pop(grab)
            stock.insert(min(k, len(stock)), item)
        self._store(stock, 'Change a shop')

    def _store(self, items, label):
        n, k = self.shop
        with self.s.edit(label, ('shops', n), merge=f'shop:{n}:{k}', source=self):
            self.s.project.shops[n][k] = text_of(items)
        self._draw()
        self._fill_list()

    # the picker ------------------------------------------------------------------
    def _cat(self, key):
        self.cat = key
        self._fill_picker()

    def _fill_picker(self):
        if not self.built:
            return
        out = []
        pic = self.s.pictures
        for r in sorted(self.s.rows('items'), key=lambda r: r['id']):
            if 'price' not in r or not r['id']:
                continue
            ty = r.get('type', '')
            cat = 'weapon' if ty in ('weapon', 'launcher') else 'wear' if ty in ('armour', 'shield', 'helmet', 'amulet') else \
                'potion' if ty == 'potion' else 'other'
            if self.cat != 'all' and cat != self.cat:
                continue
            out.append(Entry(r['id'], r.get('name') or f'#{r["id"]}', f'{r["price"]} gold', pic.bag_thumb(r['id'], 44),
                             search=f'{r.get("name", "")} {ty} {r["id"]}'.lower()))
        self.picker.set_items(out)
        self.picker.select(None, scroll=False)

    def _add(self, item):
        if not self.shop or item is None:
            return
        stock = self.stock()
        if len(stock) >= COLS * ROWS:
            self.app.say('All 40 shelves are full.', 'warn')
            return
        stock.append(item)
        self._store(stock, 'Put something on a shelf')
        self.picker.select(None, scroll=False)

    # actions ---------------------------------------------------------------------
    def new_shop(self):
        n = self.shop[0] if self.shop else min(levelmeta_level(self), self.s.levels)
        d = ui.Dialog(self, 'A new shop', width=px(380))
        ttk.Label(d.body, text='Which level is it on?', style='H3.TLabel').pack(anchor='w')
        pick = tk.StringVar(value=f'{n}   {levelmeta.title(self.s, n)}')
        box = ttk.Combobox(d.body, state='readonly', textvariable=pick, values=[f'{k}   {levelmeta.title(self.s, k)}' for k in range(1, self.s.levels + 1)], width=34)
        box.pack(anchor='w', pady=(px(6), 0))
        ttk.Label(d.body, text='Then put it on a screen with the Shop tool on the World page.', style='Dim.TLabel',
                  wraplength=px(340)).pack(anchor='w', pady=(px(10), 0))
        d.add_buttons([('Cancel', None, 'TButton'), ('Make it', 'make', 'Accent.TButton')], default='make')
        if d.run() != 'make':
            return
        n = int(pick.get().split()[0])
        have = self.s.project.shops.setdefault(n, {})
        k = next((i for i in range(1, 10) if i not in have), None)
        if k is None:
            ui.inform(self, 'Shops', 'A level can have shops 1 to 9.')
            return
        with self.s.edit('New shop', ('shops', n), source=self):
            have[k] = text_of(worldgen.shop_wares(_FakeGen(self.s.project), 0.3)[:8])
        self.shop = (n, k)
        self._fill_list()
        self._show()

    def delete(self):
        if not self.shop:
            return
        n, k = self.shop
        if not ui.confirm(self, 'Delete a shop', f'Delete shop {k} of level {n}?\n\nYou can bring it back with Undo (Ctrl+Z).', 'Delete', danger=True):
            return
        with self.s.edit('Delete a shop', ('shops', n), source=self):
            del self.s.project.shops[n][k]
        self.shop = None
        self._fill_list()
        self._show()

    def suggest(self):
        if not self.shop:
            return
        n, k = self.shop
        progress = (n - 1) / max(1, self.s.levels - 1)
        self._store(worldgen.shop_wares(_FakeGen(self.s.project), progress), 'Suggest wares')

    def sort(self):
        stock = sorted(self.stock(), key=lambda v: ((self.s.row('items', v) or {}).get('price') or 0, v))
        self._store(stock, 'Sort a shop by price')

    def clear(self):
        if self.shop and ui.confirm(self, 'Clear a shop', 'Take everything off the shelves?', 'Clear'):
            self._store([], 'Clear a shop')

    def on_show(self, level=None, shop=None, **where):
        self._fill_list()
        self._fill_picker()
        if level and shop:
            self.shop = (int(level), int(shop))
        elif self.shop and self.shop[1] not in self.s.project.shops.get(self.shop[0], {}):
            self.shop = None
        self._show()

    def reload(self):
        self.shop = None
        self.on_show()


def levelmeta_level(page):
    w = page.app.pages.get('world')
    return getattr(w, 'level', 1) if w is not None else 1


class _FakeGen:
    """worldgen.shop_wares wants something with the project and the difficulty: a stand-in for a whole generator."""

    def __init__(self, project):
        self.project = project

        class Q:
            difficulty = 'normal'
        self.q = Q()
        import random
        self.rng = random.Random(1)
