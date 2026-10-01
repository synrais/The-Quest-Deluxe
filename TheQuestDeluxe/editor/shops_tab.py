"""The Shops tab: what each shop sells. A level's shops are levels/<n>/shops/<k>.txt; the Map tab's Shop
tool says which screen's shopkeeper runs which shop. The shelves (4 x 10) fill in order, as the game
lays them out. Double-click an item on the right to put it on the next shelf; click a shelf to take
its item off."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import pygame

from .art import photo


def wares(text: str) -> list[int]:
    return [int(v) for v in text.split()][:40]


def text_of(items: list[int]) -> str:
    return '\n'.join(' '.join(str(v) for v in items[k:k + 4]) for k in range(0, len(items), 4)) + '\n'


class ShopsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.level, self.shop = 1, None
        top = ttk.Frame(self, padding=4)
        top.pack(fill='x')
        ttk.Label(top, text='Level').pack(side='left')
        self.levels = ttk.Combobox(top, state='readonly', width=8)
        self.levels.pack(side='left', padx=4)
        self.levels.bind('<<ComboboxSelected>>', lambda e: self._pick_level())
        ttk.Label(top, text='Shop').pack(side='left', padx=(10, 0))
        self.shops = ttk.Combobox(top, state='readonly', width=8)
        self.shops.pack(side='left', padx=4)
        self.shops.bind('<<ComboboxSelected>>', lambda e: self._pick_shop())
        ttk.Button(top, text='New shop', command=self.new_shop).pack(side='left', padx=(10, 2))
        ttk.Button(top, text='Delete shop', command=self.delete_shop).pack(side='left')
        self.where = ttk.Label(top, text='', foreground='#555')
        self.where.pack(side='left', padx=12)

        body = ttk.Frame(self, padding=4)
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body)
        left.pack(side='left', fill='y')
        self.shelf = tk.Canvas(left, width=4 * 64, height=10 * 64, background='#000', highlightthickness=0)
        self.shelf.pack()
        self.shelf.bind('<Button-1>', self._take_off)
        self.shelf.bind('<Motion>', self._hover)
        self.info = ttk.Label(left, text='', foreground='#555', wraplength=260)
        self.info.pack(anchor='w', pady=4)
        right = ttk.Frame(body)
        right.pack(side='left', fill='both', expand=True, padx=12)
        f = ttk.Frame(right)
        f.pack(fill='x')
        ttk.Label(f, text='Find').pack(side='left')
        self.find = tk.StringVar()
        self.find.trace_add('write', lambda *a: self.fill_items())
        ttk.Entry(f, textvariable=self.find, width=24).pack(side='left', padx=4)
        ttk.Label(f, text='(only items with a price are listed)', foreground='#555').pack(side='left')
        # the priced items in two tables side by side: half the scrolling
        both = ttk.Frame(right)
        both.pack(fill='both', expand=True, pady=4)
        self.tables = []
        for n in range(2):
            t = ttk.Treeview(both, columns=('price',), selectmode='browse', height=20)
            t.heading('#0', text='Item')
            t.heading('price', text='Price')
            t.column('#0', width=250)
            t.column('price', width=60, anchor='e')
            t.pack(side='left', fill='both', expand=True, padx=(0 if n == 0 else 6, 0))
            t.bind('<Double-1>', lambda e: self._put_on())
            t.bind('<<TreeviewSelect>>', lambda e, t=t: self._one_selection(t))
            self.tables.append(t)
        self.items = self.tables[0]
        ttk.Button(right, text='Put on the next shelf', command=self._put_on).pack(anchor='w')

    # ── data ────────────────────────────────────────────────────────────────
    def load(self):
        p = self.app.project
        self.levels.config(values=[str(n) for n in range(1, p.levels + 1)])
        self.level = min(self.level, p.levels) or 1
        self.levels.set(str(self.level))
        self._pick_level()
        self.fill_items()

    def _pick_level(self):
        self.level = int(self.levels.get() or 1)
        ks = sorted(self.app.project.shops.get(self.level, {}))
        self.shops.config(values=[str(k) for k in ks])
        self.shop = ks[0] if ks else None
        self.shops.set(str(self.shop) if self.shop else '')
        self.draw()

    def _pick_shop(self):
        self.shop = int(self.shops.get())
        self.draw()

    @property
    def stock(self) -> list[int]:
        return wares(self.app.project.shops[self.level][self.shop]) if self.shop else []

    def _store(self, items):
        p = self.app.project
        p.shops[self.level][self.shop] = text_of(items)
        p.touch(('shops', self.level))
        self.app.changed()
        self.draw()

    def _one_selection(self, chosen):
        """Only one of the two tables has a selection."""
        if chosen.selection():
            for t in self.tables:
                if t is not chosen and t.selection():
                    t.selection_remove(t.selection())

    def _selected_item(self):
        for t in self.tables:
            if t.selection():
                return int(t.selection()[0])
        return None

    def fill_items(self):
        want, art = self.find.get().strip().lower(), self.app.map_tab.art
        rows = []
        for r in sorted(self.app.project.tables['items'], key=lambda r: r['id']):
            if 'price' not in r or not r['id']:
                continue
            text = f'{r["id"]}  {r.get("name") or ""}'
            if not want or want in text.lower():
                rows.append((r, text))
        half = (len(rows) + 1) // 2
        for t, part in zip(self.tables, (rows[:half], rows[half:])):
            t.delete(*t.get_children())
            for r, text in part:
                t.insert('', 'end', iid=str(r['id']), text='  ' + text, values=(r['price'],),
                         image=art.icon('bag', r['id']))

    # ── the shelves ─────────────────────────────────────────────────────────
    def draw(self):
        c = self.shelf
        c.delete('all')
        self._imgs = []
        stock = self.stock
        art = self.app.map_tab.art
        for k in range(40):
            x, y = (k % 4) * 64, (k // 4) * 64
            s = pygame.Surface((64, 64))
            s.fill((0, 0, 0))
            cell = art.tile('bag', stock[k] if k < len(stock) else 0, 60)
            if cell is not None:
                s.blit(cell, (2, 2))
            ph = photo(s)
            self._imgs.append(ph)
            c.create_image(x, y, image=ph, anchor='nw')
        p = self.app.project
        screens = [f'({sx}, {sy})' for (sx, sy), k in (p.constant(self.level, 'SHOPS', {}) or {}).items()
                   if k == self.shop]
        self.where.config(text=(f'Sold on screen{"s" if len(screens) > 1 else ""} {", ".join(screens)} of level '
                                f'{self.level}' if screens else 'No screen has this shop yet (Map tab, Shop tool).')
                          if self.shop else f'Level {self.level} has no shops yet.')
        self.info.config(text=f'{len(stock)} of 40 shelves filled.' if self.shop else '')

    def _cell(self, e):
        k = (e.y // 64) * 4 + e.x // 64
        return k if 0 <= k < 40 else None

    def _hover(self, e):
        k, stock = self._cell(e), self.stock
        if k is not None and k < len(stock):
            p = self.app.project
            r = next((r for r in p.tables['items'] if r['id'] == stock[k]), {})
            self.info.config(text=f'Shelf {k + 1}: {stock[k]} {r.get("name", "")}, {r.get("price", 0)} gold. '
                                  'Click to take it off.')

    def _take_off(self, e):
        k, stock = self._cell(e), self.stock
        if k is not None and k < len(stock):
            del stock[k]
            self._store(stock)

    def _put_on(self):
        chosen = self._selected_item()
        if chosen is None or not self.shop:
            return
        stock = self.stock
        if len(stock) >= 40:
            messagebox.showinfo('Shop', 'All 40 shelves are full.')
            return
        stock.append(chosen)
        self._store(stock)

    def new_shop(self):
        p = self.app.project
        have = p.shops.setdefault(self.level, {})
        k = next((n for n in range(1, 10) if n not in have), None)
        if k is None:
            messagebox.showinfo('Shop', 'A level can have shops 1 to 9.')
            return
        have[k] = '1 3\n'
        p.touch(('shops', self.level))
        self.app.changed()
        self._pick_level()
        self.shops.set(str(k))
        self._pick_shop()

    def delete_shop(self):
        p = self.app.project
        if not self.shop or not messagebox.askyesno('Delete shop', f'Delete shop {self.shop} of level {self.level}?'):
            return
        del p.shops[self.level][self.shop]
        p.touch(('shops', self.level))
        self.app.changed()
        self._pick_level()
