"""The Quest Deluxe Editor: makes and changes quest packs for The Quest Deluxe.

    python run_editor.py                 opens packs/TheQuest (or the last pack opened)
    python run_editor.py --pack mypack   opens packs/mypack (or any pack folder)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from engine.pack import PACKS_DIR, DEFAULT_PACK, ROOT
from .project import Project
from .map_tab import MapTab
from .text_tabs import EventsTab, TextTab
from .items_tab import ItemsTab
from .creatures_tab import CreaturesTab
from .classes_tab import ClassesTab
from .tiles_tab import TilesTab
from .spells_tab import SpellsTab
from .shops_tab import ShopsTab
from .dialogue_tab import DialogueTab
from .stories_tab import StoriesTab

SETTINGS = os.path.join(os.path.expanduser('~'), '.quest_editor.json')


class QuestTab(ttk.Frame):
    """The quest's own settings (quest.json)."""
    FIELDS = [('title', 'Title', str), ('author', 'Author', str), ('year', 'Year', int),
              ('first_level', 'First level', int)]

    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app
        self.vars = {}
        for i, (key, label, _) in enumerate(self.FIELDS):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky='w', pady=2)
            v = tk.StringVar()
            ttk.Entry(self, textvariable=v, width=40).grid(row=i, column=1, sticky='w')
            self.vars[key] = v
        n = len(self.FIELDS)
        self.reclass = tk.BooleanVar()
        ttk.Checkbutton(self, text="The hero's class follows the stats at each level-up (Quest I's rule)",
                        variable=self.reclass).grid(row=n, column=0, columnspan=2, sticky='w', pady=2)
        ttk.Label(self, text='Starting potions').grid(row=n + 1, column=0, sticky='w')
        self.potions = tk.StringVar()
        ttk.Entry(self, textvariable=self.potions, width=40).grid(row=n + 1, column=1, sticky='w')
        ttk.Label(self, text='potion number: count, ... (6: 1 is one Full Restoration Potion)',
                  foreground='#555').grid(row=n + 2, column=1, sticky='w')
        ttk.Button(self, text='Apply', command=self.apply).grid(row=n + 3, column=1, sticky='w', pady=8)
        self.info = ttk.Label(self, text='', foreground='#555', justify='left')
        self.info.grid(row=n + 4, column=0, columnspan=2, sticky='w', pady=12)

    def load(self):
        q = self.app.project.quest
        for key, _, _ in self.FIELDS:
            self.vars[key].set('' if q.get(key) is None else str(q.get(key)))
        self.reclass.set(bool(q.get('reclass')))
        self.potions.set(', '.join(f'{k}: {v}' for k, v in q.get('start_potions', {}).items()))
        p = self.app.project
        self.info.config(text=f'Pack folder: {p.root}\n{p.levels} levels, {len(p.tables["items"])} items, '
                              f'{len(p.tables["creatures"])} creatures, {len(p.tables["spells"])} spells, '
                              f'{len(p.tables["classes"])} classes.\ndocs/QUEST_PACKS.md describes every file.')

    def apply(self):
        q = self.app.project.quest
        try:
            for key, _, kind in self.FIELDS:
                s = self.vars[key].get().strip()
                q[key] = kind(s) if s else None
            pots = {}
            for part in self.potions.get().split(','):
                if part.strip():
                    k, v = part.split(':')
                    pots[str(int(k))] = int(v)
            q['start_potions'] = pots
        except ValueError:
            messagebox.showerror('Quest', 'The year and first level are numbers; potions are like "6: 1".')
            return
        q['reclass'] = self.reclass.get()
        self.app.project.touch('quest')
        self.app.changed()


