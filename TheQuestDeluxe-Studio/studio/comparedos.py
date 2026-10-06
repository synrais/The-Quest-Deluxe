"""The "Compare to The Quest DOS" window: choose a level, a square and a hero, and start the pack's game and the original DOS game
side by side, fed the same keys (see compare/ and docs/COMPARE.md)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from compare import dos, loadout as loadouts
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


def command(pack_root, level, at, hero_path=None, cls=1, keep_bugs=True, same_things=True, hero_label='', gear=None) -> list:
    cmd = [sys.executable, os.path.join(ROOT, 'run_compare.py'), '--level', str(level), '--at', f'{at[0]},{at[1]}',
           '--class', str(cls), '--fixes', 'off' if keep_bugs else 'on', '--pack', pack_root,
           '--same-things', 'on' if same_things else 'off']
    if hero_label:
        cmd += ['--hero-label', hero_label]
    if hero_path:
        cmd += ['--hero-file', hero_path]
    if gear:
        import json
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.json', prefix='quest_loadout_')
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(gear, fh)
        cmd += ['--loadout', path]
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
        ttk.Label(b, text='Gear (both heroes wear and carry the same, from the original\'s own items)', style='H3.TLabel').pack(anchor='w', pady=(px(12), 0))
        row = ttk.Frame(b)
        row.pack(anchor='w', fill='x')
        self.gear = ttk.Combobox(row, state='readonly', width=30)
        self.gear.pack(side='left')
        ttk.Button(row, text='Choose the gear…', command=self._edit_gear).pack(side='left', padx=px(8))
        self._gear_names()
        ttk.Checkbutton(b, text="Keep the original's bugs in my game too (so the two match; leave on to compare)",
                        variable=self.keep).pack(anchor='w', pady=(px(12), 0))
        ttk.Checkbutton(b, text="Leave out of both what the original does not have (a hero's new items, spells and classes: it cannot hold them)",
                        variable=self.same).pack(anchor='w')
        ttk.Button(b, text='Check it works…', command=self._check).pack(anchor='w', pady=(px(10), 0))
        self.add_buttons([('Cancel', None, 'TButton'), ('Start the comparison', 'go', 'Accent.TButton')], default='go')

    def _check(self):
        c = CheckDialog(self.app)
        c.after(100, c.start)
        c.run()

    NO_GEAR = "(as the hero is: no change)"

    def _gear_names(self, pick=None):
        names = [self.NO_GEAR] + list(loadouts.presets())
        self.gear.configure(values=names)
        want = pick or (self.gear.get() if self.gear.get() in names else None) or self.app.settings.get('compare_gear', 'Fighter')
        self.gear.set(want if want in names else 'Fighter')

    def _edit_gear(self):
        d = LoadoutDialog(self, self.gear.get() if self.gear.get() != self.NO_GEAR else 'Fighter')
        d.run()
        self._gear_names(d.last)

    def chosen_gear(self):
        name = self.gear.get()
        if name == self.NO_GEAR or name not in loadouts.presets():
            return None
        return dict(loadouts.presets()[name], name=name)

    def _level(self, key):
        self.level.set(int(key))
        self.at = levelmeta.start_of(self.s, int(key))
        self.chosen = False
        self._show_at()

    def _show_at(self):
        x, y = self.at
        self.where.configure(text=f'square ({x}, {y}), screen ({(x - 1) // 10 + 1}, {(y - 1) // 10 + 1})')

    def _pick(self):
        got = SquarePicker(self, self.s, self.level.get(), *self.at).run()       # the square (x, y), or None when cancelled
        if got:
            self.at = tuple(got)
            self.chosen = True
            self._show_at()
            return True
        return False

    def close(self, value):
        """Starting asks which square to start from, if it has not been said."""
        if value == 'go' and not self.chosen and not self._pick():
            return
        if value == 'go':
            self.command_line = self.launch()                 # (read from the boxes now: they are gone once the window has closed)
        super().close(value)

    def launch(self):
        """The command that starts the comparison (what the buttons chose)."""
        hero_path = None
        if self.hero.get() != 'new':
            hero_path = next((p for n, t, p in self.heroes if str(n) == self.hero.get()), None)
        cls = int(self.cls.get().split()[0]) if self.cls.get() else 1
        label = next((t for n, t, p in self.heroes if str(n) == self.hero.get()), '') if self.hero.get() != 'new' else ''
        self.app.settings['compare_gear'] = self.gear.get()
        return command(self.s.project.root, self.level.get(), self.at, hero_path, cls, self.keep.get(), self.same.get(), label, self.chosen_gear())


class LoadoutDialog(ui.Dialog):
    """Choose the gear both heroes start in, from the original's items, and keep it as a named preset."""

    def __init__(self, parent, name):
        super().__init__(parent, 'Gear for the comparison', width=px(560))
        self.items = loadouts.original_items()
        self.last = name
        b = self.body
        ttk.Label(b, text='Gear for the comparison', style='H2.TLabel').pack(anchor='w')
        ttk.Label(b, text='Only things the original game has, so it can hold every one. Both heroes get exactly this: what they wear and what is in '
                          'the bag. Save it with a name to use it again; the built-in ones can be changed by saving over them.',
                  style='Dim.TLabel', wraplength=px(520), justify='left').pack(anchor='w', pady=(px(6), px(10)))
        top = ttk.Frame(b)
        top.pack(fill='x')
        ttk.Label(top, text='Loadout').pack(side='left')
        self.name = ttk.Combobox(top, width=26, values=list(loadouts.presets()))
        self.name.pack(side='left', padx=px(8))
        self.name.bind('<<ComboboxSelected>>', lambda e: self.show(self.name.get()))
        self.worn = {}
        for slot, label in loadouts.SLOTS:
            r = ttk.Frame(b)
            r.pack(fill='x', pady=2)
            ttk.Label(r, text=label, width=20).pack(side='left')
            box = ttk.Combobox(r, state='readonly', width=44, values=self.choices(slot))
            box.pack(side='left')
            self.worn[slot] = box
        ttk.Label(b, text='In the bag', style='H3.TLabel').pack(anchor='w', pady=(px(10), 0))
        r = ttk.Frame(b)
        r.pack(fill='x')
        self.bag = tk.Listbox(r, height=7, width=46, exportselection=False)
        self.bag.pack(side='left')
        side = ttk.Frame(r)
        side.pack(side='left', padx=px(8), anchor='n')
        self.add_box = ttk.Combobox(side, state='readonly', width=34, values=self.choices(None))
        self.add_box.pack()
        ttk.Button(side, text='Add to the bag', command=self.add).pack(anchor='w', pady=2)
        ttk.Button(side, text='Take out the selected', command=self.take).pack(anchor='w')
        self.say = ttk.Label(b, text='', style='Dim.TLabel')
        self.say.pack(anchor='w', pady=(px(8), 0))
        self.add_buttons([('Close', None, 'TButton'), ('Delete', 'delete', 'TButton'), ('Save', 'save', 'Accent.TButton')], default='save')
        self.show(name)

    def label(self, n):
        r = self.items[n]
        bits = [f'{k} {r[k]}' for k in ('atk', 'def', 'power') if r.get(k)]
        return f'{n}  {r.get("name") or "(no name)"}' + (f'  ({", ".join(bits)})' if bits else '')

    def choices(self, slot):
        fits = loadouts.FITS.get(slot) if slot else None
        out = [] if slot is None else ['(nothing)']
        for n, r in sorted(self.items.items()):
            if n > 0 and r.get('name') and ((fits and r.get('type') in fits) or (not fits and r.get('type') not in ('exit', 'ladder', 'rope', 'stairs',
                                                                                                                     'hole', 'jump_pad', 'teleporter', 'chest'))):
                out.append(self.label(n))
        return out

    @staticmethod
    def number(text):
        return int(text.split()[0]) if text and text[0].isdigit() else 0

    def show(self, name):
        p = loadouts.presets().get(name) or {'worn': {}, 'bag': []}
        self.name.set(name)
        for slot, box in self.worn.items():
            n = (p.get('worn') or {}).get(slot)
            box.set(self.label(n) if n in self.items else '(nothing)')
        self.bag.delete(0, 'end')
        for n in p.get('bag') or []:
            if n in self.items:
                self.bag.insert('end', self.label(n))

    def add(self):
        if self.add_box.get() and self.bag.size() < loadouts.BAG_ROOM:
            self.bag.insert('end', self.add_box.get())

    def take(self):
        for i in reversed(self.bag.curselection()):
            self.bag.delete(i)

    def current(self):
        return ({slot: self.number(box.get()) for slot, box in self.worn.items() if self.number(box.get())},
                [self.number(self.bag.get(i)) for i in range(self.bag.size())])

    def close(self, value):
        name = self.name.get().strip()
        if value == 'save':
            worn, bag = self.current()
            try:
                loadouts.save_preset(name, worn, bag)
            except ValueError as e:
                self.say.configure(text=str(e), style='Bad.TLabel')
                return
            self.last = name
            self.say.configure(text=f'Saved "{name}".', style='Dim.TLabel')
            self.name.configure(values=list(loadouts.presets()))
            return
        if value == 'delete':
            loadouts.delete_preset(name)
            self.name.configure(values=list(loadouts.presets()))
            if name in loadouts.presets():
                self.show(name)
                self.say.configure(text='That is a built-in loadout; its original gear is back.')
            else:
                self.show('Fighter')
                self.last = 'Fighter'
            return
        super().close(value)


