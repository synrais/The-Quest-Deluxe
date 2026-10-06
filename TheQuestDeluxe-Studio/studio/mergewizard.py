"""The Merge window: bring things from another quest into the open one, choosing what, and seeing what would be overwritten or lost."""
from __future__ import annotations

import os
import shutil
import tempfile
import tkinter as tk
from tkinter import filedialog, ttk

from core import custom
from core.project import Project
from engine import packio

from .stepdialog import wizard_size
from . import icons, merge, ui, upgrade
from .gallery import Entry, Gallery
from .theme import C, px

ACTIONS = [('renumber', 'Bring it under a free number (keep both)'), ('replace', 'Replace mine with it'), ('skip', 'Keep mine, leave it behind')]
ACTION_TEXT = dict(ACTIONS)
SEV = {'lost': ('warn', 'bad', 'Something of yours is lost'), 'changed': ('warn', 'warn', 'Something changes'),
       'check': ('info', 'info', 'Look at it afterwards'), 'note': ('check', 'dim', 'What will happen')}


class MergeWindow(ui.Dialog):
    def __init__(self, app):
        w, h = wizard_size(app.root)
        super().__init__(app.root, 'Merge quests', width=w, height=h)
        self.app, self.s = app, app.session
        self.dst = self.s.project
        self.src = None
        self.src_path = None
        self.temp = None
        self.plan = None
        self.step = 0
        self.vars = {}
        self.level_vars = {}
        self.frame.configure(padding=px(16))
        self.title_label = ttk.Label(self.body, text='', style='H1.TLabel')
        self.title_label.pack(anchor='w')
        self.sub = ttk.Label(self.body, text='', style='Dim.TLabel', wraplength=px(900), justify='left')
        self.sub.pack(anchor='w', pady=(px(2), px(8)))
        self.page = ttk.Frame(self.body)
        self.page.pack(fill='both', expand=True)
        self.back_btn = ttk.Button(self.foot, text='Back', command=lambda: self.go(self.step - 1))
        self.back_btn.pack(side='left')
        self.go_btn = ttk.Button(self.foot, text='Next', style='Accent.TButton', command=self.forward)
        self.go_btn.pack(side='right')
        ttk.Button(self.foot, text='Cancel', command=lambda: self.close(None)).pack(side='right', padx=px(8))
        self.picked = None
        self.go(0)

    # ── steps ───────────────────────────────────────────────────────────────
    def go(self, i):
        self.step = max(0, min(2, i))
        for w in self.page.winfo_children():
            w.destroy()
        [self._pick_page, self._choose_page, self._review_page][self.step]()
        self.back_btn.state(['!disabled'] if self.step else ['disabled'])
        self.go_btn.configure(text=['Next', 'Next', 'Merge'][self.step])
        self.go_btn.state(['!disabled'] if (self.step or self.src is not None) else ['disabled'])

    def forward(self):
        if self.step == 0:
            if self.src is None:
                return
            self.plan = merge.build_plan(self.src, self.dst)
            for k in merge.KINDS:
                self.plan.choose(k, False)
            self.go(1)
        elif self.step == 1:
            self.go(2)
        else:
            self.do_merge()

    # 1: which quest
    def _pick_page(self):
        self.title_label.configure(text='Which quest do you want to bring things from?')
        self.sub.configure(text=f'They are brought into the quest you have open: "{self.dst.quest.get("title") or self.dst.name}". To merge into a '
                                f'different quest, open that one first. The quest you bring things from is only read, never changed.')
        names = [n for n in custom.packs() if os.path.abspath(custom.pack_dir(n)) != os.path.abspath(self.dst.root)]
        entries = [Entry('__locked__', 'The Quest (the original 7 levels)', 'comes with the game', icons.icon('map', C['accent'], px(24)), group='Quests')]
        for n in names:
            title, lv = n, ''
            try:
                qq = packio.read_json(os.path.join(custom.pack_dir(n), 'quest.json'))
                title, lv = qq.get('title') or n, f'{qq.get("levels", "?")} levels'
            except (OSError, ValueError):
                pass
            entries.append(Entry(n, title, lv, icons.icon('map', C['accent'], px(24)), group='Your quests'))
        holder = ttk.Frame(self.page)
        holder.pack(fill='both', expand=True)
        self.gal = Gallery(holder, on_select=self._source, on_open=lambda k: (self._source(k), self.forward()), list_mode=True)
        self.gal.pack(side='left', fill='both', expand=True)
        side = ttk.Frame(holder)
        side.pack(side='left', fill='y', padx=px(16))
        ttk.Button(side, text='A folder or zip from somewhere else…', command=self._browse).pack(anchor='w')
        ttk.Label(side, text='Old packs and packs from other people open too: a copy is\nmended first (missing files put in) and read.',
                  style='Faint.TLabel', justify='left').pack(anchor='w', pady=px(8))
        self.picked_label = ttk.Label(side, text='', style='Dim.TLabel', wraplength=px(300), justify='left')
        self.picked_label.pack(anchor='w', pady=px(10))
        self.gal.set_items(entries)
        if self.picked:
            self.gal.select(self.picked, scroll=False)
        self._shown_source()

    def _source(self, key):
        self.picked = key
        try:
            if key == '__locked__':
                from engine.pack import DEFAULT_PACK
                path = DEFAULT_PACK
            else:
                path = custom.pack_dir(key)
            self._read(path)
        except Exception as e:                                         # noqa: BLE001 - say what is wrong with it
            self.src = None
            ui.inform(self, 'Merge', f'That quest could not be read: {e}')
        self._shown_source()

    def _browse(self):
        path = filedialog.askopenfilename(parent=self, title='A quest to bring things from (a zip), or Cancel to pick a folder',
                                          filetypes=[('Zip of a quest', '*.zip'), ('All files', '*.*')])
        if not path:
            path = filedialog.askdirectory(parent=self, title='A quest folder to bring things from')
        if not path:
            return
        if self.temp:
            shutil.rmtree(self.temp, ignore_errors=True)
        self.temp = tempfile.mkdtemp(prefix='quest_merge_')
        try:
            dest, notes = upgrade.import_pack(path, self.temp)
            self._read(dest)
            self.picked = None
            if notes:
                ui.inform(self, 'Mended', 'That quest was not complete, so a copy was mended before reading it:\n\n' + '\n'.join(notes[:8]))
        except Exception as e:                                         # noqa: BLE001
            self.src = None
            ui.inform(self, 'Merge', f'That could not be read as a quest: {e}')
        self._shown_source()

    def _read(self, path):
        if custom.is_locked(path):
            self.src = Project(path)
        else:
            tmp = tempfile.mkdtemp(prefix='quest_merge_')
            copy = os.path.join(tmp, 'q')
            shutil.copytree(path, copy)                                # (a pack made by an older editor is mended on the copy, not on itself)
            upgrade.upgrade(copy)
            self.src = Project(copy)
            if self.temp is None:
                self.temp = tmp
        self.src_path = path

    def _shown_source(self):
        if not hasattr(self, 'picked_label') or not self.picked_label.winfo_exists():
            return
        s = self.src
        self.picked_label.configure(text='' if s is None else f'{s.quest.get("title") or s.name}: {s.levels} levels, {len(s.tables["creatures"])} '
                                                              f'creatures, {len(s.tables["items"])} items, {len(s.tables["spells"])} spells.')
        self.go_btn.state(['!disabled'] if s is not None else ['disabled'])

    # 2: what to bring
    def _choose_page(self):
        self.title_label.configure(text='What do you want to bring over?')
        self.sub.configure(text='Tick what to bring. Next shows what would be added, what is already the same and what would clash, and lets you decide.')
        sc = ui.Scrolled(self.page)
        sc.pack(fill='both', expand=True)
        for kind in merge.KINDS:
            entries = self.plan.entries[kind]
            if not entries:
                continue
            new = sum(1 for e in entries if e.status == 'new')
            same = sum(1 for e in entries if e.status == 'same')
            clash = sum(1 for e in entries if e.status == 'clash')
            if kind == 'levels':
                bits = [f'{len(entries)} levels, added after your last']
            else:
                bits = [f'{new} new'] + ([f'{same} the same'] if same else []) + ([f'{clash} different under the same number'] if clash else [])
            card = tk.Frame(sc.body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
            card.pack(fill='x', padx=px(6), pady=px(3))
            inner = ttk.Frame(card, style='Raised.TFrame', padding=px(10))
            inner.pack(fill='x')
            v = tk.BooleanVar(value=kind in self.plan.chosen)
            self.vars[kind] = v
            ttk.Checkbutton(inner, text=merge.TITLES[kind], variable=v, style='Raised.TCheckbutton',
                            command=lambda k=kind, v=v: self.plan.choose(k, v.get())).grid(row=0, column=0, sticky='w')
            ttk.Label(inner, text=' · '.join(bits), style='Raised.Dim.TLabel').grid(row=1, column=0, sticky='w', padx=px(24))
            if kind == 'levels':
                row = ttk.Frame(inner, style='Raised.TFrame')
                row.grid(row=2, column=0, sticky='w', padx=px(24), pady=(px(4), 0))
                self.level_vars = {}
                for e in entries:
                    lv = tk.BooleanVar(value=e.key in self.plan.level_picks)
                    self.level_vars[e.key] = lv
                    ttk.Checkbutton(row, text=str(e.key), variable=lv, style='Raised.TCheckbutton', command=self._levels_changed).pack(side='left', padx=2)
        ttk.Frame(sc.body, height=px(10)).pack()

    def _levels_changed(self):
        self.plan.level_picks = [k for k, v in self.level_vars.items() if v.get()]
        if self.plan.level_picks and 'levels' in self.vars:
            self.vars['levels'].set(True)
            self.plan.choose('levels', True)

    # 3: review
    def _review_page(self):
        self.title_label.configure(text='Look it over')
        self.sub.configure(text='What happens to each thing that clashes is up to you. The notes on the right say what will be lost or changed, with an example.')
        merge.assign_numbers(self.plan, self.dst)
        cols = ttk.Frame(self.page)
        cols.pack(fill='both', expand=True)
        left = ttk.Frame(cols)
        left.pack(side='left', fill='both', expand=True)
        ttk.Label(left, text='When a number is already taken', style='H3.TLabel').pack(anchor='w')
        self.clash_box = ui.Scrolled(left)
        self.clash_box.pack(fill='both', expand=True, pady=px(4))
        ui.vsep(cols).pack(side='left', fill='y', padx=px(10))
        right = ttk.Frame(cols, width=px(430))
        right.pack(side='left', fill='both')
        right.pack_propagate(False)
        ttk.Label(right, text='What will happen', style='H3.TLabel').pack(anchor='w')
        self.warn_box = ui.Scrolled(right)
        self.warn_box.pack(fill='both', expand=True, pady=px(4))
        self.summary = ttk.Label(right, text='', style='Dim.TLabel', wraplength=px(400), justify='left')
        self.summary.pack(anchor='w')
        any_clash = False
        for kind in merge.KINDS:
            if kind not in self.plan.chosen or kind in ('levels',):
                continue
            for e in self.plan.entries[kind]:
                if e.status != 'clash':
                    continue
                any_clash = True
                row = tk.Frame(self.clash_box.body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
                row.pack(fill='x', padx=px(4), pady=px(3))
                inner = ttk.Frame(row, style='Raised.TFrame', padding=px(8))
                inner.pack(fill='x')
                what = merge.TITLES[kind].split(' (')[0].rstrip('s') if kind not in ('settings', 'talk') else merge.TITLES[kind]
                ttk.Label(inner, text=f'{what} {e.key}: yours is "{e.mine}", theirs is "{e.name}"', style='Raised.TLabel', wraplength=px(430),
                          justify='left').pack(anchor='w')
                choices = ACTIONS if kind not in ('skills', 'settings', 'talk') and not (kind == 'stories' and e.key in merge.RESERVED_STORIES) else \
                    [a for a in ACTIONS if a[0] != 'renumber']
                var = tk.StringVar(value=ACTION_TEXT[e.action if e.action != 'add' else 'renumber'])
                cb = ttk.Combobox(inner, state='readonly', values=[t for _, t in choices], textvariable=var, width=44)
                cb.pack(anchor='w', pady=(px(4), 0))
                cb.bind('<<ComboboxSelected>>', lambda ev, e=e, var=var, choices=choices: self._action(e, next(a for a, t in choices if t == var.get())))
        if not any_clash:
            ttk.Label(self.clash_box.body, text='Nothing you chose clashes with something of yours.', style='Dim.TLabel').pack(anchor='w', padx=px(6), pady=px(6))
        self._warnings()

    def _action(self, e, action):
        e.action = action
        merge.assign_numbers(self.plan, self.dst)
        self._warnings()

    def _warnings(self):
        ws = merge.warnings(self.plan, self.src, self.dst)
        for w in self.warn_box.body.winfo_children():
            w.destroy()
        order = {'lost': 0, 'changed': 1, 'note': 2, 'check': 3}
        for w in sorted(ws, key=lambda x: order[x.severity]):
            icon, colour, head = SEV[w.severity]
            row = tk.Frame(self.warn_box.body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
            row.pack(fill='x', padx=px(4), pady=px(3))
            tk.Frame(row, bg=C[colour] if colour in C else C['dim'], width=4).pack(side='left', fill='y')
            col = tk.Frame(row, bg=C['raised'])
            col.pack(side='left', fill='x', expand=True, padx=px(8), pady=px(6))
            tk.Label(col, text=w.title, bg=C['raised'], fg=C['text'], font=('Segoe UI', 10, 'bold'), wraplength=px(370), justify='left', anchor='w').pack(fill='x')
            tk.Label(col, text=w.detail, bg=C['raised'], fg=C['dim'], wraplength=px(370), justify='left', anchor='w').pack(fill='x')
        lost = sum(1 for w in ws if w.severity == 'lost')
        self.summary.configure(text=(f'{lost} of your things would be overwritten. ' if lost else '') + 'It is one step in Undo (Ctrl+Z).')
        self.go_btn.state(['!disabled'] if self.plan.chosen else ['disabled'])

    # ── doing it ────────────────────────────────────────────────────────────
    def do_merge(self):
        ws = merge.warnings(self.plan, self.src, self.dst)
        lost = [w for w in ws if w.severity == 'lost']
        if lost and not ui.confirm(self, 'Overwrite your things?', 'These of yours would be overwritten:\n\n' + '\n'.join('• ' + w.title for w in lost[:8])
                                   + ('\n• ...' if len(lost) > 8 else '') + '\n\nUndo (Ctrl+Z) brings them back. Go on?', 'Merge', danger=True):
            return
        self.s.autosave()
        rep = merge.apply(self.s, self.src, self.plan)
        self.report = rep
        self.close('done')

    def close(self, value):
        if self.temp:
            shutil.rmtree(self.temp, ignore_errors=True)
            self.temp = None
        super().close(value)


def open_merge(app):
    w = MergeWindow(app)
    if w.run() == 'done':
        rep = w.report
        app.say('Merged: ' + rep.summary(), 'ok')
        app.reload_all()
        app.go('world' if rep.first_level else app.current or 'home', **({'level': rep.first_level} if rep.first_level else {}))
