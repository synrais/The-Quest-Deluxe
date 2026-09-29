"""The Events tab (level scripts) and the Text tab (dialogue, stories, the questionnaire): a list of
files on the left, the text on the right, and a Check button that reads it the way the game will."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from deluxe.script import Script, ScriptError
from deluxe.formats import parse_talk, parse_story

HANDLERS = {
    'talk': ('def talk(npc):\n    # the hero walked into a person; x, y is their square, npc their creature number\n'
             '    if npc == -6:\n        say(10)\n',
             'The hero walks into a person (npc = their creature number).'),
    'check': ('def check(w):\n    # every creature on the screen, after each turn (slot(w) is the creature)\n    pass\n',
              'After every turn, for each creature on the screen.'),
    'dies': ('def dies(w):\n    # a creature has just died (slot(w)), before its body falls\n    pass\n',
             'A creature has just died, before its body falls.'),
    'level_start': ('def level_start():\n    # the hero has just arrived on this level\n    pass\n',
                    'The hero arrives on the level.'),
    'after_action': ("def after_action(key):\n    # after every key the hero presses in play ('space' or 'key')\n    pass\n",
                     'After every key pressed in play.'),
    'before_pickup': ('def before_pickup():\n    # Enter was pressed to pick up what lies here (x, y)\n    pass\n',
                      'Enter is pressed to pick things up.'),
    'opened_chest': ('def opened_chest():\n    # a chest was just opened at (x, y)\n    pass\n', 'A chest is opened.'),
    'took': ('def took(item):\n    # an item went into the backpack\n    pass\n', 'An item goes into the backpack.'),
    'killer_allowed': ('def killer_allowed():\n    # may the killer switch (k) be turned on here?\n    return 1\n',
                       'Whether the killer switch may be used.'),
}


class Editor(ttk.Frame):
    """A list of documents and a text box. Subclasses say what the documents are."""

    def __init__(self, master, app, help_text=''):
        super().__init__(master)
        self.app = app
        self.current = None
        self._loading = False
        left = ttk.Frame(self, padding=4)
        left.pack(side='left', fill='y')
        self.docs = tk.Listbox(left, width=22, height=20, exportselection=False)
        self.docs.pack(fill='y', expand=True)
        self.docs.bind('<<ListboxSelect>>', lambda e: self._open_selected())
        self.buttons = ttk.Frame(left)
        self.buttons.pack(fill='x', pady=4)
        ttk.Button(self.buttons, text='Check', command=self.check).pack(fill='x')
        if help_text:
            ttk.Label(left, text=help_text, foreground='#555', wraplength=170, justify='left').pack(anchor='w', pady=6)
        mid = ttk.Frame(self)
        mid.pack(side='left', fill='both', expand=True)
        self.text = tk.Text(mid, wrap='none', undo=True, font=('Courier', 10), tabs='4c')
        ys = ttk.Scrollbar(mid, orient='vertical', command=self.text.yview)
        xs = ttk.Scrollbar(mid, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.text.grid(row=0, column=0, sticky='nsew')
        ys.grid(row=0, column=1, sticky='ns')
        xs.grid(row=1, column=0, sticky='ew')
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        self.result = ttk.Label(mid, text='', anchor='w')
        self.result.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.text.bind('<<Modified>>', self._modified)
        self.text.tag_configure('error', background='#ffcccc')

    # subclasses: keys(), label(key), get(key), put(key, text), problems(key, text) -> [(line, message)]
    def load(self):
        self.docs.delete(0, 'end')
        self._keys = self.keys()
        for k in self._keys:
            self.docs.insert('end', self.label(k))
        if self._keys:
            k = self.current if self.current in self._keys else self._keys[0]
            self.docs.selection_clear(0, 'end')
            self.docs.selection_set(self._keys.index(k))
            self.show(k)

    def _open_selected(self):
        sel = self.docs.curselection()
        if sel:
            self.show(self._keys[sel[0]])

    def show(self, key):
        self.current = key
        self._loading = True
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', self.get(key))
        self.text.edit_reset()
        self.text.edit_modified(False)
        self._loading = False
        self.result.config(text='')

    def _modified(self, _e):
        if self._loading or not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self.current is not None:
            self.put(self.current, self.text.get('1.0', 'end-1c'))
            self.app.changed()

    def check(self):
        self.text.tag_remove('error', '1.0', 'end')
        issues = self.problems(self.current, self.text.get('1.0', 'end-1c'))
        if not issues:
            self.result.config(text='No problems found.', foreground='#060')
            return True
        for line, _ in issues:
            if line:
                self.text.tag_add('error', f'{line}.0', f'{line}.end')
        line, msg = issues[0]
        if line:
            self.text.see(f'{line}.0')
        self.result.config(text=('; '.join(m for _, m in issues))[:300], foreground='#a00')
        return False


class EventsTab(Editor):
    def __init__(self, master, app):
        super().__init__(master, app, 'Each level has a script with its settings (the map tab sets most of them) '
                                      'and handlers the game calls. docs/EVENTS.md lists everything a script can use.')
        ttk.Label(self.buttons, text='Add a handler:').pack(anchor='w', pady=(8, 0))
        self.handler = ttk.Combobox(self.buttons, values=list(HANDLERS), state='readonly', width=18)
        self.handler.pack(fill='x')
        self.handler.bind('<<ComboboxSelected>>', lambda e: self._add_handler())

    def keys(self):
        return list(range(0, self.app.project.levels + 1))

    def label(self, k):
        return 'Every level (common)' if k == 0 else f'Level {k}'

    def get(self, k):
        return self.app.project.scripts.get(k, '')

    def put(self, k, text):
        self.app.project.scripts[k] = text
        self.app.project.touch(('script', k))

    def reload(self, k):
        if k == self.current:
            self.show(k)

    def _add_handler(self):
        name = self.handler.get()
        code = self.text.get('1.0', 'end-1c')
        if f'def {name}(' in code:
            idx = self.text.search(f'def {name}(', '1.0')
            self.text.see(idx)
            self.result.config(text=f'This script already has {name}().', foreground='#555')
            return
        self.text.insert('end', ('\n\n' if code.strip() else '') + HANDLERS[name][0])
        self.text.see('end')
        self.result.config(text=HANDLERS[name][1], foreground='#555')

    def problems(self, k, text):
        try:
            sc = Script(text, self.label(k))
        except SyntaxError as e:
            return [(e.lineno, f'line {e.lineno}: {e.msg}')]
        except (ScriptError, ValueError) as e:
            msg = str(e)
            line = None
            parts = msg.split(':')
            if len(parts) > 2 and parts[1].strip().isdigit():
                line = int(parts[1])
            return [(line, msg)]
        out = []
        for name, fn in sc.handlers.items():
            if name not in HANDLERS:
                out.append((fn.lineno, f'line {fn.lineno}: the game never calls a handler named {name}()'))
        return out


class TextTab(Editor):
    NAMES = {'talk': 'Dialogue (talk.txt)', 'stories': 'Stories (stories.txt)', 'questions': 'Questionnaire'}

    def __init__(self, master, app):
        super().__init__(master, app,
                         'Dialogue: level person number "line 1 (optional "line 2) ending with ; - level 0 lines '
                         'are shared, 1-3 are chit-chat, 10 and up are said by scripts (say). Stories: '
                         'number and line count, then the lines. The questionnaire: 8 questions of 9 lines. '
                         'Shops: the item numbers a shop sells (up to 40), filling its shelves in order; the '
                         "Map tab's Shop tool says which screen has which shop.")

    def keys(self):
        p = self.app.project
        shops = [('shop', n, k) for n in range(1, p.levels + 1) for k in sorted(p.shops.get(n, {}))]
        return list(self.NAMES) + shops

    def label(self, k):
        return f'Level {k[1]} shop {k[2]}' if isinstance(k, tuple) else self.NAMES[k]

    def get(self, k):
        if isinstance(k, tuple):
            return self.app.project.shops[k[1]][k[2]]
        return self.app.project.texts[k]

    def put(self, k, text):
        if isinstance(k, tuple):
            self.app.project.shops[k[1]][k[2]] = text
            self.app.project.touch(('shops', k[1]))
        else:
            self.app.project.texts[k] = text
            self.app.project.touch(k)

    def problems(self, k, text):
        if isinstance(k, tuple):
            items = {r['id'] for r in self.app.project.tables['items']}
            out = []
            for i, line in enumerate(text.splitlines(), 1):
                for v in line.split():
                    if not v.lstrip('-').isdigit():
                        out.append((i, f'line {i}: {v} is not an item number'))
                    elif int(v) and int(v) not in items:
                        out.append((i, f'line {i}: there is no item {v}'))
            n = sum(len(line.split()) for line in text.splitlines())
            if n > 40:
                out.append((None, f'a shop holds 40 things; this lists {n}'))
            return out
        if k == 'talk':
            lines = parse_talk(text)
            starts = sum(1 for line in text.splitlines() if line[:1].isdigit() or line[:2].lstrip('-')[:1].isdigit())
            if not lines and text.strip():
                return [(None, 'no lines could be read')]
            if starts > len(lines):
                return [(None, f'{starts - len(lines)} entries could not be read (each must end with ;)')]
            return []
        if k == 'stories':
            stories = parse_story(text)
            if text.strip() and not stories:
                return [(1, 'no stories could be read: each starts with "number lines"')]
            return []
        n = len(text.splitlines())
        return [] if n >= 72 else [(None, f'the questionnaire needs 72 lines (8 x 9); it has {n}')]
