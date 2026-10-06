"""The shape of every page that edits a table of the pack (creatures, items, spells, heroes): a gallery on the left, the chosen
row's picture, name and fields on the right. Subclasses say what is particular to their table."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import filedialog, ttk

import pygame

from studio.art import bag_cell, photo, to_ega

from .. import theme, ui
from ..gallery import Entry, Gallery
from ..inspector import Inspector
from ..model import FOLDER_LAYER, scope_of
from ..schema import Schema
from ..theme import C, px
from .base import Page

OPAQUE = {'bag', 'spells', 'floors'}


class TablePage(Page):
    table = ''
    layer = ''                  # what Pictures.thumb draws for a row: 'mon', 'item', 'spell'
    placeable = True            # the row can be put on a map
    noun = 'entry'              # in words: "a new creature"
    nouns = 'entries'
    skip = ('id', 'name')
    filters = [('all', 'All')]
    card = (94, 104)
    thumb = 44
    list_width = 330
    blurb = ''

    @property
    def scope(self):
        return scope_of(self.table)

    # ── hooks ───────────────────────────────────────────────────────────────
    def category(self, row) -> str:
        return 'all'

    def group(self, row) -> str:
        return ''

    def badges(self, row) -> list:
        """[(text, colour)] under the name."""
        return [(f'#{row["id"]}', 'dim')]

    def thumb_image(self, row, size, bg='raised', frame=False):
        return self.s.pictures.thumb(self.layer, row['id'], size, bg, frame)

    def entry_sub(self, row) -> str:
        return f'#{row["id"]}'

    def new_row(self):
        """The row to add for New (None: cancelled). Subclasses may ask first."""
        return None

    def order(self, row):
        return row['id']

    def extra_cards(self, parent):
        """Widgets to put between the header and the fields (a fight check)."""

    def shown(self, row):
        """The row on show has changed (the fight check refreshes)."""

    def edited(self, row, key):
        """A field was changed."""

    def pictures(self) -> list:
        return list(self.schema.pictures)

    def delete_extra(self, row):
        """Called inside the delete step, to remove what belongs to the row."""

    def after_new(self, row):
        pass

    def on_drag(self, key, phase, x, y):
        """A card is being carried (the Items page drops them on the hero)."""

    # ── build ───────────────────────────────────────────────────────────────
    def build(self):
        self.schema = Schema(self.s, self.table)
        self.rid = None
        self.cat = 'all'
        self.query = ''
        self.paint_buttons = {}
        left = ttk.Frame(self, width=px(self.list_width))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True)
        self._build_list(left)
        self._build_detail(right)
        self.s.on(self.scope, self._changed)
        self.s.on('pictures', self._pictures_changed)

    def _build_list(self, left):
        head = ttk.Frame(left)
        head.pack(fill='x', padx=px(14), pady=(px(14), px(6)))
        ttk.Label(head, text=self.title, style='H2.TLabel').pack(side='left')
        ui.button(head, 'New', self.new, 'plus', 'Accent.TButton', f'Make a new {self.noun}').pack(side='right')
        if len(self.filters) > 1:
            self.seg = ui.Segmented(left, self.filters, self._filter, 'all')
            self.seg.pack(fill='x', padx=px(14))
        self.search_box = ui.SearchBox(left, self._search, 'Search', width=24)
        self.search_box.pack(fill='x', padx=px(14), pady=px(8))
        self.gallery = Gallery(left, on_select=self.select, card=self.card, drag=self.on_drag)
        self.gallery.pack(fill='both', expand=True)

    def _build_detail(self, right):
        self.empty = ui.EmptyState(right, self.icon, f'Pick one on the left, or make a new {self.noun}.', f'Make a {self.noun}', self.new)
        self.detail = ttk.Frame(right)
        self.pane = ui.Scrolled(self.detail)             # the whole detail scrolls together: header, previews and fields
        self.pane.pack(fill='both', expand=True)
        host = self.pane.body
        top = ttk.Frame(host)
        top.pack(fill='x', padx=px(20), pady=(px(16), px(4)))
        self.pic_box = ttk.Frame(top)
        self.pic_box.pack(side='left')
        col = ttk.Frame(top)
        col.pack(side='left', fill='x', expand=True, padx=px(16))
        self.name_var = tk.StringVar()
        e = ttk.Entry(col, textvariable=self.name_var, font=(theme.FONT, 16, 'bold'))
        e.pack(fill='x')
        e.bind('<Return>', lambda ev: self._rename())
        e.bind('<FocusOut>', lambda ev: self._rename())
        self.badge_row = ttk.Frame(col)
        self.badge_row.pack(anchor='w', pady=(px(6), 0))
        bar = ui.Flow(col)
        bar.pack(fill='x', pady=(px(8), 0))
        bar.add(ui.button(bar, 'Duplicate', self.duplicate, 'copy', 'TButton'))
        bar.add(ui.button(bar, '', self.delete, 'trash', 'Tool.TButton', f'Delete this {self.noun}'))
        if self.placeable and self.layer in ('mon', 'item', 'floor', 'wall', 'deco'):
            bar.add(ui.button(bar, 'Put on a map', self.put_on_map, 'map', 'TButton', f'Go to the World page with this {self.noun} ready to paint with'))
        self.bar = bar
        self.uses_label = ttk.Label(col, text='', style='Faint.TLabel', wraplength=px(560), justify='left')
        self.uses_label.pack(anchor='w', pady=(px(6), 0))
        col.bind('<Configure>', lambda e: self.uses_label.configure(wraplength=max(px(200), e.width - px(8))))
        self.extra_cards(host)
        self.inspector = Inspector(host, self.s, self.schema, skip=self.skip, on_change=self._edited, scroller=self.pane)
        self.inspector.pack(fill='x')

    def put_on_map(self):
        """The World page, with this one chosen as what the brush paints."""
        if self.rid is not None:
            self.app.go('world', brush=(self.layer, self.rid), panel='paint', tool='brush')

    # ── the list ────────────────────────────────────────────────────────────
    def rows(self):
        return self.s.rows(self.table)

    def row(self):
        return self.s.row(self.table, self.rid) if self.rid is not None else None

    def entries(self):
        out = []
        for r in sorted(self.rows(), key=self.order):
            if self.cat != 'all' and self.category(r) != self.cat:
                continue
            out.append(Entry(r['id'], r.get('name') or '(no name)', self.entry_sub(r), self.thumb_image(r, self.thumb),
                             group=self.group(r) if self.cat == 'all' else '',
                             search=f'{r.get("name", "")} {r["id"]} {self.category(r)} {self.group(r)}'.lower()))
        return out

    def fill(self):
        self.gallery.set_items(self.entries(), self.query)
        self.gallery.select(self.rid, scroll=False)

    def _filter(self, key):
        self.cat = key
        self.fill()

    def _search(self, text):
        self.query = text
        self.gallery.filter(text)

    # ── the detail ──────────────────────────────────────────────────────────
    def select(self, rid, scroll=True):
        if rid is None:
            return
        self.rid = rid
        self.gallery.select(rid, scroll=scroll)
        self.show_row()

    def show_row(self):
        r = self.row()
        if r is None:
            self.detail.pack_forget()
            self.empty.pack(expand=True)
            return
        self.empty.pack_forget()
        self.detail.pack(fill='both', expand=True)
        self.name_var.set(r.get('name') or '')
        self.header()
        self.inspector.show(self.rid)
        self.shown(r)

    def header(self):
        r = self.row()
        if r is None:
            return
        for w in self.pic_box.winfo_children():
            w.destroy()
        self._imgs = []
        slots = [p for p in self.pictures() if self.has_picture(p[1], r)]
        for label, folder, is_bag in slots:
            box = ttk.Frame(self.pic_box)
            box.pack(side='left', padx=(0, px(12)))
            img = self.picture_image(folder, r)
            self._imgs.append(img)
            tk.Label(box, image=img, bd=0, bg=C['panel']).pack()
            if len(slots) > 1:
                ttk.Label(box, text=label, style='Faint.TLabel').pack()
            row = ttk.Frame(box)
            row.pack(pady=(px(4), 0))
            ui.button(row, 'Paint', lambda f=folder, b=is_bag, l=label: self.paint(f, b, l), 'brush', 'Small.TButton',
                      'Draw or change this picture').pack(side='left')
            ui.button(row, '', lambda f=folder, b=is_bag: self.import_picture(f, b), 'download', 'Tool.TButton',
                      'Use a picture file (converted to the 16 game colours)').pack(side='left', padx=px(3))
        for w in self.badge_row.winfo_children():
            w.destroy()
        for text, colour in self.badges(r):
            ui.Badge(self.badge_row, text, colour).pack(side='left', padx=(0, px(6)))
        used = self.schema.uses(r)
        if used:
            more = f'  and {len(used) - 3} more' if len(used) > 3 else ''
            self.uses_label.configure(text='Used in: ' + '; '.join(used[:3]) + more)
        else:
            self.uses_label.configure(text='')

    def has_picture(self, folder, row) -> bool:
        return True

    def picture_image(self, folder, row):
        layer = FOLDER_LAYER.get(folder)
        size = px(96)
        if layer == 'bag':
            return self.s.pictures.bag_thumb(row['id'], size)
        if layer:
            return self.s.pictures.thumb(layer, row['id'], size, 'raised', frame=True)
        img = self.s.project.picture(folder, row['id'])
        surf = pygame.Surface((size, size))
        surf.fill((60, 60, 60))
        if img is not None:
            surf.blit(pygame.transform.scale(img, (size, size)), (0, 0))
        return photo(surf)

    def _rename(self):
        r = self.row()
        if r is None or self.name_var.get().strip() == (r.get('name') or ''):
            return
        f = next(f for f in self.schema.all_fields() if f.key == 'name')
        self.inspector.commit(f, self.name_var.get().strip())

    def _edited(self, row, key):
        if key == 'name':
            self.name_var.set(row.get('name') or '')
        if key in ('name',):
            self.fill()
        self.header()
        self.edited(row, key)
        self.app.changed_world()

    # ── notifications ───────────────────────────────────────────────────────
    def _changed(self, scope, source):
        if source is self.inspector or not self.built:
            return
        self.fill()
        if self.rid is not None and self.row() is None:
            self.rid = None
        self.show_row()

    def _pictures_changed(self, scope, source):
        if isinstance(scope, tuple) and len(scope) > 2 and scope[1] in {p[1] for p in self.pictures()}:
            self.fill()
            if self.rid is not None:
                self.header()

    # ── pictures ────────────────────────────────────────────────────────────
    def start_picture(self, folder, row):
        return self.s.project.picture(folder, row['id'])

    def picture_templates(self, folder, row):
        p = self.s.project
        return [(f'{r["id"]}  {r.get("name", "")}', lambda r=r: p.picture(folder, r['id']))
                for r in sorted(self.rows(), key=lambda r: r['id']) if r['id'] != row['id'] and p.picture(folder, r['id']) is not None]

    def paint(self, folder, is_bag, label):
        from ..painter import StudioPainter as Painter
        r = self.row()
        if r is None:
            return
        rid = r['id']
        Painter(self, f'{label}: {r.get("name", rid)}', self.start_picture(folder, r),
                lambda surface: self.set_picture(rid, folder, surface, is_bag), opaque=is_bag or folder in OPAQUE,
                templates=self.picture_templates(folder, r), project=self.s.project, folder=folder)

    def import_picture(self, folder, is_bag):
        r = self.row()
        if r is None:
            return
        path = filedialog.askopenfilename(title='A picture (40 x 40 is best)', parent=self.winfo_toplevel(),
                                          filetypes=[('Pictures', '*.png *.gif *.bmp'), ('All files', '*.*')])
        if not path:
            return
        try:
            img = pygame.image.load(path)
        except pygame.error as e:
            ui.inform(self, 'Import', f"Couldn't read that picture: {e}")
            return
        self.set_picture(r['id'], folder, to_ega(img, keep_alpha=not is_bag), is_bag)

    def set_picture(self, rid, folder, surface, is_bag=False):
        p = self.s.project
        folders = [f for _, f, _ in self.pictures()]
        with self.s.edit(f'Change a picture of {self.s.name_of(self.table, rid)}', *[('pic', f, rid) for f in folders]):
            if is_bag and surface.get_flags() & pygame.SRCALPHA:
                surface = bag_cell(p, surface)
            p.set_picture(folder, rid, surface)
            bag = next((f for _, f, b in self.pictures() if b), None)
            if not is_bag and bag and p.picture(bag, rid) is None:
                p.set_picture(bag, rid, bag_cell(p, surface))          # a new item gets a bag picture too
            self.picture_set(rid, folder, surface)
        self.fill()
        self.header()

    def picture_set(self, rid, folder, surface):
        """Inside the picture's edit: more to change with it."""

    # ── new, duplicate, delete ──────────────────────────────────────────────
    def new(self):
        row = self.new_row()
        if row is None:
            return
        self.add_row(row, label=f'New {self.noun}: {row.get("name", "")}')

    def add_row(self, row, label, picture_from=None):
        p = self.s.project
        folders = [f for _, f, _ in self.pictures()]
        with self.s.edit(label, self.scope, *[('pic', f, row['id']) for f in folders]):
            self.rows().append(row)
            self.rows().sort(key=lambda r: r['id'])
            if picture_from is not None:
                for f in folders:
                    img = p.picture(f, picture_from)
                    if img is not None:
                        p.set_picture(f, row['id'], img)
            self.after_new(row)
        self.cat = 'all'
        if hasattr(self, 'seg'):
            self.seg.choose('all', run=False)
        self.fill()
        self.select(row['id'])

    def duplicate(self):
        r = self.row()
        if r is None:
            return
        new = copy.deepcopy(r)
        new['id'] = self.schema.duplicate_id(r)
        if 'name' in new:
            new['name'] = f'{r["name"]} (copy)'
        self.add_row(new, f'Duplicate {r.get("name", r["id"])}', picture_from=r['id'])

    def delete(self):
        r = self.row()
        if r is None:
            return
        used = self.schema.uses(r)
        msg = f'Delete {r.get("name") or r["id"]}?'
        if used:
            msg += '\n\nIt is still used here, and those places would point at nothing:\n  ' + '\n  '.join(used[:10])
            if len(used) > 10:
                msg += f'\n  ... and {len(used) - 10} more'
        msg += '\n\nYou can bring it back with Undo (Ctrl+Z).'
        if not ui.confirm(self, f'Delete a {self.noun}', msg, 'Delete', danger=True):
            return
        rid, p = r['id'], self.s.project
        folders = [f for _, f, _ in self.pictures()]
        with self.s.edit(f'Delete {r.get("name") or rid}', self.scope, *[('pic', f, rid) for f in folders]):
            self.rows().remove(r)
            for f in folders:
                if p.picture(f, rid) is not None:
                    p.set_picture(f, rid, None)
            self.delete_extra(r)
        self.rid = None
        self.fill()
        self.show_row()

    # ── life cycle ──────────────────────────────────────────────────────────
    def first_id(self):
        rows = sorted(self.rows(), key=self.order)
        return rows[0]['id'] if rows else None

    def on_show(self, select=None, new=False, **where):
        self.fill()
        if select is not None and self.s.row(self.table, select) is not None:
            self.rid = select
        if self.rid is None or self.row() is None:
            self.rid = self.first_id()
        self.gallery.select(self.rid, scroll=True)
        self.show_row()
        if new:
            self.after(150, self.new)

    def reload(self):
        self.fill()
        self.show_row()

    def search(self, q):
        out = []
        for r in self.rows():
            if q in (r.get('name') or '').lower() or q == str(r['id']):
                out.append((r.get('name') or f'#{r["id"]}', f'{self.noun} #{r["id"]}', self.icon,
                            lambda r=r: self.app.go(self.key, select=r['id'])))
        return out