class App:
    def __init__(self, root: tk.Tk, pack: str | None = None):
        self.root = root
        self.project = None
        self.dirty = False
        root.geometry('1280x780')
        root.minsize(1000, 600)
        self._menus()
        bar = ttk.Frame(root, padding=(6, 4))
        bar.pack(fill='x')
        ttk.Button(bar, text='Save', command=self.save).pack(side='left')
        ttk.Button(bar, text='Play from here (F5)', command=self.play).pack(side='left', padx=6)
        ttk.Label(bar, text='as').pack(side='left')
        self.play_class = ttk.Combobox(bar, state='readonly', width=12)
        self.play_class.pack(side='left', padx=4)
        ttk.Label(bar, text='(on the square last clicked on the map, or the level start)',
                  foreground='#555').pack(side='left')
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True)
        self.map_tab = MapTab(self.tabs, self)
        self.events_tab = EventsTab(self.tabs, self)
        self.text_tab = TextTab(self.tabs, self)
        self.quest_tab = QuestTab(self.tabs, self)
        self.items_tab = ItemsTab(self.tabs, self)
        self.creatures_tab = CreaturesTab(self.tabs, self)
        self.classes_tab = ClassesTab(self.tabs, self)
        self.spells_tab = SpellsTab(self.tabs, self)
        self.shops_tab = ShopsTab(self.tabs, self)
        self.dialogue_tab = DialogueTab(self.tabs, self)
        self.stories_tab = StoriesTab(self.tabs, self)
        self.tiles_tab = TilesTab(self.tabs, self)
        for tab, name in ((self.map_tab, 'Map'), (self.items_tab, 'Items'), (self.creatures_tab, 'Creatures'),
                          (self.classes_tab, 'Classes'), (self.spells_tab, 'Spells'), (self.tiles_tab, 'Tiles'),
                          (self.shops_tab, 'Shops'), (self.dialogue_tab, 'Dialogue'), (self.stories_tab, 'Stories'),
                          (self.events_tab, 'Events'), (self.text_tab, 'Text files'), (self.quest_tab, 'Quest')):
            self.tabs.add(tab, text=f'  {name}  ')
        self.tabs.bind('<<NotebookTabChanged>>', lambda e: self._tab_changed())
        root.bind('<Control-s>', lambda e: self.save())
        root.bind('<F5>', lambda e: self.play())
        root.bind('<Control-z>', lambda e: self._undo(False))
        root.bind('<Control-y>', lambda e: self._undo(True))
        root.protocol('WM_DELETE_WINDOW', self.quit)
        last = self._settings().get('last')
        if last and not os.path.exists(os.path.join(last, 'quest.json')):
            last = None                              # a pack that has moved or gone: start from the default
        self.open(pack or last or DEFAULT_PACK)

    # ── menus ───────────────────────────────────────────────────────────────
    def _menus(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label='New pack...', command=self.new_pack)
        f.add_command(label='Open pack...', command=self.open_dialog)
        f.add_separator()
        f.add_command(label='Save', accelerator='Ctrl+S', command=self.save)
        f.add_command(label='Play from here', accelerator='F5', command=self.play)
        f.add_separator()
        f.add_command(label='Quit', command=self.quit)
        m.add_cascade(label='File', menu=f)
        e = tk.Menu(m, tearoff=False)
        e.add_command(label='Undo map change', accelerator='Ctrl+Z', command=lambda: self._undo(False))
        e.add_command(label='Redo map change', accelerator='Ctrl+Y', command=lambda: self._undo(True))
        m.add_cascade(label='Edit', menu=e)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label='Map tools', command=lambda: self._help('map'))
        h.add_command(label='About', command=lambda: self._help('about'))
        m.add_cascade(label='Help', menu=h)
        self.root.config(menu=m)

    def _help(self, what):
        if what == 'map':
            from . import map_tab
            messagebox.showinfo('Map tools', map_tab.__doc__.split('\n', 2)[2].strip())
        else:
            messagebox.showinfo('About', 'The Quest Deluxe Editor for The Quest Deluxe.\nPacks are described in docs/QUEST_PACKS.md, '
                                         'level scripts in docs/EVENTS.md.')

    def _undo(self, redo):
        if isinstance(self.root.focus_get(), tk.Text):
            return                                  # the text box has its own undo
        self.map_tab.redo() if redo else self.map_tab.undo()

    # ── settings file (the last pack opened) ────────────────────────────────
    @staticmethod
    def _settings() -> dict:
        try:
            with open(SETTINGS) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _remember(self, path):
        try:
            with open(SETTINGS, 'w') as fh:
                json.dump({'last': path}, fh)
        except OSError:
            pass

    # ── packs ───────────────────────────────────────────────────────────────
    def open(self, path):
        if not os.path.isdir(path):
            path = os.path.join(PACKS_DIR, path)
        if not os.path.exists(os.path.join(path, 'quest.json')):
            messagebox.showerror('Open pack', f'{path} is not a quest pack (it has no quest.json).')
            if self.project is None:
                path = DEFAULT_PACK
            else:
                return
        self.project = Project(path)
        self.dirty = False
        self._remember(path)
        classes = [f'{c["id"]} {c["name"]}' for c in self.project.tables['classes']]
        self.play_class.config(values=classes)
        self.play_class.set(classes[0] if classes else '')
        for tab in (self.map_tab, self.events_tab, self.text_tab, self.quest_tab, self.items_tab, self.creatures_tab,
                    self.classes_tab, self.spells_tab, self.tiles_tab, self.shops_tab, self.dialogue_tab,
                    self.stories_tab):
            tab.load()
        self._title()

    def open_dialog(self):
        if not self._keep_changes():
            return
        path = filedialog.askdirectory(title='Open a quest pack', initialdir=PACKS_DIR, mustexist=True)
        if path:
            self.open(path)

    def new_pack(self):
        if not self._keep_changes():
            return
        name = simpledialog.askstring('New pack', 'A name for the new pack (its folder under packs/):',
                                      parent=self.root)
        if not name:
            return
        dest = os.path.join(PACKS_DIR, name.strip())
        if os.path.exists(dest):
            messagebox.showerror('New pack', f'packs/{name} already exists.')
            return
        blank = messagebox.askyesnocancel(
            'New pack', f'Start from the pack now open ({self.project.name})?\n\n'
                        'Yes: its items, creatures, spells, classes, tiles and pictures, but one empty level and no '
                        'story - for a new quest.\nNo: a complete copy of it, levels and story included.')
        if blank is None:
            return
        Project.create(dest, self.project.root, blank=blank)
        self.open(dest)

    def save(self):
        if self.project and self.dirty:
            self.project.save()
            self.dirty = False
            self._title()

    def _keep_changes(self) -> bool:
        """Before leaving this pack: save it, drop the changes, or stay."""
        if not self.dirty:
            return True
        ans = messagebox.askyesnocancel('Unsaved changes', f'Save the changes to {self.project.name}?')
        if ans is None:
            return False
        if ans:
            self.save()
        return True

    def changed(self):
        if not self.dirty:
            self.dirty = True
            self._title()

    def status(self, text):
        self.map_tab.status.config(text=text)

    def pictures_changed(self, layer, v):
        self.map_tab.art.forget(layer, v)
        if layer == 'item':
            self.map_tab.art.forget('bag', v)

    def scripts_changed(self, level):
        self.events_tab.reload(level)

    def _title(self):
        p = self.project
        self.root.title(f'{"*" if self.dirty else ""}{p.quest.get("title") or p.name} ({p.name}) - The Quest Deluxe Editor')

    def _tab_changed(self):
        tab = self.tabs.nametowidget(self.tabs.select())
        if tab is self.classes_tab:
            self.play_class.config(values=[f'{c["id"]} {c["name"]}' for c in self.project.tables['classes']])
        if tab in (self.events_tab, self.text_tab, self.dialogue_tab, self.stories_tab, self.shops_tab):
            tab.load()                                  # the same files can be changed from other tabs
        elif tab is self.map_tab:
            self.map_tab._show_settings()
            self.map_tab._fill_palette()                 # names and pictures may have changed
            self.map_tab.redraw()

    # ── test play ───────────────────────────────────────────────────────────
    def play(self):
        if self.dirty:
            self.save()
        m = self.map_tab
        cls = int(self.play_class.get().split()[0]) if self.play_class.get() else 1
        cmd = [sys.executable, os.path.join(ROOT, 'run_deluxe.py'), '--pack', self.project.root,
               '--quick', str(cls), '--level', str(m.level)]
        if m.selected:
            cmd += ['--at', f'{m.selected[0]},{m.selected[1]}']
        self.player = subprocess.Popen(cmd, cwd=ROOT)

    def quit(self):
        if self._keep_changes():
            self.root.destroy()


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack')
    args = ap.parse_args(argv)
    root = tk.Tk()
    App(root, args.pack)
    root.mainloop()
