"""The Events page: what happens on each level, written as a small script, with a wizard that writes the common rules for you."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from core import dialogue
from engine.formats import parse_story
from engine.script import Script, ScriptError

from .. import levelmeta, ui
from ..eventwizard import EventWizard
from ..gallery import Entry, choose
from ..theme import C, px
from .base import Page

HANDLERS = {
    'talk': ('def talk(npc):\n    # the hero walked into a person; x, y is their square, npc their creature number\n    if npc == -6:\n        say(10)\n',
             'The hero walks into a person (npc is their creature number).'),
    'check': ('def check(w):\n    # every creature on the screen, after each turn (slot(w) is the creature)\n    pass\n', 'After every turn, for each creature on the screen.'),
    'dies': ('def dies(w):\n    # a creature has just died (slot(w)), before its body falls\n    pass\n', 'A creature has just died, before its body falls.'),
    'level_start': ('def level_start():\n    # the hero has just arrived on this level\n    pass\n', 'The hero arrives on the level.'),
    'after_action': ("def after_action(key):\n    # after every key the hero presses in play ('space' or 'key')\n    pass\n", 'After every key pressed in play.'),
    'before_pickup': ('def before_pickup():\n    # Enter was pressed to pick up what lies here (x, y)\n    pass\n', 'Enter is pressed to pick things up.'),
    'opened_chest': ('def opened_chest():\n    # a chest was just opened at (x, y)\n    pass\n', 'A chest is opened.'),
    'took': ('def took(item):\n    # an item went into the backpack\n    pass\n', 'An item goes into the backpack.'),
    'killer_allowed': ('def killer_allowed():\n    # may the killer switch (k) be turned on here?\n    return 1\n', 'Whether the killer switch may be used.'),
}


class EventsPage(Page):
    key = 'events'
    intro = 'Events are the small scripts that make things happen: a door that opens, a villager who asks for something. The wizard writes them for you, and you can type them too. Check finds mistakes.'
    title = 'Events'
    icon = 'bolt'

    def build(self):
        self.level = 1
        self._loading = False
        self._job = None
        left = ttk.Frame(self, width=px(250))
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        ui.vsep(self).pack(side='left', fill='y')
        ttk.Label(left, text='Where', style='H2.TLabel').pack(anchor='w', padx=px(14), pady=(px(14), px(6)))
        self.list = Gallery_(left, self)
        right = ttk.Frame(self)
        right.pack(side='left', fill='both', expand=True)
        head = ttk.Frame(right)
        head.pack(fill='x', padx=px(20), pady=(px(14), px(4)))
        self.title_label = ttk.Label(head, text='', style='H1.TLabel')
        self.title_label.pack(side='left')
        bar = ttk.Frame(right)
        bar.pack(fill='x', padx=px(20), pady=px(6))
        ui.button(bar, 'Add an event', self.wizard, 'bolt', 'Accent.TButton', 'Build a rule from menus: when this happens, only if that, then do this').pack(side='left')
        ui.button(bar, 'Insert…', self._insert_menu, 'plus', 'TButton', 'Put a message, item, creature or story number into the script').pack(side='left', padx=px(8))
        ui.button(bar, 'Add a handler…', self._handler_menu, 'gear', 'TButton', 'A place the game calls your code').pack(side='left')
        ui.button(bar, 'Check', self.check, 'check', 'TButton', 'Read the script the way the game will').pack(side='left', padx=px(8))
        self.blurb = ttk.Label(right, text='Each level has a script: its settings (the World page sets most of them) and handlers the game calls. '
                               'docs/EVENTS.md lists everything a script can use.', style='Dim.TLabel', wraplength=px(900), justify='left')
        self.blurb.pack(anchor='w', padx=px(20))
        body = ttk.Frame(right)
        body.pack(fill='both', expand=True, padx=px(20), pady=px(8))
        self.outline = ttk.Frame(body, width=px(210))
        self.outline.pack(side='left', fill='y', padx=(0, px(10)))
        self.outline.pack_propagate(False)
        ttk.Label(self.outline, text='Handlers', style='H3.TLabel').pack(anchor='w')
        self.outline_rows = ttk.Frame(self.outline)
        self.outline_rows.pack(fill='both', expand=True, pady=px(4))
        self.code = ui.CodeText(body, height=26, width=96)
        self.code.pack(side='left', fill='both', expand=True)
        self.code.text.bind('<KeyRelease>', lambda e: self._typed(), add='+')
        self.result = ttk.Label(right, text='', style='Dim.TLabel', wraplength=px(1000), justify='left')
        self.result.pack(anchor='w', padx=px(20), pady=(0, px(8)))
        self.s.on('script', self._script_changed)
        self.s.on('quest', lambda sc, src: self.list.fill())
        self.s.on('texts', lambda sc, src: None)

    # list ------------------------------------------------------------------------
    def scopes(self):
        return list(range(0, self.s.levels + 1))

    def label(self, k):
        return 'Every level (common)' if k == 0 else f'Level {k}  {levelmeta.title(self.s, k)}'.replace(f'Level {k}  Level {k}', f'Level {k}')

    def handlers_of(self, k):
        text = self.s.project.scripts.get(k, '')
        return re.findall(r'^def (\w+)\(', text, re.M)

    def on_show(self, level=None, **where):
        if level is not None:
            self.level = int(level)
        self.list.fill()
        self.load()

    def pick(self, k):
        self.level = k
        self.load()

    # the script ------------------------------------------------------------------
    def load(self):
        self._loading = True
        self.code.set(self.s.project.scripts.get(self.level, ''))
        self._loading = False
        self.title_label.configure(text=self.label(self.level))
        self._outline()
        self.result.configure(text='')

    def _script_changed(self, scope, source):
        if not self.built:
            return
        if scope[1] == self.level and source is not self:
            self.load()
        self.list.fill()

    def _typed(self):
        if self._loading:
            return
        text = self.code.get()
        if text == self.s.project.scripts.get(self.level, ''):
            return
        with self.s.edit(f'Edit the events of {self.label(self.level)}', ('script', self.level), merge=f'script:{self.level}', source=self):
            self.s.project.scripts[self.level] = text
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(400, self._after_typing)

    def _after_typing(self):
        self._job = None
        self._outline()
        self.list.fill()
        self.check(quiet=True)

    def _outline(self):
        for w in self.outline_rows.winfo_children():
            w.destroy()
        text = self.code.get()
        found = [(m.group(1), text.count('\n', 0, m.start()) + 1) for m in re.finditer(r'^def (\w+)\(', text, re.M)]
        if not found:
            ttk.Label(self.outline_rows, text='No handlers yet.\nAdd an event, or a handler.', style='Faint.TLabel', justify='left').pack(anchor='w')
        for name, line in found:
            row = tk.Frame(self.outline_rows, bg=C['panel'], cursor='hand2')
            row.pack(fill='x', pady=1)
            known = name in HANDLERS
            lab = tk.Label(row, text=name, bg=C['panel'], fg=C['text'] if known else C['warn'], anchor='w')
            lab.pack(side='left', padx=px(6), pady=px(3))
            tk.Label(row, text=f'line {line}', bg=C['panel'], fg=C['faint'], font=(0, 8)).pack(side='right', padx=px(6))
            for w in (row, lab):
                w.bind('<Button-1>', lambda e, ln=line: self._goto(ln))
            if known:
                ui.tip(lab, HANDLERS[name][1])

    def _goto(self, line):
        self.code.text.mark_set('insert', f'{line}.0')
        self.code.text.see(f'{line}.0')
        self.code.text.focus_set()

    def check(self, quiet=False):
        text = self.code.get()
        issues = self.problems(text)
        self.code.mark_errors([ln for ln, _ in issues])
        if not issues:
            self.result.configure(text='No problems found.' if not quiet else '', foreground=C['ok'])
            return True
        self.result.configure(text='; '.join(m for _, m in issues)[:400], foreground=C['bad'])
        return False

    def problems(self, text):
        try:
            sc = Script(text, self.label(self.level))
        except SyntaxError as e:
            return [(e.lineno, f'line {e.lineno}: {e.msg}')]
        except (ScriptError, ValueError) as e:
            msg = str(e)
            parts = msg.split(':')
            line = int(parts[1]) if len(parts) > 2 and parts[1].strip().isdigit() else None
            return [(line, msg)]
        return [(fn.lineno, f'line {fn.lineno}: the game never calls a handler named {name}()') for name, fn in sc.handlers.items() if name not in HANDLERS]

    # actions ---------------------------------------------------------------------
    def wizard(self):
        if EventWizard(self, self.s, self.level).run():
            self.load()
            self.code.text.see('end')
            self.result.configure(text='The event is at the end of its handler. Check reads it the way the game will.', foreground=C['dim'])

    def _handler_menu(self):
        m = tk.Menu(self, tearoff=False)
        for name, (code, about) in HANDLERS.items():
            m.add_command(label=f'{name}   {about}', command=lambda n=name: self._add_handler(n))
        w = self.winfo_toplevel()
        m.tk_popup(w.winfo_pointerx(), w.winfo_pointery())

    def _add_handler(self, name):
        code = self.code.get()
        if f'def {name}(' in code:
            idx = self.code.text.search(f'def {name}(', '1.0')
            self.code.text.see(idx)
            self.result.configure(text=f'This script already has {name}().', foreground=C['dim'])
            return
        self.code.text.insert('end', ('\n\n' if code.strip() else '') + HANDLERS[name][0])
        self.code.text.see('end')
        self._typed()
        self.result.configure(text=HANDLERS[name][1], foreground=C['dim'])

    def _insert_menu(self):
        m = tk.Menu(self, tearoff=False)
        for label, kind in (('A message…', 'message'), ('An item…', 'item'), ('A creature…', 'creature'), ('A story…', 'story')):
            m.add_command(label=label, command=lambda k=kind: self.insert(k))
        w = self.winfo_toplevel()
        m.tk_popup(w.winfo_pointerx(), w.winfo_pointery())

    def insert(self, kind):
        p, level, pic = self.s.project, self.level, self.s.pictures
        text = None
        if kind == 'item':
            got = choose(self, 'An item', [Entry(r['id'], r.get('name') or f'#{r["id"]}', r.get('type', ''), pic.thumb('item', r['id'], 32)) for r in sorted(p.tables['items'], key=lambda r: r['id'])], ok='Insert')
            text = None if got in (False, None) else str(got)
        elif kind == 'creature':
            got = choose(self, 'A creature', [Entry(r['id'], r.get('name') or f'#{r["id"]}', '', pic.thumb('mon', r['id'], 32)) for r in sorted(p.tables['creatures'], key=lambda r: r['id'])], ok='Insert')
            text = None if got in (False, None) else str(got)
        elif kind == 'story':
            stories = parse_story(p.texts['stories'])
            got = choose(self, 'A story', [Entry(n, f'Story {n}', s.split('\n')[0][:60]) for n, s in sorted(stories.items())], ok='Insert')
            text = None if got in (False, None) else str(got)
        else:
            names = {r['id']: r.get('name', '') for r in p.tables['creatures']}
            rows = [Entry((e.person, e.number), f'{names.get(e.person, e.person)}: {e.line1}', f'line {e.number}') for e in dialogue.entries(dialogue.parse(p.texts['talk']))
                    if e.level in (level, 0) and e.number >= 10]
            if not rows:
                ui.inform(self, 'Messages', 'No lines for events yet. Add some on the Story & talk page, or use "Add an event".')
                return
            got = choose(self, f'A message (level {level})', rows, ok='Insert')
            if got in (False, None):
                return
            before = self.code.text.get('1.0', 'insert')
            last = before.rfind('\ndef ')
            inside_talk = before[last + 1:].startswith('def talk(') if last >= 0 else before.startswith('def talk(')
            text = f'say({got[1]})' if inside_talk else f'message({got[0]}, {got[1]})'
        if text:
            self.code.text.insert('insert', text)
            self.code.text.focus_set()
            self._typed()

    def reload(self):
        self.level = min(self.level, self.s.levels)
        self.on_show()

    def search(self, q):
        out = []
        for k in self.scopes():
            if q in self.label(k).lower() or q in 'events script':
                out.append((self.label(k), 'events', 'bolt', lambda k=k: self.app.go('events', level=k)))
        return out


class Gallery_(ttk.Frame):
    """The list of scripts: a card each, with how many handlers it has."""

    def __init__(self, master, page):
        super().__init__(master)
        from ..gallery import Gallery
        self.page = page
        self.g = Gallery(self, on_select=page.pick, list_mode=True)
        self.g.pack(fill='both', expand=True)
        self.pack(fill='both', expand=True)

    def fill(self):
        entries = []
        for k in self.page.scopes():
            n = len(self.page.handlers_of(k))
            entries.append(Entry(k, self.page.label(k), f'{n} handler{"s" if n != 1 else ""}' if n else 'no events yet'))
        self.g.set_items(entries)
        self.g.select(self.page.level, scroll=False)
