"""The form of one row of a table: its fields in collapsible groups, every change one step of the undo history."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import icons, theme, ui
from .gallery import Entry, Picker
from .model import scope_of
from .theme import C, px

CREATURE_REFS = {'raises_dead', 'reveals_as', 'hides_as', 'becomes_on_death', 'transforms_into'}
ITEM_REFS = {'hit_item'}
# (lowest, highest, where the slider ends) for numbers that are better dragged than typed
RANGES = {'life': (0, 99999, 300), 'power': (0, 999, 100), 'atk': (0, 999, 250), 'def': (0, 999, 200), 'warm': (0, 999, 60),
          'marm': (0, 999, 60), 'range': (1, 30, 12), 'exp': (0, 99999, 500), 'size': (1, 6, 4), 'price': (0, 99999, 1500),
          'req_str': (0, 99, 40), 'req_int': (0, 99, 40), 'str': (-99, 99, 20), 'int': (-99, 99, 20), 'dex': (-99, 99, 20),
          'acc': (-99, 99, 20), 'atk.item': (-99, 999, 100), 'mana': (0, 9999, 200), 'growth': (0, 99, 20),
          'chase_range': (1, 40, 20), 'flees_within': (1, 40, 20), 'transforms_below': (1, 100, 100),
          'rise_limit': (1, 20, 10), 'blood_range': (1, 100, 30), 'hit_item_chance': (1, 100, 100)}


def _range(key):
    if key in RANGES:
        return RANGES[key]
    if key.endswith('.chance'):
        return 0, 100, 100
    return None


class Inspector(ttk.Frame):
    """Shows the row of `schema.table` with this id. `skip`: field keys the page shows itself."""

    def __init__(self, master, session, schema, skip=(), on_change=None, label_width=190):
        super().__init__(master)
        self.s, self.schema, self.skip = session, schema, set(skip)
        self.on_change = on_change
        self.rid = None
        self.label_width = label_width
        self._open = {}
        self._errors = {}
        self.scroll = ui.Scrolled(self)
        self.scroll.pack(fill='both', expand=True)
        self.body = self.scroll.body
        self.extra_top = None

    @property
    def table(self):
        return self.schema.table

    def row(self):
        return self.s.row(self.table, self.rid) if self.rid is not None else None

    def show(self, rid, keep_scroll=False):
        self.rid = rid
        y = self.scroll.canvas.yview()[0] if keep_scroll else 0
        self.render()
        self.scroll.canvas.update_idletasks()
        self.scroll.canvas.yview_moveto(y)

    def refresh(self):
        self.show(self.rid, keep_scroll=True)

    # ── render ──────────────────────────────────────────────────────────────
    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        row = self.row()
        if row is None:
            return
        sch = self.schema
        sch.decorate(row)
        try:
            fields = [f for f in sch.fields(row) if f.key not in self.skip]
            groups = list(sch.groups)
            where = {k: i for i, (_, _, _, keys) in enumerate(groups) for k in keys}
            more = len(groups)
            for i in range(more + 1):
                mine = [f for f in fields if where.get(f.key, more) == i]
                if not mine:
                    continue
                title, default, blurb, _ = groups[i] if i < more else ('More', False, '', [])
                is_set = sum(1 for f in mine if sch.get(row, f.key) not in (None, 0, False, '', [], {}))
                opened = self._open.get(title, default or is_set > 0)
                sec = ui.Section(self.body, title, f'{blurb}' + (f'  ({is_set} set)' if is_set and not opened else ''), open_=opened,
                                 on_toggle=lambda s_, t=title: self._toggled(t, s_.open))
                sec.pack(fill='x', padx=px(14), pady=(px(10), 0))
                grid = ttk.Frame(sec.body)
                grid.pack(fill='x')
                grid.columnconfigure(1, weight=1)
                for n, f in enumerate(mine):
                    self._field(grid, n, f, row)
        finally:
            sch.undecorate(row)
        ttk.Frame(self.body, height=px(30)).pack()

    def _toggled(self, title, opened):
        self._open[title] = opened

    # ── one field ───────────────────────────────────────────────────────────
    def _field(self, grid, n, f, row):
        sch = self.schema
        value = sch.get(row, f.key, f.default)
        lab = ttk.Label(grid, text=f.label, wraplength=px(self.label_width), justify='left')
        lab.grid(row=n * 2, column=0, sticky='nw', pady=(px(6), 0), padx=(0, px(10)))
        box = ttk.Frame(grid)
        box.grid(row=n * 2, column=1, sticky='w', pady=(px(4), 0))
        words = self._tip(f)
        if words:
            ui.tip(lab, words)
        w = self._widget(box, f, value, row)
        w.pack(anchor='w')
        if f.hint:
            ttk.Label(grid, text=f.hint, style='Faint.TLabel', wraplength=px(430), justify='left').grid(
                row=n * 2 + 1, column=1, sticky='w', pady=(0, px(2)))
        err = ttk.Label(grid, text='', style='Bad.TLabel', wraplength=px(430), justify='left')
        err.grid(row=n * 2 + 1, column=0, columnspan=2, sticky='e')
        self._errors[f.key] = err

    @staticmethod
    def _tip(f):
        try:
            from editor.tips import field_tip
            return field_tip(f)
        except Exception:                                               # noqa: BLE001
            return f.hint

    def _widget(self, parent, f, value, row):
        kind = f.kind
        if kind == 'readonly':
            return ttk.Label(parent, text=str(value if value is not None else ''), style='Dim.TLabel')
        if kind == 'bool':
            return ui.Switch(parent, bool(value), lambda v, f=f: self.commit(f, v))
        if kind == 'choice':
            return self._choice(parent, f, value)
        if kind == 'multi':
            return self._multi(parent, f, value)
        if kind == 'int':
            return self._number(parent, f, value)
        if kind == 'custom':
            if f.key in ('loot', 'hit_drops'):
                return LootEditor(parent, self, f, row)
            return self._custom(parent, f, row)
        var = tk.StringVar(value='' if value is None else str(value))
        e = ttk.Entry(parent, textvariable=var, width=34)
        e.bind('<Return>', lambda ev: self.commit(f, var.get().strip()))
        e.bind('<FocusOut>', lambda ev: self.commit(f, var.get().strip()))
        return e

    def _number(self, parent, f, value):
        rng = _range(f.key)
        if rng and f.default is not None or (rng and value is not None):
            lo, hi, soft = rng
            num = ui.Number(parent, lo, hi, value if value is not None else (f.default or lo),
                            commit=lambda v, f=f: self.commit(f, v), soft_max=soft, width=6)
            return num
        var = tk.StringVar(value='' if value is None else str(value))
        fr = ttk.Frame(parent)
        e = ttk.Entry(fr, textvariable=var, width=8, justify='right')
        e.pack(side='left')

        def done(ev=None):
            s = var.get().strip()
            if s == '':
                self.commit(f, None if f.default is None else f.default)
                return
            try:
                self.commit(f, int(s))
            except ValueError:
                self._error(f, f'"{s}" is not a whole number.')
        e.bind('<Return>', done)
        e.bind('<FocusOut>', done)
        if rng:
            ttk.Label(fr, text=f'  {rng[0]} to {rng[1]}', style='Faint.TLabel').pack(side='left')
        return fr

    def _choice(self, parent, f, value):
        choices = f.choices
        if f.key in CREATURE_REFS or f.key in ITEM_REFS:
            kind = 'mon' if f.key in CREATURE_REFS else 'item'
            pic = self.s.pictures
            entries = [Entry(v, lab, '', pic.thumb(kind, v, 32) if v else None) for v, lab in choices if v is not None]
            return Picker(parent, lambda e=entries: e, value, lambda v, f=f: self.commit(f, v),
                          none_label='(none)' if f.key in CREATURE_REFS else '(nothing)', width=30)
        labels = [lab for _, lab in choices]
        values = [v for v, _ in choices]
        w = ttk.Combobox(parent, values=labels, state='readonly', width=max(24, min(44, max(len(l) for l in labels) + 2)))
        w.set(labels[values.index(value)] if value in values else '')
        w.bind('<<ComboboxSelected>>', lambda e, f=f: self.commit(f, values[labels.index(w.get())]))
        return w

    def _multi(self, parent, f, value):
        w = ttk.Frame(parent)
        chosen = {value} if isinstance(value, str) else set(value or ())
        for i, (v, lab) in enumerate(f.choices):
            var = tk.BooleanVar(value=v in chosen)
            ttk.Checkbutton(w, text=lab, variable=var, command=lambda v=v, var=var, f=f: self._toggle(f, v, var.get())).grid(
                row=i // 3, column=i % 3, sticky='w', padx=(0, px(12)))
        return w

    def _toggle(self, f, v, on):
        row = self.row()
        cur = self.schema.get(row, f.key)
        cur = [cur] if isinstance(cur, str) else list(cur or [])
        if on and v not in cur:
            cur.append(v)
        elif not on and v in cur:
            cur.remove(v)
        order = [c for c, _ in f.choices]
        cur = sorted(cur, key=lambda c: order.index(c) if c in order else 99)
        if getattr(f, 'one_as_name', False):
            cur = cur[0] if len(cur) == 1 else cur or None
        self.commit(f, cur)

    def _custom(self, parent, f, row):
        text = f.fmt(row) if f.fmt else ''
        var = tk.StringVar(value=text)
        if f.suggest:
            w = ttk.Combobox(parent, textvariable=var, values=list(f.suggest), width=40)
            w.bind('<<ComboboxSelected>>', lambda e: self._typed(f, var))
        else:
            w = ttk.Entry(parent, textvariable=var, width=42)
        w.bind('<Return>', lambda e: self._typed(f, var))
        w.bind('<FocusOut>', lambda e: self._typed(f, var))
        return w

    def _typed(self, f, var):
        s = var.get().strip()
        try:
            value = f.parse(s)
        except (ValueError, KeyError, IndexError) as e:
            self._error(f, f'{e}. {f.hint}'[:200])
            return
        self._error(f, '')
        row = self.row()
        if row is not None and value == self.schema.get(row, f.key):
            return
        self.commit(f, value)

    def _error(self, f, text):
        lab = self._errors.get(f.key)
        if lab is not None and lab.winfo_exists():
            lab.configure(text=text)

    # ── a change ────────────────────────────────────────────────────────────
    def commit(self, f, value):
        """Set a field of the row as one undoable step (typing in one box is one step)."""
        row = self.row()
        if row is None:
            return
        sch = self.schema
        old = sch.get(row, f.key, f.default)
        missing = sch.get(row, f.key, KeyError) is KeyError
        if value == old or (f.kind != 'bool' and value in (None, '', []) and missing):
            return
        name = row.get('name') or f'#{row["id"]}'
        shown = self._shown(row)
        with self.s.edit(f'Change {f.label.lower()} of {name}', scope_of(self.table), merge=f'{self.table}:{self.rid}:{f.key}', source=self):
            if f.kind == 'bool':
                if value == bool(f.default):
                    sch.drop(row, f.key)
                else:
                    sch.put(row, f.key, value)
            elif value is None or (value == '' and f.kind != 'str') or (value == [] and f.kind == 'multi'):
                sch.drop(row, f.key)
            else:
                sch.put(row, f.key, value)
            sch.after_change(row, f.key, old)
        if self.on_change:
            self.on_change(row, f.key)
        if self._shown(row) != shown:                       # which fields apply has changed: draw the form again
            self.refresh()

    def _shown(self, row):
        self.schema.decorate(row)
        try:
            return [f.key for f in self.schema.fields(row) if f.key not in self.skip]
        finally:
            self.schema.undecorate(row)


# ── loot: rules tried with a roll of 1 to 100 ────────────────────────────────
class LootEditor(ttk.Frame):
    """Rules "from-to: gold n+base" or "from-to: item number", shown as rows and as a strip over the 100 numbers of the roll."""

    def __init__(self, parent, inspector, field, row):
        super().__init__(parent)
        self.ins, self.f = inspector, field
        self.s = inspector.s
        self.rules = [list(r) for r in (inspector.schema.get(row, field.key) or [])]
        self.strip = tk.Canvas(self, width=px(400), height=px(22), highlightthickness=1, highlightbackground=C['line'], bg=C['input'])
        self.strip.pack(anchor='w', pady=(0, px(4)))
        self.rows = ttk.Frame(self)
        self.rows.pack(anchor='w')
        bar = ttk.Frame(self)
        bar.pack(anchor='w', pady=(px(4), 0))
        ui.button(bar, 'Add gold', lambda: self._add('gold'), 'coin', 'TButton').pack(side='left')
        ui.button(bar, 'Add an item', lambda: self._add('item'), 'plus', 'TButton').pack(side='left', padx=px(6))
        self.info = ttk.Label(self, text='', style='Faint.TLabel', wraplength=px(420), justify='left')
        self.info.pack(anchor='w', pady=(px(4), 0))
        self._draw()

    def _draw(self):
        for w in self.rows.winfo_children():
            w.destroy()
        for i, r in enumerate(self.rules):
            self._row(i, r)
        self._strip()

    def _strip(self):
        c = self.strip
        c.delete('all')
        w = px(400)
        taken = [None] * 101
        for r in self.rules:
            for n in range(max(1, r[0]), min(100, r[1]) + 1):
                if taken[n] is None:
                    taken[n] = r[2]
        for n in range(1, 101):
            col = {'gold': C['warn'], 'item': C['info'], None: C['input']}[taken[n]]
            c.create_rectangle((n - 1) * w / 100, 0, n * w / 100, 22, fill=col, outline='')
        gold = sum(1 for t in taken[1:] if t == 'gold')
        item = sum(1 for t in taken[1:] if t == 'item')
        nothing = 100 - gold - item
        self.info.configure(text=f'Of every 100 rolls: {gold} give gold, {item} give an item, {nothing} give nothing. '
                                 'The first rule that holds the roll is the one used.')

    def _row(self, i, r):
        row = ttk.Frame(self.rows)
        row.pack(anchor='w', pady=2)
        ttk.Label(row, text='Roll').pack(side='left')
        lo = ui.Number(row, 1, 100, r[0], commit=lambda v, r=r: self._set(r, 0, v), slider=False, width=4)
        lo.pack(side='left', padx=(px(4), 0))
        ttk.Label(row, text='to').pack(side='left', padx=px(4))
        hi = ui.Number(row, 1, 100, r[1], commit=lambda v, r=r: self._set(r, 1, v), slider=False, width=4)
        hi.pack(side='left')
        if r[2] == 'gold':
            ttk.Label(row, text='  gold: up to').pack(side='left')
            n = ui.Number(row, 1, 999, r[3], commit=lambda v, r=r: self._set(r, 3, v), slider=False, width=4)
            n.pack(side='left', padx=px(4))
            ttk.Label(row, text='plus').pack(side='left')
            b = ui.Number(row, 0, 9999, r[4], commit=lambda v, r=r: self._set(r, 4, v), slider=False, width=4)
            b.pack(side='left', padx=px(4))
            ui.tip(n, 'A random amount from 1 up to this (a die).')
            ui.tip(b, 'Added to the random amount.')
        else:
            pic = self.s.pictures
            entries = [Entry(it['id'], it.get('name') or f'#{it["id"]}', it.get('type', ''), pic.thumb('item', it['id'], 32))
                       for it in self.s.project.entries('item')]
            Picker(row, lambda e=entries: e, r[3], lambda v, r=r: self._set(r, 3, v), width=22).pack(side='left', padx=px(8))
        ui.button(row, '', lambda i=i: self._drop(i), 'close', 'Tool.TButton', 'Take this rule away').pack(side='left', padx=px(6))

    def _set(self, rule, at, value):
        rule[at] = int(value) if value is not None else rule[at]
        if at in (0, 1) and rule[0] > rule[1]:
            rule[0], rule[1] = rule[1], rule[0]
        self._commit()
        self._draw()

    def _add(self, kind):
        taken = {n for r in self.rules for n in range(r[0], r[1] + 1)}
        free = [n for n in range(1, 101) if n not in taken]
        lo, hi = (free[0], min(100, free[0] + 29)) if free else (1, 30)
        if kind == 'gold':
            self.rules.append([lo, hi, 'gold', 5, 1])
        else:
            first = next((it['id'] for it in self.s.project.entries('item') if it['id'] > 0), 1)
            self.rules.append([lo, hi, 'item', first])
        self._commit()
        self._draw()

    def _drop(self, i):
        del self.rules[i]
        self._commit()
        self._draw()

    def _commit(self):
        self.ins.commit(self.f, [list(r) for r in self.rules])
