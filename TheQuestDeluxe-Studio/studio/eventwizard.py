"""The "Add an event" wizard: a rule built from menus (When ... Only if ... Then ...) and written into a level's script as code,
with what people say written into the dialogue at the same time."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core import dialogue, event_code
from core.eventwords import ACTIONS, CONDITIONS, NEEDS_ITEM, NEEDS_NUMBER, WHENS

from . import ui
from .gallery import Entry, Picker
from .theme import C, px


class EventWizard(ui.Dialog):
    """result: True once the event is added."""

    def __init__(self, page, session, level: int):
        super().__init__(page, f'Add an event to {"every level" if level == 0 else f"level {level}"}', width=px(780))
        self.s, self.level = session, level
        self.conds, self.actions = [], []
        p = session.project
        pic = session.pictures

        def entries(table, layer, keep=lambda r: True):
            return [Entry(r['id'], r.get('name') or f'#{r["id"]}', '', pic.thumb(layer, r['id'], 32)) for r in sorted(p.tables[table], key=lambda r: r['id'])
                    if keep(r)]
        self.people = entries('creatures', 'mon', lambda r: -100 < r['id'] < 0 and r['id'] != -5)
        self.monsters = entries('creatures', 'mon', lambda r: r['id'] > 0)
        self.items = entries('items', 'item')
        b = self.body
        ttk.Label(b, text='1. When', style='H3.TLabel').pack(anchor='w')
        top = ttk.Frame(b)
        top.pack(fill='x', pady=(px(4), px(10)))
        self.when_box = ttk.Combobox(top, state='readonly', width=36, values=[t for _, t in WHENS])
        self.when_box.set(WHENS[0][1])
        self.when_box.pack(side='left')
        self.when_box.bind('<<ComboboxSelected>>', lambda e: self._when())
        self.subject_holder = ttk.Frame(top)
        self.subject_holder.pack(side='left', padx=px(10))
        self.subject = None
        ttk.Label(b, text='2. Only if  (optional)', style='H3.TLabel').pack(anchor='w')
        self.cond_rows = ttk.Frame(b)
        self.cond_rows.pack(fill='x')
        ui.button(b, 'Add a condition', self._add_condition, 'plus', 'Small.TButton').pack(anchor='w', pady=(px(4), px(10)))
        ttk.Label(b, text='3. Then', style='H3.TLabel').pack(anchor='w')
        self.action_rows = ttk.Frame(b)
        self.action_rows.pack(fill='x')
        adder = ttk.Frame(b)
        adder.pack(fill='x', pady=(px(6), px(8)))
        self.action_box = ttk.Combobox(adder, state='readonly', width=38)
        self.action_box.pack(side='left')
        self.action_box.bind('<<ComboboxSelected>>', lambda e: self._action_changed())
        self.param_holder = ttk.Frame(adder)
        self.param_holder.pack(side='left', padx=px(8))
        ui.button(adder, 'Add', self._add_action, 'plus', 'Accent.TButton').pack(side='left')
        self.msg = ttk.Label(b, text='', style='Bad.TLabel')
        self.msg.pack(anchor='w')
        ttk.Label(b, text='This is written into the script:', style='Dim.TLabel').pack(anchor='w', pady=(px(8), px(2)))
        self.preview = tk.Text(b, height=8, width=80, font=('Courier', 10), bg=C['input'], fg=C['text'], relief='flat', highlightthickness=1,
                               highlightbackground=C['line'])
        self.preview.pack(fill='x')
        self.add_buttons([('Cancel', None, 'TButton'), ('Add the event to the script', 'add', 'Accent.TButton')], default=None)
        self._when()
        self.person_default = self.people[0].key if self.people else None

    # 1 ----------------------------------------------------------------------------
    def when(self):
        label = self.when_box.get()
        return next(k for k, t in WHENS if t == label)

    def _when(self):
        for w in self.subject_holder.winfo_children():
            w.destroy()
        kind = self.when()
        pool = {'talk': self.people, 'dies': self.monsters, 'took': self.items}.get(kind)
        self.subject = None
        if pool:
            ttk.Label(self.subject_holder, text={'talk': 'who', 'dies': 'which', 'took': 'which'}[kind]).pack(side='left')
            self.subject = Picker(self.subject_holder, lambda p=pool: p, pool[0].key if pool else None, lambda v: self._refresh(), none_label=None, width=26)
            self.subject.pack(side='left', padx=px(6))
        self.action_box.configure(values=[t for k, t in ACTIONS if k != 'say' or kind == 'talk'])
        self.action_box.set(self.action_box.cget('values')[0])
        self._action_changed()
        self._refresh()

    def subject_value(self):
        return self.subject.value if self.subject is not None else None

    # 2 ----------------------------------------------------------------------------
    def _add_condition(self):
        row = ttk.Frame(self.cond_rows)
        row.pack(fill='x', pady=2)
        kind = ttk.Combobox(row, state='readonly', width=34, values=[t for _, t in CONDITIONS])
        kind.set(CONDITIONS[0][1])
        kind.pack(side='left')
        holder = ttk.Frame(row)
        holder.pack(side='left', padx=px(6))
        entry = {'kind': kind, 'row': row, 'holder': holder, 'widget': None, 'var': None}
        self.conds.append(entry)

        def key():
            return next(k for k, t in CONDITIONS if t == kind.get())

        def fill(_e=None):
            for w in holder.winfo_children():
                w.destroy()
            if key() in NEEDS_ITEM:
                entry['widget'] = Picker(holder, lambda: self.items, self.items[0].key if self.items else None, lambda v: self._refresh(), none_label=None, width=24)
                entry['var'] = None
            else:
                entry['var'] = tk.StringVar(value='0')
                entry['widget'] = ttk.Spinbox(holder, from_=-999, to=99999, width=8, textvariable=entry['var'], command=self._refresh)
                entry['var'].trace_add('write', lambda *a: self._refresh())
            entry['widget'].pack(side='left')
            self._refresh()
        entry['key'] = key
        kind.bind('<<ComboboxSelected>>', fill)
        ui.button(row, '', lambda: self._drop_condition(entry), 'close', 'Tool.TButton', 'Take it away').pack(side='left', padx=px(6))
        fill()

    def _drop_condition(self, entry):
        entry['row'].destroy()
        self.conds.remove(entry)
        self._refresh()

    def conditions(self):
        out = []
        for c in self.conds:
            k = c['key']()
            try:
                n = c['widget'].value if k in NEEDS_ITEM else int(c['var'].get())
            except (ValueError, AttributeError):
                continue
            if n is not None:
                out.append((k, n))
        return out

    # 3 ----------------------------------------------------------------------------
    def action_key(self):
        label = self.action_box.get()
        return next(k for k, t in ACTIONS if t == label)

    def _action_changed(self):
        for w in self.param_holder.winfo_children():
            w.destroy()
        k = self.action_key()
        self.param = {}
        f = self.param_holder
        if k in ('say', 'message'):
            if k == 'message':
                self.param['person'] = Picker(f, lambda: self.people, self.people[0].key if self.people else None, lambda v: None, none_label=None, width=18)
                self.param['person'].pack(side='left', padx=(0, px(4)))
            self.param['text'] = ttk.Entry(f, width=40)
            self.param['text'].pack(side='left')
            ui.tip(self.param['text'], 'What is said. It is written into the dialogue as a new line.')
        elif k in NEEDS_ITEM:
            self.param['item'] = Picker(f, lambda: self.items, self.items[0].key if self.items else None, lambda v: None, none_label=None, width=24)
            self.param['item'].pack(side='left')
        elif k in NEEDS_NUMBER:
            self.param['n'] = tk.StringVar(value='1')
            ttk.Spinbox(f, from_=-9999, to=99999, width=8, textvariable=self.param['n']).pack(side='left')

    def _add_action(self):
        k = self.action_key()
        self.msg.configure(text='')
        if k in ('say', 'message'):
            words = self.param['text'].get().strip()
            if not words or any(c in words for c in '";'):
                self.msg.configure(text='Type what is said (it cannot contain " or ;).')
                return
            who = self.param['person'].value if k == 'message' else (self.subject_value() if self.when() == 'talk' else self.person_default)
            if who is None:
                self.msg.configure(text='Nobody can say it: there are no people in this quest.')
                return
            self.actions.append((k, ('pending', who, words)))
        elif k in NEEDS_ITEM:
            self.actions.append((k, self.param['item'].value))
        elif k in NEEDS_NUMBER:
            try:
                self.actions.append((k, int(self.param['n'].get())))
            except ValueError:
                self.msg.configure(text='A number, please.')
                return
        else:
            self.actions.append((k, None))
        self._refresh()

    def _describe(self, k, n):
        text = dict(ACTIONS)[k]
        if k in ('say', 'message'):
            return f'{text}: "{n[2]}"'
        if k in NEEDS_ITEM:
            return f'{text}: {self.s.name_of("items", n)}'
        return text if n is None else f'{text} {n}'

    def _free_number(self, person, also=()):
        items = dialogue.parse(self.s.project.texts['talk'])
        taken = {e.number for e in dialogue.entries(items) if e.level == self.level and e.person == person} | set(also)
        return next(n for n in range(10, 1000) if n not in taken)

    def _lines(self):
        reserved, actions = {}, []
        for k, n in self.actions:
            if k in ('say', 'message'):
                person, words = n[1], n[2]
                number = reserved.setdefault((person, words), self._free_number(person, {v for (pp, _), v in reserved.items() if pp == person}))
                actions.append((k, number if k == 'say' else (person, number)))
            else:
                actions.append((k, n))
        return event_code.rule_lines(self.when(), self.subject_value(), self.conditions(), actions), reserved

    def _refresh(self):
        for w in self.action_rows.winfo_children():
            w.destroy()
        for i, (k, n) in enumerate(self.actions):
            r = ttk.Frame(self.action_rows)
            r.pack(fill='x', pady=1)
            ttk.Label(r, text=f'{i + 1}.', width=3).pack(side='left')
            ttk.Label(r, text=self._describe(k, n)).pack(side='left')
            ui.button(r, '', lambda i=i: self._drop_action(i), 'close', 'Tool.TButton', 'Take it away').pack(side='left', padx=px(6))
        lines, _ = self._lines()
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        header = event_code.HEADERS[event_code.WHEN[self.when()][0]]
        self.preview.insert('1.0', header + '\n' + '\n'.join('    ' + line for line in lines))
        self.preview.configure(state='disabled')

    def _drop_action(self, i):
        del self.actions[i]
        self._refresh()

    # finish -----------------------------------------------------------------------
    def close(self, value):
        if value == 'add':
            if not self.actions:
                self.msg.configure(text='Add at least one thing for it to do (step 3).')
                return
            lines, made = self._lines()
            p, s, n = self.s.project, self.s, self.level
            with s.edit('Add an event', ('script', n), 'texts'):
                if made:
                    items = dialogue.parse(p.texts['talk'])
                    for (person, words), number in made.items():
                        line1, line2 = (words[:70], words[70:140] or None) if len(words) > 70 else (words, None)
                        at = max((i for i, it in enumerate(items) if isinstance(it, dialogue.Entry) and it.level == n and it.person == person),
                                 default=len(items) - 1)
                        items.insert(at + 1, dialogue.Entry(n, person, number, line1, line2))
                    p.texts['talk'] = dialogue.write(items)
                    p.touch('talk')
                handler = event_code.WHEN[self.when()][0]
                p.scripts[n] = event_code.add_to_handler(p.scripts.get(n, ''), handler, lines)
                p.touch(('script', n))
            super().close(True)
            return
        super().close(None)
