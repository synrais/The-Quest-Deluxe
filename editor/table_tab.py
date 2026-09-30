"""A tab that edits one of the pack's tables (items, creatures, spells, classes): the entries on the
left with a Find box, the chosen entry's fields on the right, and its pictures.

Subclasses describe their table: TABLE, the fields (Field), which fields apply to an entry (when),
its pictures, how to make a new entry, and where an entry is used (so deleting it can warn).
Changes apply as soon as a field is left or a choice is made.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pygame

from .art import photo, to_ega, bag_cell

OPAQUE = {'bag', 'spells', 'floors'}           # pictures with no transparent pixels


class Field:
    def __init__(self, key, label, kind='int', choices=None, when=None, hint='', default=None, width=8,
                 fmt=None, parse=None):
        self.key, self.label, self.kind = key, label, kind
        self.fmt, self.parse = fmt, parse        # 'custom': row -> text, text -> value (ValueError if wrong)
        self.choices = choices            # [(value, label)] for 'choice' and 'multi'
        self.when = when                  # row -> bool: does the field apply to this entry?
        self.hint, self.default, self.width = hint, default, width


class TableTab(ttk.Frame):
    TABLE = ''
    ICON_LAYER = ''                       # the layer whose pictures change with this table ('item', 'mon', ...)
    LIST_ICON = ''                        # the layer the list's icons come from (default ICON_LAYER)
    PICTURES: list = []                   # [(label, sprite folder, is_bag_cell)]
    INTRO = ''

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.row = None
        self.widgets = {}
        self._build()

    # ── what subclasses provide ─────────────────────────────────────────────
    def fields(self) -> list[Field]:
        return []

    def new_row(self) -> dict | None:
        return None

    def uses(self, row) -> list[str]:
        return []

    def duplicate_id(self, row) -> int:
        return self.app.project.next_id(self.TABLE, row['id'] + 1)

    def label(self, row) -> str:
        return f'{row["id"]}  {row.get("name", "")}'

    def after_change(self, row, key, old):
        """A field changed from old (subclasses fix up related fields here)."""

    # ── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        left = ttk.Frame(self, padding=4)
        left.pack(side='left', fill='y')
        f = ttk.Frame(left)
        f.pack(fill='x')
        ttk.Label(f, text='Find').pack(side='left')
        self.find = tk.StringVar()
        self.find.trace_add('write', lambda *a: self.fill_list())
        ttk.Entry(f, textvariable=self.find).pack(side='left', fill='x', expand=True, padx=4)
        lst = ttk.Frame(left)
        lst.pack(fill='both', expand=True, pady=4)
        self.list = ttk.Treeview(lst, show='tree', selectmode='browse', height=20)
        self.list.column('#0', width=250)
        sb = ttk.Scrollbar(lst, orient='vertical', command=self.list.yview)
        self.list.configure(yscrollcommand=sb.set)
        self.list.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.list.bind('<<TreeviewSelect>>', lambda e: self._select())
        self.buttons = ttk.Frame(left)
        self.buttons.pack(fill='x')
        ttk.Button(self.buttons, text='New', command=self.new).pack(side='left')
        ttk.Button(self.buttons, text='Duplicate', command=self.duplicate).pack(side='left', padx=2)
        ttk.Button(self.buttons, text='Delete', command=self.delete).pack(side='left')

        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True)
        if self.INTRO:
            ttk.Label(right, text=self.INTRO, foreground='#555', wraplength=900, justify='left',
                      padding=(8, 4)).pack(anchor='w')
        self.pics = ttk.Frame(right, padding=(8, 4))
        self.pics.pack(anchor='w')
        canvas = tk.Canvas(right, highlightthickness=0)
        sb = ttk.Scrollbar(right, orient='vertical', command=canvas.yview)
        self.form = ttk.Frame(canvas, padding=8)
        self.form.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.form, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')

    # ── the list ────────────────────────────────────────────────────────────
    @property
    def rows(self) -> list:
        return self.app.project.tables[self.TABLE]

    def load(self):
        self.row = None
        self.fill_list()
        rows = self.rows
        if rows:
            self.select(rows[0]['id'])

    def fill_list(self):
        t = self.list
        t.delete(*t.get_children())
        want = self.find.get().strip().lower()
        art = self.app.map_tab.art
        for r in sorted(self.rows, key=lambda r: r['id']):
            text = self.label(r)
            if want and want not in text.lower():
                continue
            layer = self.LIST_ICON or self.ICON_LAYER
            kw = {'image': art.icon(layer, r['id'])} if layer else {}
            t.insert('', 'end', iid=str(r['id']), text='  ' + text, **kw)
        if self.row is not None and t.exists(str(self.row['id'])):
            t.selection_set(str(self.row['id']))

    def select(self, v):
        if self.list.exists(str(v)):
            self.list.selection_set(str(v))
            self.list.see(str(v))
        self._show(next((r for r in self.rows if r['id'] == v), None))

    def _select(self):
        sel = self.list.selection()
        if sel and (self.row is None or str(self.row['id']) != sel[0]):
            self._show(next((r for r in self.rows if str(r['id']) == sel[0]), None))

    # ── fields, with dotted keys for nested values ('look.colour') ──────────
    @staticmethod
    def get(row, key, default=None):
        for part in key.split('.')[:-1]:
            row = row.get(part) or {}
        return row.get(key.split('.')[-1], default)

    @staticmethod
    def put(row, key, value):
        *path, last = key.split('.')
        for part in path:
            row = row.setdefault(part, {})
        row[last] = value

    @staticmethod
    def drop(row, key):
        *path, last = key.split('.')
        for part in path:
            row = row.get(part) or {}
        row.pop(last, None)

    def preview(self, row):
        """A picture drawn rather than stored (the hero's look), or None."""
        return None

    # ── the form ────────────────────────────────────────────────────────────
    def _show(self, row):
        self.row = row
        for w in self.form.winfo_children():
            w.destroy()
        self.widgets = {}
        self._show_pictures()
        if row is None:
            return
        line = 0
        for f in self.fields():
            if f.when and not f.when(row):
                continue
            ttk.Label(self.form, text=f.label).grid(row=line, column=0, sticky='nw', pady=2, padx=(0, 8))
            w = self._widget(f, row)
            w.grid(row=line, column=1, sticky='w', pady=2)
            if f.hint:
                ttk.Label(self.form, text=f.hint, foreground='#666', wraplength=300,
                          justify='left').grid(row=line, column=2, sticky='w', padx=8)
            line += 1

    def _widget(self, f: Field, row):
        value = self.get(row, f.key, f.default)
        if f.kind == 'readonly':
            return ttk.Label(self.form, text=str(value))
        if f.kind == 'bool':
            var = tk.BooleanVar(value=bool(value))
            w = ttk.Checkbutton(self.form, variable=var, command=lambda: self._set(f, var.get()))
        elif f.kind == 'choice':
            labels = [lab for _, lab in f.choices]
            values = [v for v, _ in f.choices]
            w = ttk.Combobox(self.form, values=labels, state='readonly', width=max(f.width, 24))
            w.set(labels[values.index(value)] if value in values else '')
            w.bind('<<ComboboxSelected>>', lambda e: self._set(f, values[labels.index(w.get())]))
            var = None
        elif f.kind == 'multi':
            w = ttk.Frame(self.form)
            chosen = set(value or ())
            for i, (v, lab) in enumerate(f.choices):
                var = tk.BooleanVar(value=v in chosen)
                ttk.Checkbutton(w, text=lab, variable=var,
                                command=lambda v=v, var=var: self._toggle(f, v, var.get())).grid(
                    row=i // 3, column=i % 3, sticky='w', padx=(0, 10))
            return w
        else:
            text = f.fmt(row) if f.kind == 'custom' else ('' if value is None else str(value))
            var = tk.StringVar(value=text)
            w = ttk.Entry(self.form, textvariable=var, width=f.width if f.kind == 'int' else 30 if f.kind == 'str' else 38)
            w.bind('<FocusOut>', lambda e: self._typed(f, var, w))
            w.bind('<Return>', lambda e: self._typed(f, var, w))
        self.widgets[f.key] = (w, var)
        return w

    def _typed(self, f: Field, var, w):
        s = var.get().strip()
        if f.kind == 'int':
            if s == '' and f.default is None:
                value = None
            else:
                try:
                    value = int(s or 0)
                except ValueError:
                    w.configure(foreground='red') if isinstance(w, tk.Entry) else None
                    self.app.status(f'{f.label}: "{s}" is not a number')
                    return
        elif f.kind == 'custom':
            try:
                value = f.parse(s)
            except (ValueError, KeyError, IndexError) as e:
                self.app.status(f'{f.label}: {e}')
                from tkinter import messagebox
                messagebox.showerror(f.label, f'{s!r}: {e}\n\nThe hint beside it shows the form.')
                return
            if value == self.get(self.row, f.key):
                return
        else:
            value = s
        self._set(f, value)

    def _toggle(self, f: Field, v, on):
        cur = list(self.get(self.row, f.key) or [])
        if on and v not in cur:
            cur.append(v)
        elif not on and v in cur:
            cur.remove(v)
        order = [c for c, _ in f.choices]
        self._set(f, sorted(cur, key=lambda c: order.index(c) if c in order else 99))

    def _set(self, f: Field, value):
        row = self.row
        if row is None:
            return
        old = self.get(row, f.key, f.default)
        missing = self.get(row, f.key, KeyError) is KeyError
        if value == old or (f.kind != 'bool' and value in (None, '', []) and missing):
            return
        if f.kind == 'bool':
            if value == bool(f.default):
                self.drop(row, f.key)                 # the default: left out of the file
            else:
                self.put(row, f.key, value)
        elif value is None or (value == '' and f.kind != 'str') or (value == [] and f.kind == 'multi'):
            self.drop(row, f.key)
        else:
            self.put(row, f.key, value)
        self.after_change(row, f.key, old)
        self.app.project.touch(self.TABLE)
        self.app.changed()
        self.list.item(str(row['id']), text='  ' + self.label(row))
        if any(g.when for g in self.fields()):
            self._show(row)                           # which fields apply may have changed
        else:
            self._show_pictures()                     # a drawn preview may have changed

    # ── pictures ────────────────────────────────────────────────────────────
    def _show_pictures(self):
        for w in self.pics.winfo_children():
            w.destroy()
        self._pic_images = []
        if self.row is None:
            return
        p, v = self.app.project, self.row['id']
        drawn = self.preview(self.row)
        if drawn is not None:
            ph = photo(pygame.transform.scale(drawn, (80, 80)))
            self._pic_images.append(ph)
            box = ttk.Frame(self.pics)
            box.grid(row=0, column=len(self.PICTURES), padx=(0, 18), sticky='n')
            ttk.Label(box, text='How it looks').pack(anchor='w')
            ttk.Label(box, image=ph).pack(anchor='w')
        for i, (label, folder, is_bag) in enumerate(self.PICTURES):
            box = ttk.Frame(self.pics)
            box.grid(row=0, column=i, padx=(0, 18), sticky='n')
            ttk.Label(box, text=label).pack(anchor='w')
            s = pygame.Surface((80, 80))
            s.fill((60, 60, 60))
            img = p.picture(folder, v)
            if img is not None:
                s.blit(pygame.transform.scale(img, (80, 80)), (0, 0))
            ph = photo(s)
            self._pic_images.append(ph)
            ttk.Label(box, image=ph).pack(anchor='w')
            ttk.Button(box, text='Paint...', command=lambda f=folder, b=is_bag, l=label: self.paint(f, b, l)).pack(
                fill='x')
            ttk.Button(box, text='Import...', command=lambda f=folder, b=is_bag: self.import_picture(f, b)).pack(
                fill='x')
            if is_bag:
                ttk.Button(box, text='From the map picture', command=self.bag_from_map).pack(fill='x')

    def paint(self, folder, is_bag, label):
        """Open the painter on this picture; saving puts it back here."""
        from .painter import Painter
        row = self.row
        opaque = is_bag or folder in OPAQUE

        def keep(surface):
            if self.row is not row:                  # another entry is showing: store it all the same
                self.select(row['id'])
            self.set_picture(folder, surface, is_bag)
        return Painter(self, f'{label}: {self.label(row)}', self.app.project.picture(folder, row['id']), keep,
                       opaque=opaque)

    def import_picture(self, folder, is_bag):
        path = filedialog.askopenfilename(title='A picture (40 x 40 is best)',
                                          filetypes=[('Pictures', '*.png *.gif *.bmp'), ('All files', '*.*')])
        if not path:
            return
        try:
            img = pygame.image.load(path)
        except pygame.error as e:
            messagebox.showerror('Import', f"Couldn't read {path}: {e}")
            return
        self.set_picture(folder, to_ega(img, keep_alpha=not is_bag), is_bag)

    def set_picture(self, folder, surface, is_bag=False):
        p, v = self.app.project, self.row['id']
        if is_bag:
            surface = bag_cell(p, surface) if surface.get_flags() & pygame.SRCALPHA else surface
        p.set_picture(folder, v, surface)
        bag = next((f for _, f, b in self.PICTURES if b), None)
        if not is_bag and bag and p.picture(bag, v) is None:
            p.set_picture(bag, v, bag_cell(p, surface))          # a new item gets a bag picture too
        self.app.pictures_changed(self.ICON_LAYER, v)
        self.app.changed()
        self._show_pictures()
        self.fill_list()

    def bag_from_map(self):
        p, v = self.app.project, self.row['id']
        mp = next((f for _, f, b in self.PICTURES if not b), None)
        bag = next((f for _, f, b in self.PICTURES if b), None)
        img = p.picture(mp, v)
        if img is None:
            messagebox.showinfo('Bag picture', 'This entry has no map picture yet.')
            return
        self.set_picture(bag, bag_cell(p, img), True)

    # ── new, duplicate, delete ──────────────────────────────────────────────
    def new(self):
        row = self.new_row()
        if row:
            self._add(row)

    def duplicate(self):
        if self.row is None:
            return
        import copy
        row = copy.deepcopy(self.row)
        row['id'] = self.duplicate_id(self.row)
        if 'name' in row:
            row['name'] = f'{row["name"]} (copy)'
        self._add(row)
        p = self.app.project
        for _, folder, _ in self.PICTURES:
            img = p.picture(folder, self.row['id'])
            if img is not None:
                p.set_picture(folder, row['id'], img)

    def _add(self, row):
        self.rows.append(row)
        self.rows.sort(key=lambda r: r['id'])
        self.app.project.touch(self.TABLE)
        self.app.changed()
        self.fill_list()
        self.select(row['id'])

    def delete(self):
        row = self.row
        if row is None:
            return
        used = self.uses(row)
        msg = f'Delete {self.label(row)}?'
        if used:
            msg += '\n\nIt is still used here (these would point at nothing):\n  ' + '\n  '.join(used[:12])
            if len(used) > 12:
                msg += f'\n  ... and {len(used) - 12} more'
        if not messagebox.askyesno('Delete', msg, icon='warning' if used else 'question'):
            return
        self.rows.remove(row)
        p = self.app.project
        for _, folder, _ in self.PICTURES:
            if p.picture(folder, row['id']) is not None:
                p.set_picture(folder, row['id'], None)
        p.touch(self.TABLE)
        self.app.changed()
        self.row = None
        self.fill_list()
        self._show(None)
