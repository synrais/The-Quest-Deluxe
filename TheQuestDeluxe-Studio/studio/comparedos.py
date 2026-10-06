"""The "Compare to The Quest DOS" window: choose a level, a square and a hero, and start the pack's game and the original DOS game
side by side, fed the same keys (see compare/ and docs/COMPARE.md)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from compare import dos
from engine import savefile
from engine.pack import ROOT
from core import custom

from . import levelmeta, ui
from .pages.world_places import SquarePicker
from .theme import px


def saves_dir(pack_root: str) -> str:
    inside = os.path.dirname(os.path.abspath(pack_root)) == os.path.abspath(custom.CUSTOM_DIR)
    return os.path.join(ROOT, 'saves', *(['Custom Maps'] if inside else []), os.path.basename(pack_root))


def saved_heroes(pack_root: str) -> list:
    """[(slot, 'Knight, level 4', path)] for the saves of the pack."""
    out = []
    slots = savefile.Slots(saves_dir(pack_root))
    for n, level, cls in slots.listing(all_=True):
        out.append((n, f'Slot {n}: class {cls}, level {level}', slots.path(n)))
    return out


def problems() -> list:
    """What is missing for the comparison to run on this computer (empty when it can)."""
    out = []
    if dos.find_dosbox() is None:
        out.append('DOSBox is not installed (it comes in dos/dosbox on Windows; on Linux or macOS install it: apt install dosbox).')
    if not os.path.isfile(os.path.join(dos.ORIGINAL, 'TheQuest.exe')):
        out.append('The original game files are missing from dos/TheQuest.')
    if not sys.platform.startswith('win') and not (shutil.which('xdotool') and shutil.which('import')):
        out.append('On Linux the comparison needs xdotool and ImageMagick (apt install xdotool imagemagick).')
    return out


def command(pack_root, level, at, hero_path=None, cls=1, keep_bugs=True, same_things=True, hero_label='') -> list:
    cmd = [sys.executable, os.path.join(ROOT, 'run_compare.py'), '--level', str(level), '--at', f'{at[0]},{at[1]}',
           '--class', str(cls), '--fixes', 'off' if keep_bugs else 'on', '--pack', pack_root,
           '--same-things', 'on' if same_things else 'off']
    if hero_label:
        cmd += ['--hero-label', hero_label]
    if hero_path:
        cmd += ['--hero-file', hero_path]
    return cmd


class CompareDialog(ui.Dialog):
    def __init__(self, app):
        super().__init__(app.root, 'Compare to The Quest DOS', width=px(620))
        self.app, self.s = app, app.session
        self.level = tk.IntVar(value=1)
        self.at = levelmeta.start_of(self.s, 1)
        self.chosen = False                          # a square has been picked (it is asked for when it has not)
        self.same = tk.BooleanVar(value=True)
        self.hero = tk.StringVar(value='new')
        self.keep = tk.BooleanVar(value=True)
        self.heroes = saved_heroes(self.s.project.root)
        b = self.body
        ttk.Label(b, text='Compare to The Quest DOS', style='H2.TLabel').pack(anchor='w')
        ttk.Label(b, text='Your pack\'s game and the original DOS game open side by side at the same place, with the same hero. Type in the '
                          'window that says "The Quest Deluxe": every key goes to both, and the dice are matched, so any difference is a '
                          'real one. F12 saves a bug report of what both show.', style='Dim.TLabel', wraplength=px(560),
                  justify='left').pack(anchor='w', pady=(px(6), px(10)))
        bad = problems()
        if bad:
            ttk.Label(b, text='\n'.join(bad), style='Bad.TLabel', wraplength=px(560), justify='left').pack(anchor='w', pady=(0, px(8)))
        ttk.Label(b, text='Level (1 to 7 are in the original)', style='H3.TLabel').pack(anchor='w')
        levels = min(7, self.s.levels)
        ui.Segmented(b, [(str(n), str(n)) for n in range(1, levels + 1)], self._level, '1').pack(anchor='w', pady=(px(4), px(8)))
        row = ttk.Frame(b)
        row.pack(fill='x')
        ttk.Label(row, text='Where on the level', style='H3.TLabel').pack(side='left')
        self.where = ttk.Label(row, text='', style='Dim.TLabel')
        self.where.pack(side='left', padx=px(10))
        ttk.Button(row, text='Pick a square on the map…', command=self._pick).pack(side='left')
        self._show_at()
        ttk.Label(b, text='The hero', style='H3.TLabel').pack(anchor='w', pady=(px(12), 0))
        ttk.Radiobutton(b, text='A new hero of class', value='new', variable=self.hero).pack(anchor='w')
        classes = self.s.project.tables['classes']
        self.cls = ttk.Combobox(b, state='readonly', width=20, values=[f'{c["id"]} {c["name"]}' for c in classes])
        self.cls.set(self.cls['values'][0] if classes else '')
        self.cls.pack(anchor='w', padx=px(24))
        for n, text, path in self.heroes:
            ttk.Radiobutton(b, text='From my saves: ' + text, value=str(n), variable=self.hero).pack(anchor='w')
        if not self.heroes:
            ttk.Label(b, text='(No saved games for this pack yet: play, press V to save, and they will be here.)',
                      style='Faint.TLabel').pack(anchor='w', padx=px(24))
        ttk.Checkbutton(b, text="Keep the original's bugs in my game too (so the two match; leave on to compare)",
                        variable=self.keep).pack(anchor='w', pady=(px(12), 0))
        ttk.Checkbutton(b, text="Leave out of both what the original does not have (a hero's new items, spells and classes: it cannot hold them)",
                        variable=self.same).pack(anchor='w')
        self.add_buttons([('Cancel', None, 'TButton'), ('Start the comparison', 'go', 'Accent.TButton')], default='go')

    def _level(self, key):
        self.level.set(int(key))
        self.at = levelmeta.start_of(self.s, int(key))
        self.chosen = False
        self._show_at()

    def _show_at(self):
        x, y = self.at
        self.where.configure(text=f'square ({x}, {y}), screen ({(x - 1) // 10 + 1}, {(y - 1) // 10 + 1})')

    def _pick(self):
        p = SquarePicker(self, self.s, self.level.get(), *self.at)
        if p.run() == 'ok':
            self.at = p.pos
            self.chosen = True
            self._show_at()
            return True
        return False

    def close(self, value):
        """Starting asks which square to start from, if it has not been said."""
        if value == 'go' and not self.chosen and not self._pick():
            return
        super().close(value)

    def launch(self):
        """The command that starts the comparison (what the buttons chose)."""
        hero_path = None
        if self.hero.get() != 'new':
            hero_path = next((p for n, t, p in self.heroes if str(n) == self.hero.get()), None)
        cls = int(self.cls.get().split()[0]) if self.cls.get() else 1
        label = next((t for n, t, p in self.heroes if str(n) == self.hero.get()), '') if self.hero.get() != 'new' else ''
        return command(self.s.project.root, self.level.get(), self.at, hero_path, cls, self.keep.get(), self.same.get(), label)


def open_compare(app):
    app.session.autosave()
    d = CompareDialog(app)
    if d.run() != 'go':
        return
    bad = problems()
    if bad:
        ui.inform(app.root, 'Compare to DOS', 'It cannot run yet:\n\n' + '\n'.join(bad))
        return
    log = os.path.join(os.path.expanduser('~'), '.quest_compare_log.txt')
    with open(log, 'w', encoding='utf-8') as fh:
        subprocess.Popen(d.launch(), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    app.say('Starting the comparison: your game and the original open side by side in a moment.', 'ok')