LOG = os.path.join(os.path.expanduser('~'), '.quest_compare_log.txt')


def watch(app, proc, log_path=LOG, seconds=8, every=500):
    """If the comparison stops within its first seconds, say so and show why (it used to stop without a word)."""
    started = [0]

    def look():
        code = proc.poll()
        started[0] += every / 1000
        if code is None:
            if started[0] < seconds:
                app.root.after(every, look)
            return
        if code == 0:
            return
        try:
            with open(log_path, encoding='utf-8', errors='replace') as fh:
                tail = fh.read()[-1500:]
        except OSError:
            tail = ''
        ui.inform(app.root, 'The comparison did not start',
                  'It stopped straight away (exit code %s).\n\n%s\n\nPress "Check it works" in the Compare window to find out what is missing; the full text is in %s.'
                  % (code, tail.strip() or '(it said nothing)', log_path))
    app.root.after(every, look)


class CheckDialog(ui.Dialog):
    """Runs `run_compare.py --check` and shows what it says, to read or to copy and send on."""

    def __init__(self, app):
        super().__init__(app.root, 'Does the comparison work here?', width=px(680), height=px(520))
        self.app = app
        ttk.Label(self.body, text='Checking DOSBox, its window, its picture, its keys and its memory ...', style='H3.TLabel').pack(anchor='w')
        self.text = tk.Text(self.body, wrap='word', height=22, font=('Consolas', 10) if sys.platform.startswith('win') else ('Courier', 10))
        self.text.pack(fill='both', expand=True, pady=px(8))
        self.add_buttons([('Close', None, 'TButton'), ('Copy this', 'copy', 'TButton')])
        self.out = ''

    def start(self):
        import threading
        cmd = [sys.executable, os.path.join(ROOT, 'run_compare.py'), '--check']

        def work():
            try:
                r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=240)
                text = (r.stdout + ('\n' + r.stderr[-1500:] if r.returncode and r.stderr.strip() else '')).strip()
            except (OSError, subprocess.SubprocessError) as e:
                text = f'The check could not run: {e}'
            self.after(0, lambda: self.show(text))
        threading.Thread(target=work, daemon=True).start()

    def show(self, text):
        if not self.winfo_exists():
            return
        self.out = text
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)

    def close(self, value):
        if value == 'copy':
            self.clipboard_clear()
            self.clipboard_append(self.out)
            return
        super().close(value)


def open_compare(app):
    app.session.autosave()
    d = CompareDialog(app)
    if d.run() != 'go':
        return
    bad = problems()
    if bad:
        ui.inform(app.root, 'Compare to DOS', 'It cannot run yet:\n\n' + '\n'.join(bad))
        return
    try:
        with open(LOG, 'w', encoding='utf-8') as fh:
            proc = subprocess.Popen(d.command_line, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    except OSError as e:
        ui.inform(app.root, 'The comparison did not start', f'It could not be started: {e}')
        return
    watch(app, proc)
    app.say('Starting the comparison: your game and the original open side by side in a moment.', 'ok')
