"""The Settings page: the quest's own settings (quest.json) and how the Studio looks."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

from engine.pack import Pack

from .. import theme, ui
from ..model import save_settings
from ..theme import C, px
from .base import Page
from .world_level import ColourRow

RECLASS = [(False, 'Keep the class', 'The hero keeps the class he chose.'),
           (True, "Quest I's rule", 'The stats pick Knight, Mage, Rogue or Monk at each level-up, as in the original.'),
           ('stats', 'By the stats', "The class whose starting stats are most like the hero's.")]
POTION_FIELDS = (('life', 'Life'), ('mana', 'Mana'))
NUMBER_FIELDS = (('berserk', 'Berserk turns'), ('foresight', 'Foresight turns'), ('shrink', 'Shrink turns'), ('grow', 'Grow turns'))
ORIGINAL_POTIONS = {1: 'Minor Health', 2: 'Full Health', 3: 'Minor Mana', 4: 'Full Mana', 5: 'Minor Restoration', 6: 'Full Restoration',
                    7: 'Cure Poison', 8: 'Berserker'}


class SettingsPage(Page):
    key = 'settings'
    intro = "The quest's title and author, how the hero starts and the rules of the game. Everything saves by itself."
    title = 'Settings'
    icon = 'scroll'

    def build(self):
        self.header(self)
        self.scroll = ui.Scrolled(self)
        self.scroll.pack(fill='both', expand=True)
        self.body = self.scroll.body
        self.s.on('quest', self._external)
        self._build()

    def _external(self, scope, source):
        if source is not self and self.built:
            self._build()

    # ── build ───────────────────────────────────────────────────────────────
    def _card(self, title, blurb=''):
        head = ttk.Frame(self.body)
        head.pack(fill='x', padx=px(24), pady=(px(20), px(4)))
        ttk.Label(head, text=title, style='H2.TLabel').pack(side='left')
        if blurb:
            ttk.Label(head, text=blurb, style='Dim.TLabel').pack(side='left', padx=px(12), pady=(px(6), 0))
        card = ui.Card(self.body, pad=14)
        card.pack(fill='x', padx=px(24), pady=px(4))
        return card.inner

    def _row(self, parent, label, tip=''):
        r = ttk.Frame(parent, style='Raised.TFrame')
        r.pack(fill='x', pady=3)
        lab = ttk.Label(r, text=label, style='Raised.TLabel', width=26)
        lab.pack(side='left')
        if tip:
            ui.tip(lab, tip)
        return r

    def _build(self):
        for w in self.body.winfo_children():
            w.destroy()
        q = self.s.project.quest
        p = self.s.project
        # about
        f = self._card('This quest')
        for key, label, kind in (('title', 'Title', str), ('author', 'Author', str), ('year', 'Year', int)):
            r = self._row(f, label)
            var = tk.StringVar(value='' if q.get(key) is None else str(q.get(key)))
            e = ttk.Entry(r, textvariable=var, width=36)
            e.pack(side='left')
            for ev in ('<Return>', '<FocusOut>'):
                e.bind(ev, lambda ev_, k=key, v=var, kd=kind, e=e: self._text(k, v, kd, e))
        r = self._row(f, 'First level', 'The level a new game begins on.')
        box = ttk.Combobox(r, state='readonly', width=34, values=[f'{n}   {self._title(n)}' for n in range(1, p.levels + 1)])
        box.set(f'{q.get("first_level", 1)}   {self._title(q.get("first_level", 1))}')
        box.pack(side='left')
        box.bind('<<ComboboxSelected>>', lambda e: self._put('first_level', int(box.get().split()[0]), 'Change the first level'))
        r = self._row(f, 'A giant takes up', 'How many squares across a hero under a giant potion takes up.')
        ui.Number(r, 1, 5, int(q.get('giant_size') or 2), commit=lambda v: self._put('giant_size', v, 'Change the giant size'), slider=False,
                  width=3, raised=True).pack(side='left')
        ttk.Label(r, text=' squares across', style='Raised.Dim.TLabel').pack(side='left')
        r = self._row(f, 'Folder')
        ttk.Label(r, text=p.root, style='Raised.Dim.TLabel').pack(side='left')
        ui.button(r, 'Open', self._open_folder, None, 'Small.TButton').pack(side='left', padx=px(10))
        ttk.Label(f, text=f'{p.levels} levels · {len(p.tables["items"])} items · {len(p.tables["creatures"])} creatures · '
                  f'{len(p.tables["spells"])} spells · {len(p.tables["classes"])} classes', style='Raised.Dim.TLabel').pack(anchor='w', pady=(px(6), 0))

        # heroes
        f = self._card('The hero', 'what he starts with and how he grows')
        ttk.Label(f, text='Class changes', style='Raised.TLabel').pack(anchor='w')
        cards = ui.ChoiceCards(f, [(str(k), t, tx, 'helmet') for k, t, tx in RECLASS], self._reclass,
                               str(q.get('reclass') if q.get('reclass') in (False, True, 'stats') else True), columns=3, width=280)
        cards.pack(fill='x', pady=(px(4), px(10)))
        ttk.Label(f, text='Potions he starts with', style='Raised.TLabel').pack(anchor='w')
        self.pot_rows = ttk.Frame(f, style='Raised.TFrame')
        self.pot_rows.pack(fill='x', pady=px(4))
        self._start_potions()

        # special potions
        f = self._card('Special potions', 'potions 9 and 10, on the keys 9 and 0')
        extra = q.get('potions') or {}
        for k in ('9', '10'):
            self._potion(f, k, extra.get(k))

        # keys
        f = self._card('Key colours', "yellow, red and blue are the original's")
        self.key_rows = ttk.Frame(f, style='Raised.TFrame')
        self.key_rows.pack(fill='x')
        self._keys()
        ui.button(f, 'Add a key colour', self._add_key, 'plus', 'TButton').pack(anchor='w', pady=(px(6), 0))

        # bugs
        f = self._card("The original's bugs", 'switch off to keep a bug, as the original has it')
        fixes = q.get('fixes')
        for name, text in Pack.FIXES.items():
            r = ttk.Frame(f, style='Raised.TFrame')
            r.pack(fill='x', pady=3)
            sw = ui.Switch(r, fixes is True or (isinstance(fixes, list) and name in fixes), lambda v, n=name: self._fix(n, v), bg=C['raised'])
            sw.pack(side='left')
            ttk.Label(r, text=text, style='Raised.TLabel', wraplength=px(820), justify='left').pack(side='left', padx=px(12))

        # the studio
        f = self._card('Quest Studio')
        r = self._row(f, 'Theme')
        seg = ui.Segmented(r, [('dark', 'Dark'), ('light', 'Light')], lambda k: self._theme(k), theme.name(), raised=True)
        seg.pack(side='left')
        r = self._row(f, 'Saving')
        ttk.Label(r, text='Everything is saved a moment after you change it, and again when you leave.', style='Raised.Dim.TLabel').pack(side='left')
        ttk.Frame(self.body, height=px(40)).pack()

    def _title(self, n):
        from .. import levelmeta
        return levelmeta.title(self.s, n)

    # ── changes ─────────────────────────────────────────────────────────────
    def _put(self, key, value, label):
        q = self.s.project.quest
        if q.get(key) == value:
            return
        with self.s.edit(label, 'quest', merge=f'quest:{key}', source=self):
            if value in (None, ''):
                q.pop(key, None)
            else:
                q[key] = value

    def _text(self, key, var, kind, entry):
        s = var.get().strip()
        try:
            value = kind(s) if s else None
        except ValueError:
            self.app.say(f'The {key} has to be a number.', 'warn')
            var.set('' if self.s.project.quest.get(key) is None else str(self.s.project.quest.get(key)))
            return
        self._put(key, value, f'Change the {key}')
        if key == 'title':
            self.app.pack_btn.configure(text=f'{value or self.s.project.name}  ▾')

    def _reclass(self, key):
        val = {'False': False, 'True': True, 'stats': 'stats'}[key]
        with self.s.edit('Change how classes change', 'quest', source=self):
            self.s.project.quest['reclass'] = val

    def _fix(self, name, on):
        with self.s.edit('Change the bug fixes', 'quest', source=self):
            q = self.s.project.quest
            cur = q.get('fixes')
            have = list(Pack.FIXES) if cur is True else list(cur or []) if isinstance(cur, list) else []
            if on and name not in have:
                have.append(name)
            if not on and name in have:
                have.remove(name)
            if len(have) == len(Pack.FIXES):
                q['fixes'] = True
            elif have:
                q['fixes'] = have
            else:
                q.pop('fixes', None)

    def _theme(self, key):
        if key != theme.name():
            self.app.toggle_theme()

    def _open_folder(self):
        path = self.s.project.root
        try:
            if sys.platform.startswith('win'):
                os.startfile(path)                                           # noqa: S606
            elif sys.platform == 'darwin':
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
        except OSError:
            self.app.say(path)

    # starting potions
    def _start_potions(self):
        for w in self.pot_rows.winfo_children():
            w.destroy()
        q = self.s.project.quest
        have = dict(q.get('start_potions') or {})
        names = dict(ORIGINAL_POTIONS)
        for k, v in (q.get('potions') or {}).items():
            names[int(k)] = v.get('name') or f'Potion {k}'
        for k, n in sorted(have.items(), key=lambda kv: int(kv[0])):
            r = ttk.Frame(self.pot_rows, style='Raised.TFrame')
            r.pack(anchor='w', pady=2)
            ttk.Label(r, text=names.get(int(k), f'Potion {k}'), style='Raised.TLabel', width=24).pack(side='left')
            ui.Number(r, 0, 99, n, commit=lambda v, k=k: self._start_potion(k, v), slider=False, width=3, raised=True).pack(side='left')
        r = ttk.Frame(self.pot_rows, style='Raised.TFrame')
        r.pack(anchor='w', pady=(px(6), 0))
        box = ttk.Combobox(r, state='readonly', width=26, values=[f'{k}  {v}' for k, v in sorted(names.items()) if str(k) not in have])
        box.pack(side='left')
        ui.button(r, 'Add', lambda: self._add_start(box), 'plus', 'Small.TButton').pack(side='left', padx=px(8))

    def _start_potion(self, k, n):
        with self.s.edit('Change the starting potions', 'quest', merge='quest:start_potions', source=self):
            d = dict(self.s.project.quest.get('start_potions') or {})
            if n:
                d[k] = n
            else:
                d.pop(k, None)
            if d:
                self.s.project.quest['start_potions'] = d
            else:
                self.s.project.quest.pop('start_potions', None)
        self._start_potions()

    def _add_start(self, box):
        if box.get():
            self._start_potion(str(int(box.get().split()[0])), 1)

    # special potions
    def _potion(self, parent, k, pot):
        pot = pot or {}
        box = ttk.Frame(parent, style='Raised.TFrame')
        box.pack(fill='x', pady=(px(4), px(10)))
        head = ttk.Frame(box, style='Raised.TFrame')
        head.pack(fill='x')
        ttk.Label(head, text=f'Potion {k}', style='H3.TLabel', background=C['raised']).pack(side='left')
        var = tk.StringVar(value=pot.get('name', ''))
        e = ttk.Entry(head, textvariable=var, width=26)
        e.pack(side='left', padx=px(12))
        ui.tip(e, 'Its name. Empty: there is no such potion.')
        for ev in ('<Return>', '<FocusOut>'):
            e.bind(ev, lambda ev_, k=k, v=var: self._pot(k, 'name', v.get().strip() or None))
        cr = ColourRow(head, self.s.pictures, lambda v, k=k: self._pot(k, 'colour', v))
        cr.pack(side='left', padx=px(10))
        cr.set(pot.get('colour'))
        row = ttk.Frame(box, style='Raised.TFrame')
        row.pack(fill='x', pady=(px(6), 0))
        for f, label in POTION_FIELDS:
            ttk.Label(row, text=label, style='Raised.TLabel').pack(side='left')
            cb = ttk.Combobox(row, width=6, values=['', 'half', 'full'])
            cb.set('' if pot.get(f) is None else str(pot.get(f)))
            cb.pack(side='left', padx=(px(4), px(12)))
            cb.bind('<<ComboboxSelected>>', lambda e, k=k, f=f, cb=cb: self._pot_life(k, f, cb))
            cb.bind('<FocusOut>', lambda e, k=k, f=f, cb=cb: self._pot_life(k, f, cb))
            cb.bind('<Return>', lambda e, k=k, f=f, cb=cb: self._pot_life(k, f, cb))
        row2 = ttk.Frame(box, style='Raised.TFrame')
        row2.pack(fill='x', pady=(px(6), 0))
        ttk.Label(row2, text='Cures poison', style='Raised.TLabel').pack(side='left')
        ui.Switch(row2, bool(pot.get('cure_poison')), lambda v, k=k: self._pot(k, 'cure_poison', True if v else None), bg=C['raised']).pack(side='left', padx=(px(6), px(16)))
        for f, label in NUMBER_FIELDS:
            ttk.Label(row2, text=label, style='Raised.TLabel').pack(side='left')
            ui.Number(row2, 0, 999, pot.get(f) or 0, commit=lambda v, k=k, f=f: self._pot(k, f, v or None), slider=False, width=4,
                      raised=True).pack(side='left', padx=(px(4), px(10)))
        ui.hsep(parent).pack(fill='x') if k == '9' else None

    def _pot_life(self, k, f, cb):
        s = cb.get().strip().lower()
        if not s:
            self._pot(k, f, None)
        elif s in ('half', 'full'):
            self._pot(k, f, s)
        else:
            try:
                self._pot(k, f, int(s))
            except ValueError:
                self.app.say('Life and mana: half, full or a number.', 'warn')

    def _pot(self, k, field, value):
        with self.s.edit('Change a special potion', 'quest', merge=f'quest:potion:{k}:{field}', source=self):
            q = self.s.project.quest
            pots = {a: dict(b) for a, b in (q.get('potions') or {}).items()}
            pot = pots.setdefault(k, {})
            if value is None:
                pot.pop(field, None)
            else:
                pot[field] = value
            if field == 'name' and value is None:
                pots.pop(k, None)
            elif 'colour' not in pot and pot:
                pot['colour'] = 7
            if pots:
                q['potions'] = pots
            else:
                q.pop('potions', None)

    # keys
    def _keys(self):
        for w in self.key_rows.winfo_children():
            w.destroy()
        for name, v in (self.s.project.quest.get('keys') or {}).items():
            colour = v.get('colour', 7) if isinstance(v, dict) else v
            r = ttk.Frame(self.key_rows, style='Raised.TFrame')
            r.pack(anchor='w', pady=2)
            ttk.Label(r, text=name, style='Raised.TLabel', width=16).pack(side='left')
            cr = ColourRow(r, self.s.pictures, lambda v, n=name: self._key(n, v if v is not None else 7))
            cr.pack(side='left')
            cr.set(colour)
            ui.button(r, '', lambda n=name: self._key(n, None), 'close', 'Tool.TButton', 'Take it away').pack(side='left', padx=px(8))

    def _key(self, name, colour):
        with self.s.edit('Change the key colours', 'quest', merge=f'quest:key:{name}', source=self):
            q = self.s.project.quest
            keys = dict(q.get('keys') or {})
            if colour is None:
                keys.pop(name, None)
            else:
                keys[name] = colour
            if keys:
                q['keys'] = keys
            else:
                q.pop('keys', None)
        self._keys()

    def _add_key(self):
        name = ui.ask_text(self, 'A key colour', 'Its name (for example green). Doors of that colour need a key of the same name.')
        if not name:
            return
        name = name.strip().lower()
        if name in ('yellow', 'red', 'blue') or name in (self.s.project.quest.get('keys') or {}):
            ui.inform(self, 'A key colour', f'There is already a {name} key.')
            return
        self._key(name, 10)

    def on_show(self, **where):
        pass

    def reload(self):
        self._build()
