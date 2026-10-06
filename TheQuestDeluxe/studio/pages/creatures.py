"""The Creatures page: monsters, people and allies, with a fight check against any hero and a wizard for making new ones."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import filedialog, ttk

import pygame

from editor.art import bag_cell, to_ega

from .. import archetypes, fightcalc, icons, levelmeta, theme, ui
from ..gallery import Entry, Gallery
from ..inspector import Inspector
from ..schema import Schema
from ..theme import C, px
from .base import Page

VERDICT_COLOURS = {'Pushover': 'ok', 'Easy': 'ok', 'Fair': 'info', 'Tough': 'warn', 'Deadly': 'bad', 'Cannot be hurt': 'bad'}
ROLES = [('all', 'All'), ('mon', 'Monsters'), ('person', 'People'), ('ally', 'Allies')]


def role_of(v: int) -> str:
    return 'mon' if v > 0 else 'person' if v > -100 else 'ally'


ROLE_TITLE = {'mon': 'Monsters', 'person': 'People', 'ally': 'Summoned allies'}


class CreaturesPage(Page):
    key = 'creatures'
    title = 'Creatures'
    icon = 'skull'
    table = 'creatures'

    def build(self):
        self.schema = Schema(self.s, 'creatures')
        self.rid = None
        self.role = 'all'
        self.query = ''
        left = ttk.Frame(self, width=px(330))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True)
        self._build_list(left)
        self._build_detail(right)
        self.s.on('creatures', self._changed)
        self.s.on('pictures', self._pictures_changed)
        self.s.on('classes', lambda sc, src: self.fight.refresh())
        self.s.on('items', lambda sc, src: self.fight.refresh())

    # ── the list ────────────────────────────────────────────────────────────
    def _build_list(self, left):
        head = ttk.Frame(left)
        head.pack(fill='x', padx=px(14), pady=(px(14), px(6)))
        ttk.Label(head, text='Creatures', style='H2.TLabel').pack(side='left')
        ui.button(head, 'New', self.new, 'plus', 'Accent.TButton', 'Make a new creature').pack(side='right')
        seg = ui.Segmented(left, ROLES, self._role, 'all')
        seg.pack(anchor='w', padx=px(14))
        self.search = ui.SearchBox(left, self._search, 'Search', width=24)
        self.search.pack(fill='x', padx=px(14), pady=px(8))
        self.gallery = Gallery(left, on_select=self.select, card=(94, 104))
        self.gallery.pack(fill='both', expand=True)

    def _entries(self):
        pic = self.s.pictures
        out = []
        for c in sorted(self.s.rows('creatures'), key=lambda c: (-(1 if c['id'] > 0 else 0 if c['id'] > -100 else -1), c['id'])):
            r = role_of(c['id'])
            if self.role != 'all' and r != self.role:
                continue
            out.append(Entry(c['id'], c.get('name') or '(no name)', f'#{c["id"]}', pic.thumb('mon', c['id'], 44, 'raised'),
                             group=ROLE_TITLE[r] if self.role == 'all' else '', search=f'{c.get("name", "")} {c["id"]} {r}'.lower()))
        return out

    def _fill(self):
        self.gallery.set_items(self._entries())
        self.gallery.filter(self.query)
        self.gallery.select(self.rid, scroll=False)

    def _role(self, key):
        self.role = key
        self._fill()

    def _search(self, text):
        self.query = text
        self.gallery.filter(text)

    # ── the detail ──────────────────────────────────────────────────────────
    def _build_detail(self, right):
        self.empty = ui.EmptyState(right, 'skull', 'Pick a creature on the left, or make a new one.', 'Make a creature', self.new)
        self.detail = ttk.Frame(right)
        top = ttk.Frame(self.detail)
        top.pack(fill='x', padx=px(20), pady=(px(16), px(4)))
        self.pic = tk.Label(top, bd=0, bg=C['panel'])
        self.pic.pack(side='left')
        col = ttk.Frame(top)
        col.pack(side='left', fill='x', expand=True, padx=px(16))
        self.name_var = tk.StringVar()
        e = ttk.Entry(col, textvariable=self.name_var, font=(theme.FONT, 16, 'bold'))
        e.pack(fill='x')
        e.bind('<Return>', lambda ev: self._rename())
        e.bind('<FocusOut>', lambda ev: self._rename())
        self.badges = ttk.Frame(col)
        self.badges.pack(anchor='w', pady=(px(6), 0))
        bar = ttk.Frame(col)
        bar.pack(anchor='w', pady=(px(8), 0))
        ui.button(bar, 'Paint', self.paint, 'brush', 'TButton', 'Draw or change its picture').pack(side='left')
        ui.button(bar, 'Import', self.import_picture, 'download', 'TButton', 'Use a picture file (converted to the 16 game colours)').pack(side='left', padx=px(6))
        ui.button(bar, 'Duplicate', self.duplicate, 'copy', 'TButton').pack(side='left')
        ui.button(bar, '', self.delete, 'trash', 'Tool.TButton', 'Delete this creature').pack(side='left', padx=px(6))
        self.uses = ttk.Label(col, text='', style='Faint.TLabel', wraplength=px(560), justify='left')
        self.uses.pack(anchor='w', pady=(px(6), 0))
        self.fight = FightCard(self.detail, self)
        self.fight.pack(fill='x', padx=px(20), pady=(px(10), px(4)))
        self.inspector = Inspector(self.detail, self.s, self.schema, skip=('id', '_role', 'name'), on_change=self._edited)
        self.inspector.pack(fill='both', expand=True)

    def select(self, rid, scroll=True):
        if rid is None:
            return
        self.rid = rid
        self.gallery.select(rid, scroll=scroll)
        self._show()

    def row(self):
        return self.s.row('creatures', self.rid)

    def _show(self):
        r = self.row()
        if r is None:
            self.detail.pack_forget()
            self.empty.pack(expand=True)
            return
        self.empty.pack_forget()
        self.detail.pack(fill='both', expand=True)
        self.name_var.set(r.get('name') or '')
        self._header()
        self.inspector.show(self.rid)
        self.fight.refresh()

    def _header(self):
        r = self.row()
        if r is None:
            return
        self.pic.configure(image=self.s.pictures.thumb('mon', r['id'], px(96), 'raised', frame=True))
        for w in self.badges.winfo_children():
            w.destroy()
        from editor.creatures_tab import role
        ui.Badge(self.badges, f'#{r["id"]}', 'dim').pack(side='left')
        ui.Badge(self.badges, role(r['id']), 'accent' if r['id'] > 0 else 'info').pack(side='left', padx=px(6))
        size = int(r.get('size') or 1)
        if size > 1:
            ui.Badge(self.badges, f'{size} × {size} squares', 'warn').pack(side='left')
        used = self.schema.uses(r)
        if used:
            more = f'  and {len(used) - 3} more' if len(used) > 3 else ''
            self.uses.configure(text='Used in: ' + '; '.join(used[:3]) + more)
        else:
            self.uses.configure(text='Not used anywhere yet: put it on a map, or in a spell.')

    def _rename(self):
        r = self.row()
        if r is None or self.name_var.get().strip() == (r.get('name') or ''):
            return
        f = next(f for f in self.schema.all_fields() if f.key == 'name')
        self.inspector.commit(f, self.name_var.get().strip())

    def _edited(self, row, key):
        if key in ('name', 'size', 'att'):
            self._header()
            if key == 'name':
                self.name_var.set(row.get('name') or '')
                self._fill()
        self.fight.refresh()
        self.app.changed_world()

    # ── notifications ───────────────────────────────────────────────────────
    def _changed(self, scope, source):
        if source is self.inspector:
            return
        if not self.visible and not self.built:
            return
        self._fill()
        if self.rid is not None and self.row() is None:
            self.rid = None
        self._show()

    def _pictures_changed(self, scope, source):
        if isinstance(scope, tuple) and len(scope) > 1 and scope[1] == 'creatures':
            self._fill()
            self._header()

    # ── pictures ────────────────────────────────────────────────────────────
    def paint(self):
        from editor.painter import Painter
        r = self.row()
        if r is None:
            return
        p, rid = self.s.project, r['id']
        templates = [(f'{c["id"]}  {c.get("name", "")}', lambda c=c: p.picture('creatures', c['id']))
                     for c in sorted(self.s.rows('creatures'), key=lambda c: c['id']) if c['id'] != rid and p.picture('creatures', c['id']) is not None]

        def keep(surface):
            self.set_picture(rid, surface)
        Painter(self, f'Picture: {r.get("name", rid)}', p.picture('creatures', rid), keep, opaque=False, templates=templates,
                project=p, folder='creatures')

    def import_picture(self):
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
        self.set_picture(r['id'], to_ega(img, keep_alpha=True))

    def set_picture(self, rid, surface):
        with self.s.edit('Change a creature\'s picture', ('pic', 'creatures', rid)):
            self.s.project.set_picture('creatures', rid, surface)
        self._fill()
        self._header()

    # ── new, duplicate, delete ──────────────────────────────────────────────
    def new(self):
        w = CreatureWizard(self)
        rid = w.run()
        if rid is not None:
            self.role = 'all'
            self._fill()
            self.select(rid)

    def duplicate(self):
        r = self.row()
        if r is None:
            return
        p = self.s.project
        new = copy.deepcopy(r)
        new['id'] = self.schema.duplicate_id(r)
        new['name'] = f'{r.get("name", "")} (copy)'
        with self.s.edit('Duplicate a creature', 'creatures', ('pic', 'creatures', new['id'])):
            self.s.rows('creatures').append(new)
            self.s.rows('creatures').sort(key=lambda c: c['id'])
            img = p.picture('creatures', r['id'])
            if img is not None:
                p.set_picture('creatures', new['id'], img)
        self._fill()
        self.select(new['id'])

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
        if not ui.confirm(self, 'Delete a creature', msg, 'Delete', danger=True):
            return
        rid = r['id']
        with self.s.edit(f'Delete {r.get("name") or rid}', 'creatures', ('pic', 'creatures', rid)):
            self.s.rows('creatures').remove(r)
            if self.s.project.picture('creatures', rid) is not None:
                self.s.project.set_picture('creatures', rid, None)
        self.rid = None
        self._fill()
        self._show()

    # ── life cycle ──────────────────────────────────────────────────────────
    def on_show(self, select=None, **where):
        self._fill()
        if select is not None and self.row() is not None or (select is not None and self.s.row('creatures', select)):
            self.rid = select
        if self.rid is None and self.s.rows('creatures'):
            self.rid = next((c['id'] for c in sorted(self.s.rows('creatures'), key=lambda c: c['id']) if c['id'] > 0),
                            self.s.rows('creatures')[0]['id'])
        self.gallery.select(self.rid, scroll=True)
        self._show()

    def reload(self):
        self._fill()
        self._show()

    def search(self, q):
        out = []
        for c in self.s.rows('creatures'):
            if q in (c.get('name') or '').lower() or q == str(c['id']):
                out.append((c.get('name') or f'#{c["id"]}', f'creature #{c["id"]}', 'skull', lambda c=c: self.app.go('creatures', select=c['id'])))
        return out


class FightCard(ui.Card):
    """How this creature fares against a hero: the numbers in words, and a strip showing every hero level from 1 to 20."""

    def __init__(self, master, page):
        super().__init__(master, pad=14)
        self.page, self.s = page, page.s
        f = self.inner
        head = ttk.Frame(f, style='Raised.TFrame')
        head.pack(fill='x')
        ttk.Label(head, text='Fight check', style='H3.TLabel', background=C['raised']).pack(side='left')
        ttk.Label(head, text='against', style='Raised.Dim.TLabel').pack(side='left', padx=px(10))
        self.cls = ttk.Combobox(head, state='readonly', width=12)
        self.cls.pack(side='left')
        ttk.Label(head, text='at level', style='Raised.Dim.TLabel').pack(side='left', padx=px(10))
        self.level = ui.Number(head, 1, 60, int(page.app.settings.get('calc_level', 5)), commit=self._level, soft_max=30, width=3,
                               raised=True)
        self.level.pack(side='left')
        self.cls.bind('<<ComboboxSelected>>', lambda e: self._class())
        row = ttk.Frame(f, style='Raised.TFrame')
        row.pack(fill='x', pady=(px(10), 0))
        self.badge = tk.Label(row, text='', font=(theme.FONT, 12, 'bold'), padx=px(12), pady=px(4), bd=0)
        self.badge.pack(side='left', anchor='n')
        self.text = ttk.Label(row, text='', style='Raised.TLabel', wraplength=px(520), justify='left')
        self.text.pack(side='left', padx=px(14), anchor='n')
        self.strip = tk.Canvas(f, height=px(30), highlightthickness=0, bg=C['raised'])
        self.strip.pack(fill='x', pady=(px(10), 0))
        self.strip.bind('<Motion>', self._hover)
        self.strip.bind('<Leave>', lambda e: self.tip.configure(text=''))
        self.tip = ttk.Label(f, text='', style='Raised.Dim.TLabel')
        self.tip.pack(anchor='w')
        bal = ttk.Frame(f, style='Raised.TFrame')
        bal.pack(fill='x', pady=(px(6), 0))
        ttk.Label(bal, text='Balance it so this hero loses about', style='Raised.TLabel').pack(side='left')
        self.target = ui.Number(bal, 5, 95, 30, slider=False, width=3, raised=True)
        self.target.pack(side='left', padx=px(6))
        ttk.Label(bal, text='% of his life per fight', style='Raised.TLabel').pack(side='left')
        ui.button(bal, 'Balance', self.balance, 'dice', 'TButton', 'Set its life and power for you, keeping their proportion').pack(side='left', padx=px(10))
        self._cells = []
        self._fill_classes()

    def _fill_classes(self):
        classes = self.s.rows('classes')
        names = [f'{c["id"]} {c["name"]}' for c in classes]
        self.cls.configure(values=names)
        want = self.page.app.settings.get('calc_class', self.page.app.settings.get('hero'))
        self.cls.set(next((n for n in names if n.split()[0] == str(want)), names[0] if names else ''))

    def class_id(self):
        v = self.cls.get()
        return int(v.split()[0]) if v else None

    def _class(self):
        self.page.app.settings['calc_class'] = self.class_id()
        self.refresh()

    def _level(self, v):
        self.page.app.settings['calc_level'] = v
        self.refresh()

    def hero(self):
        cid = self.class_id()
        if cid is None:
            return None
        lv = self.level.get()
        return fightcalc.hero_at(self.s.project, cid, lv, fightcalc.gear_for_level(self.s.project, cid, lv))

    def refresh(self):
        if not self.winfo_exists():
            return
        classes = [f'{c["id"]} {c["name"]}' for c in self.s.rows('classes')]
        if list(self.cls.cget('values')) != classes:
            self._fill_classes()
        mon, h = self.page.row(), self.hero()
        if mon is None or h is None or not h.life:
            return
        d = fightcalc.duel(h, mon)
        colour = C[VERDICT_COLOURS.get(d.verdict, 'info')]
        self.badge.configure(text=d.verdict, bg=colour, fg='#101114')
        lines = fightcalc.describe(d, h, mon)
        if d.note:
            lines.append(d.note)
        self.text.configure(text='\n'.join(lines))
        self._heat(mon)

    def _heat(self, mon):
        c = self.strip
        c.delete('all')
        cid = self.class_id()
        data = fightcalc.heat(self.s.project, mon, cid, range(1, 21), runs=120)
        self._cells = data
        w = max(px(300), c.winfo_width() or px(600))
        cw = w / 20
        for i, (lv, d) in enumerate(data):
            colour = C[VERDICT_COLOURS.get(d.verdict, 'info')]
            c.create_rectangle(i * cw + 1, 0, (i + 1) * cw - 1, px(18), fill=colour, outline='')
            if lv in (1, 5, 10, 15, 20) or lv == self.level.get():
                c.create_text(i * cw + cw / 2, px(25), text=str(lv), fill=C['dim'], font=(theme.FONT, 8))
        cur = self.level.get()
        if 1 <= cur <= 20:
            c.create_rectangle((cur - 1) * cw, 0, cur * cw, px(18), outline=C['text'], width=2)

    def _hover(self, e):
        if not self._cells:
            return
        w = max(px(300), self.strip.winfo_width())
        i = max(0, min(19, int(e.x / (w / 20))))
        lv, d = self._cells[i]
        self.tip.configure(text=f'Level {lv}: {d.verdict}. He loses about {d.life_lost_pct * 100:.0f}% of his life and wins {d.win * 100:.0f}% of fights.')

    def balance(self):
        mon, h = self.page.row(), self.hero()
        if mon is None or h is None:
            return
        res = fightcalc.tune(h, mon, self.target.get() / 100)
        if res is None:
            ui.inform(self, 'Balance', 'This hero cannot hurt it at all (its armour or defence is too high for his weapon). '
                      'Lower its armour or defence first, or pick another hero.')
            return
        life, power = res
        name = mon.get('name') or mon['id']
        with self.s.edit(f'Balance {name}', 'creatures', merge=None):
            mon['life'], mon['power'] = life, power
        self.page.inspector.refresh()
        self.refresh()
        self.page.app.say(f'{name} now has life {life} and power {power}.', 'ok')


class CreatureWizard(ui.Dialog):
    """Make a creature from a kind (brute, archer, mage, boss ...), give it a name and a toughness, and it exists."""

    def __init__(self, page):
        super().__init__(page, 'A new creature', width=px(760))
        self.page, self.s = page, page.s
        self.kinds = archetypes.available(self.s.project)
        self.kind = self.kinds[0] if self.kinds else None
        self.tier = 3
        ttk.Label(self.body, text='What kind of creature is it?', style='H2.TLabel').pack(anchor='w')
        ttk.Label(self.body, text='It starts as a copy of one that is already in the quest, so everything it needs is there. '
                  'Then make it your own.', style='Dim.TLabel', wraplength=px(700)).pack(anchor='w', pady=(0, px(8)))
        options = [(k.key, k.title, k.text, k.icon) for k in self.kinds]
        self.cards = ui.ChoiceCards(self.body, options, self._kind, options[0][0], columns=3, width=210)
        self.cards.pack(fill='x')
        row = ttk.Frame(self.body)
        row.pack(fill='x', pady=(px(12), 0))
        ttk.Label(row, text='Name').pack(side='left')
        self.name = tk.StringVar(value='New ' + self.kind.title.lower() if self.kind else 'New creature')
        e = ttk.Entry(row, textvariable=self.name, width=28)
        e.pack(side='left', padx=px(10))
        e.focus_set()
        e.select_range(0, 'end')
        ttk.Label(row, text='How tough').pack(side='left', padx=(px(16), px(6)))
        self.tier_box = ui.Number(row, 1, 10, 3, commit=self._tier, live=self._tier, width=3)
        self.tier_box.pack(side='left')
        self.preview = ttk.Label(self.body, text='', style='Dim.TLabel', wraplength=px(700))
        self.preview.pack(anchor='w', pady=(px(10), 0))
        self.add_buttons([('Cancel', None, 'TButton'), ('Make it', 'make', 'Accent.TButton')], default='make')
        self._preview()

    def _kind(self, key):
        self.kind = next(k for k in self.kinds if k.key == key)
        if self.name.get().startswith('New '):
            self.name.set('New ' + self.kind.title.lower())
        self._preview()

    def _tier(self, v):
        self.tier = v
        self._preview()

    def _preview(self):
        if not self.kind:
            return
        row, base = archetypes.make(self.s.project, self.kind, self.name.get(), self.tier)
        self.preview.configure(text=f'Starts as {base.get("name")}: life {row["life"]}, power {row["power"]}, attack {row["atk"]}, '
                                    f'defence {row["def"]}.   You can fine tune everything afterwards, and Balance sets it for a hero.')

    def close(self, value):
        if value == 'make' and self.kind:
            p = self.s.project
            row, base = archetypes.make(p, self.kind, self.name.get().strip() or 'New creature', self.tier)
            rid = row['id']
            with self.s.edit(f'New creature: {row["name"]}', 'creatures', ('pic', 'creatures', rid)):
                self.s.rows('creatures').append(row)
                self.s.rows('creatures').sort(key=lambda c: c['id'])
                img = p.picture('creatures', base['id'])
                if img is not None:
                    p.set_picture('creatures', rid, img)
            super().close(rid)
            return
        super().close(None)
