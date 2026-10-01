"""The Events tab's "Add an event" wizard, and the pickers that put an item, creature or message number into
a script: a rule is built from drop-down menus ("When ... Only if ... Then ...") and written into the level's
script as code, and what people say is written to the Dialogue (talk.txt) at the same time."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from . import dialogue, event_code
from .uikit import center, tip

WHENS = [('talk', 'the hero talks to a person'), ('dies', 'a creature dies'),
         ('arrive', 'the hero arrives on the level'), ('chest', 'the hero opens a chest'),
         ('took', 'the hero picks up an item')]
CONDITIONS = [('m1', 'quest counter 1 is'), ('m2', 'quest counter 2 is'), ('has', 'the hero has the item'),
              ('hasnt', 'the hero has not the item'), ('rep', "the hero's reputation is at least"),
              ('coins', 'the hero has at least this much gold')]
ACTIONS = [('say', 'the person says a message'), ('message', 'show a message from a person'),
           ('give', 'give the hero an item'), ('take', 'take an item from the hero'),
           ('drop', 'put an item on the ground here'), ('coins', 'give the hero gold (a minus takes it)'),
           ('rep', 'change the hero\'s reputation by'), ('m1', 'set quest counter 1 to'),
           ('m2', 'set quest counter 2 to'), ('next', 'send the hero to the next level')]
NEEDS_ITEM = {'has', 'hasnt', 'give', 'take', 'drop'}
NEEDS_NUMBER = {'m1', 'm2', 'rep', 'coins'}


def rows_of(project, table, keep=lambda r: True):
    """[(id, 'id name')] of a table, in order."""
    return [(r['id'], f'{r["id"]}  {r.get("name") or "(no name)"}') for r in
            sorted(project.tables[table], key=lambda r: r['id']) if keep(r)]


class Combo(ttk.Combobox):
    """A drop-down of (value, label) pairs that answers with the value."""

    def __init__(self, master, pairs, width=34, **kw):
        self.pairs = list(pairs)
        super().__init__(master, values=[lab for _, lab in self.pairs], state='readonly', width=width, **kw)
        if self.pairs:
            self.current(0)

    def value(self):
        i = self.current()
        return self.pairs[i][0] if i >= 0 else None

    def set_pairs(self, pairs):
        self.pairs = list(pairs)
        self.configure(values=[lab for _, lab in self.pairs])
        if self.pairs:
            self.current(0)


class EventWizard(tk.Toplevel):
    """Builds one rule. result: None, or the code lines (and the script's handler) once Add is pressed."""

    def __init__(self, tab, level: int):
        super().__init__(tab)
        self.title(f'Add an event to {"every level" if level == 0 else f"level {level}"}')
        self.tab, self.app, self.level = tab, tab.app, level
        self.actions = []                           # [(key, n)], shown in the list
        self.done = False
        p = self.app.project
        self.people = rows_of(p, 'creatures', lambda r: -100 < r['id'] < 0 and r['id'] != -5)
        self.monsters = rows_of(p, 'creatures', lambda r: r['id'] > 0)
        self.items = rows_of(p, 'items')
        body = ttk.Frame(self, padding=10)
        body.pack(fill='both', expand=True)

        box = ttk.LabelFrame(body, text='1. When', padding=6)
        box.pack(fill='x')
        self.when = Combo(box, WHENS)
        self.when.pack(side='left')
        self.when.bind('<<ComboboxSelected>>', lambda e: self._when_changed())
        self.subject_frame = ttk.Frame(box)
        self.subject_frame.pack(side='left', padx=8)
        self.subject = None

        box = ttk.LabelFrame(body, text='2. Only if (optional)', padding=6)
        box.pack(fill='x', pady=6)
        self.conds = []                             # [(key, widget var)]
        self.cond_rows = ttk.Frame(box)
        self.cond_rows.pack(fill='x')
        ttk.Button(box, text='Add a condition', command=self._add_condition).pack(anchor='w', pady=2)

        box = ttk.LabelFrame(body, text='3. Then', padding=6)
        box.pack(fill='both', expand=True)
        self.list = tk.Listbox(box, height=6, width=70)
        self.list.pack(fill='x')
        row = ttk.Frame(box)
        row.pack(fill='x', pady=4)
        self.action = Combo(row, ACTIONS, width=38)
        self.action.pack(side='left')
        self.action.bind('<<ComboboxSelected>>', lambda e: self._action_changed())
        self.action_frame = ttk.Frame(row)
        self.action_frame.pack(side='left', padx=6)
        ttk.Button(row, text='Add', command=self._add_action).pack(side='left')
        ttk.Button(row, text='Remove the selected', command=self._remove_action).pack(side='left', padx=6)
        self.param = None

        ttk.Label(body, text='This is written into the script:').pack(anchor='w', pady=(8, 0))
        self.preview = tk.Text(body, height=9, width=80, font=('Courier', 10), background='#f4f4f4')
        self.preview.pack(fill='x')
        self.preview.configure(state='disabled')
        bar = ttk.Frame(body)
        bar.pack(fill='x', pady=8)
        ttk.Button(bar, text='Add the event to the script', command=self._finish).pack(side='left')
        ttk.Button(bar, text='Cancel', command=self.destroy).pack(side='left', padx=6)
        self.msg = ttk.Label(bar, text='', foreground='#a00')
        self.msg.pack(side='left', padx=10)
        self._when_changed()
        self._action_changed()
        from .tips import apply as apply_tips
        apply_tips(self)
        tip(self.when, 'What starts the event. The choice may ask who or which, beside it.')
        tip(self.action, 'One thing the event does. Add as many as you like; they happen in order.')
        tip(self.list, 'What happens, in order. Select one and use Remove to take it out.')
        tip(self.preview, 'The code that will be written into the level script. You can change it there later.')
        center(self, parent=tab.winfo_toplevel())
        self.transient(tab.winfo_toplevel())
        self.grab_set()

    # ── 1. when ─────────────────────────────────────────────────────────────
    def _when_changed(self):
        for w in self.subject_frame.winfo_children():
            w.destroy()
        kind = self.when.value()
        pairs = {'talk': self.people, 'dies': self.monsters, 'took': self.items}.get(kind)
        self.subject = None
        if hasattr(self, 'action'):                 # a person only "says" a message when the hero talks to them
            self.action.set_pairs([a for a in ACTIONS if a[0] != 'say' or kind == 'talk'])
            self._action_changed()
        if pairs:
            ttk.Label(self.subject_frame, text={'talk': 'who', 'dies': 'which', 'took': 'which'}[kind]).pack(side='left')
            self.subject = Combo(self.subject_frame, pairs)
            self.subject.pack(side='left', padx=4)
            self.subject.bind('<<ComboboxSelected>>', lambda e: self._refresh())
        self._refresh()

    # ── 2. conditions ───────────────────────────────────────────────────────
    def _add_condition(self):
        row = ttk.Frame(self.cond_rows)
        row.pack(fill='x', pady=1)
        kind = Combo(row, CONDITIONS, width=34)
        kind.pack(side='left')
        holder = ttk.Frame(row)
        holder.pack(side='left', padx=4)
        entry = {'kind': kind, 'row': row, 'holder': holder, 'widget': None}
        self.conds.append(entry)

        def fill(_e=None):
            for w in holder.winfo_children():
                w.destroy()
            if kind.value() in NEEDS_ITEM:
                entry['widget'] = Combo(holder, self.items, width=30)
            else:
                var = tk.StringVar(value='0')
                entry['widget'] = ttk.Spinbox(holder, from_=-999, to=99999, width=8, textvariable=var)
                entry['var'] = var
            entry['widget'].pack(side='left')
            entry['widget'].bind('<<ComboboxSelected>>', lambda e: self._refresh())
            entry['widget'].bind('<KeyRelease>', lambda e: self._refresh())
            self._refresh()
        kind.bind('<<ComboboxSelected>>', fill)
        ttk.Button(row, text='Remove', command=lambda: self._drop_condition(entry)).pack(side='left')
        fill()

    def _drop_condition(self, entry):
        entry['row'].destroy()
        self.conds.remove(entry)
        self._refresh()

    def _conditions(self):
        out = []
        for c in self.conds:
            k = c['kind'].value()
            w = c['widget']
            try:
                n = w.value() if k in NEEDS_ITEM else int(c['var'].get())
            except ValueError:
                continue
            out.append((k, n))
        return out

    # ── 3. actions ──────────────────────────────────────────────────────────
    def _action_changed(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        k = self.action.value()
        self.param = {}
        f = self.action_frame
        if k in ('say', 'message'):
            if k == 'message':
                self.param['person'] = Combo(f, self.people, width=22)
                self.param['person'].pack(side='left', padx=(0, 4))
            self.param['text'] = ttk.Entry(f, width=40)
            self.param['text'].pack(side='left')
            ttk.Label(f, text=' the words (a new line in the Dialogue)', foreground='#555').pack(side='left')
        elif k in NEEDS_ITEM:
            self.param['item'] = Combo(f, self.items, width=30)
            self.param['item'].pack(side='left')
        elif k in NEEDS_NUMBER:
            self.param['n'] = tk.StringVar(value='1')
            ttk.Spinbox(f, from_=-9999, to=99999, width=8, textvariable=self.param['n']).pack(side='left')

    def _add_action(self):
        k = self.action.value()
        self.msg.config(text='')
        if k in ('say', 'message'):
            words = self.param['text'].get().strip()
            if not words or any(c in words for c in '";'):
                self.msg.config(text='Type what is said (no " or ;).')
                return
            who = self.person()
            if k == 'message':
                who = self.param['person'].value()
            if who is None:
                self.msg.config(text='Nobody to say it: there are no people in this quest.')
                return
            n = ('pending', who, words)                  # the Dialogue line is made when the event is added
            self.actions.append((k, n))
        elif k in NEEDS_ITEM:
            self.actions.append((k, self.param['item'].value()))
        elif k in NEEDS_NUMBER:
            try:
                self.actions.append((k, int(self.param['n'].get())))
            except ValueError:
                self.msg.config(text='A number, please.')
                return
        else:
            self.actions.append((k, None))
        self._refresh()

    def person(self):
        """Who says a line in a "talks to a person" event: the person chosen; elsewhere asked for."""
        if self.when.value() == 'talk' and self.subject is not None:
            return self.subject.value()
        return self.people[0][0] if self.people else None

    def _remove_action(self):
        sel = self.list.curselection()
        if sel:
            del self.actions[sel[0]]
            self._refresh()

    # ── the code ────────────────────────────────────────────────────────────
    def _describe(self, k, n):
        text = dict(ACTIONS)[k]
        if k in ('say', 'message'):
            return f'{text}: "{n[2]}"'
        if k in NEEDS_ITEM:
            return f'{text}: {dict(self.items).get(n, n)}'
        return text if n is None else f'{text} {n}'

    def _lines(self, final=False):
        """The rule's code. A message not yet in the Dialogue is numbered from the free numbers (and made, when
        final) so that the code shows what it will say."""
        reserved = {}
        actions = []
        for k, n in self.actions:
            if k in ('say', 'message'):
                person, words = n[1], n[2]
                number = reserved.setdefault((person, words), self._free_number(person, set(
                    v for (pp, _), v in reserved.items() if pp == person)))
                actions.append((k, number if k == 'say' else (person, number)))
            else:
                actions.append((k, n))
        when = self.when.value()
        subject = self.subject.value() if self.subject is not None else None
        return event_code.rule_lines(when, subject, self._conditions(), actions), reserved

    def _free_number(self, person, also=()):
        items = dialogue.parse(self.app.project.texts['talk'])
        taken = {e.number for e in dialogue.entries(items) if e.level == self.level and e.person == person} | set(also)
        return next(n for n in range(10, 1000) if n not in taken)

    def _refresh(self):
        self.list.delete(0, 'end')
        for k, n in self.actions:
            self.list.insert('end', self._describe(k, n))
        lines, _ = self._lines()
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        header = event_code.HEADERS[event_code.WHEN[self.when.value()][0]]
        self.preview.insert('1.0', header + '\n' + '\n'.join('    ' + line for line in lines))
        self.preview.configure(state='disabled')

    def _finish(self):
        if not self.actions:
            self.msg.config(text='Add at least one thing for it to do (step 3).')
            return
        lines, made = self._lines(final=True)
        p = self.app.project
        if made:                                        # the words go into Dialogue (talk.txt), at the same time
            items = dialogue.parse(p.texts['talk'])
            for (person, words), number in made.items():
                line1, line2 = (words[:70], words[70:140] or None) if len(words) > 70 else (words, None)
                at = max((i for i, it in enumerate(items) if isinstance(it, dialogue.Entry) and it.level == self.level
                          and it.person == person), default=len(items) - 1)
                items.insert(at + 1, dialogue.Entry(self.level, person, number, line1, line2))
            p.texts['talk'] = dialogue.write(items)
            p.touch('talk')
        handler = event_code.WHEN[self.when.value()][0]
        script = p.scripts.get(self.level, '')
        p.scripts[self.level] = event_code.add_to_handler(script, handler, lines)
        p.touch(('script', self.level))
        self.app.changed()
        self.app.dialogue_tab.load()
        self.done = True
        self.destroy()


class Picker(tk.Toplevel):
    """Choose one of a list (with a Find box) to put its number into the script. Used for items, creatures,
    stories and messages. result: the id chosen, or None."""

    def __init__(self, parent, title, rows, columns=('Number', 'Name'), note=''):
        super().__init__(parent)
        self.title(title)
        self.rows, self.result = rows, None
        top = ttk.Frame(self, padding=8)
        top.pack(fill='both', expand=True)
        f = ttk.Frame(top)
        f.pack(fill='x')
        ttk.Label(f, text='Find').pack(side='left')
        self.find = tk.StringVar()
        self.find.trace_add('write', lambda *a: self._fill())
        e = ttk.Entry(f, textvariable=self.find)
        e.pack(side='left', fill='x', expand=True, padx=4)
        e.focus_set()
        box = ttk.Frame(top)
        box.pack(fill='both', expand=True, pady=6)
        self.tree = ttk.Treeview(box, columns=columns, show='headings', height=14, selectmode='browse')
        for i, c in enumerate(columns):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=90 if i == 0 else 420, stretch=i > 0)
        sb = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda e: self._ok())
        self.tree.bind('<Return>', lambda e: self._ok())
        if note:
            ttk.Label(top, text=note, foreground='#555', wraplength=520).pack(anchor='w')
        bar = ttk.Frame(top)
        bar.pack(fill='x', pady=4)
        ttk.Button(bar, text='Insert', command=self._ok).pack(side='left')
        ttk.Button(bar, text='Cancel', command=self.destroy).pack(side='left', padx=6)
        self._fill()
        center(self, parent=parent.winfo_toplevel())
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.wait_window()

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        want = self.find.get().strip().lower()
        for i, (key, *cells) in enumerate(self.rows):
            if want and want not in ' '.join([str(key)] + [str(c) for c in cells]).lower():
                continue
            self.tree.insert('', 'end', iid=str(i), values=[key[1] if isinstance(key, tuple) else key] + cells)

    def _ok(self):
        sel = self.tree.selection()
        if sel:
            self.result = self.rows[int(sel[0])][0]
            self.destroy()
