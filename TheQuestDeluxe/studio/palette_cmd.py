"""Ctrl+K: type to jump to a level, a creature, an item, a spell, a hero, a tile, or to run a command."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import icons, theme
from .theme import C, px


class CommandPalette(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=C['line'])
        outer = tk.Frame(self, bg=C['panel'])
        outer.pack(padx=1, pady=1, fill='both', expand=True)
        top = ttk.Frame(outer, padding=(px(14), px(12)))
        top.pack(fill='x')
        ttk.Label(top, image=icons.icon('search', C['dim'], px(18))).pack(side='left', padx=(0, px(10)))
        self.var = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.var, bg=C['panel'], fg=C['text'], insertbackground=C['text'],
                              relief='flat', font=(theme.FONT, 14), highlightthickness=0)
        self.entry.pack(side='left', fill='x', expand=True)
        ttk.Separator(outer).pack(fill='x')
        self.list = tk.Frame(outer, bg=C['panel'])
        self.list.pack(fill='both', expand=True)
        self.foot = tk.Label(outer, text='↑ ↓ to choose   Enter to go   Esc to close', bg=C['panel'], fg=C['faint'],
                             font=(theme.FONT, 8), anchor='w', padx=px(14), pady=px(5))
        self.foot.pack(fill='x')
        self.results: list = []
        self.rows: list = []
        self.index = 0
        self.var.trace_add('write', lambda *a: self.refresh())
        self.entry.bind('<Down>', lambda e: self.move(1))
        self.entry.bind('<Up>', lambda e: self.move(-1))
        self.entry.bind('<Return>', lambda e: self.run())
        self.entry.bind('<Escape>', lambda e: self.destroy())
        self.bind('<FocusOut>', lambda e: self.after(150, self._lost))
        w, h = px(620), px(430)
        r = app.root
        self.geometry(f'{w}x{h}+{r.winfo_rootx() + (r.winfo_width() - w) // 2}+{r.winfo_rooty() + px(70)}')
        self.refresh()
        self.deiconify()
        self.lift()
        self.entry.focus_force()

    def _lost(self):
        try:
            if self.focus_get() is None:
                self.destroy()
        except (KeyError, tk.TclError):
            self.destroy()

    # ── what can be found ───────────────────────────────────────────────────
    def candidates(self):
        a, s = self.app, self.app.session
        p = s.project
        out = []
        cmds = [('Save now, and make the zip', 'Ctrl+S', 'save', a.save),
                ('Undo', 'Ctrl+Z', 'undo', lambda: a._undo(False)), ('Redo', 'Ctrl+Y', 'redo', lambda: a._undo(True)),
                ('Play the game from here', 'F5', 'play', a.play),
                ('Play from the title screen', '', 'play', lambda: a.play(from_start=True)),
                ('Run the Quest Doctor', 'finds what is missing', 'check', lambda: a.go('doctor')),
                ('New level with the wizard', 'a whole level, start to end', 'wand', lambda: a.go('world', wizard=True)),
                ('New blank level', '', 'plus', lambda: a.go('world', new_level=True)),
                ('New creature', '', 'skull', lambda: a.go('creatures', new=True)),
                ('New item', '', 'sword', lambda: a.go('items', new=True)),
                ('New hero class', '', 'helmet', lambda: a.go('heroes', new=True)),
                ('New spell', '', 'wand', lambda: a.go('spells', new=True)),
                ('Switch the theme (dark / light)', '', 'sun', a.toggle_theme),
                ('Shortcuts and help', '', 'info', a.help),
                ('Mods: switch additions off or on', '', 'gear', lambda: a.go('mods')),
                ('Send my edits', '', 'save', a.send_edits)]
        for title, sub, icon, fn in cmds:
            out.append((title, sub, icon, fn, 0))
        for key, title, icon, _ in __import__('studio.app', fromlist=['NAV']).NAV:
            out.append((f'Go to {title}', '', icon, lambda k=key: a.go(k), 1))
        for n in range(1, s.levels + 1):
            out.append((f'Level {n}', 'World', 'map', lambda n=n: a.go('world', level=n), 2))
        for r in p.tables['creatures']:
            out.append((r.get('name') or f'#{r["id"]}', f'Creature {r["id"]}', 'skull',
                        lambda i=r['id']: a.go('creatures', select=i), 3))
        for r in p.tables['items']:
            if r['id']:
                out.append((r.get('name') or f'#{r["id"]}', f'Item {r["id"]}  ({r.get("type", "")})', 'sword',
                            lambda i=r['id']: a.go('items', select=i), 3))
        for r in p.tables['spells']:
            out.append((r.get('name') or f'#{r["id"]}', f'Spell {r["id"]}', 'wand', lambda i=r['id']: a.go('spells', select=i), 3))
        for r in p.tables['classes']:
            out.append((r.get('name') or f'#{r["id"]}', f'Hero {r["id"]}', 'helmet', lambda i=r['id']: a.go('heroes', select=i), 3))
        from . import storytext
        for st in storytext.stories(p):
            first = (st.lines[0] if st.lines else '')[:50]
            out.append((f'Story {st.number}: {first}', 'Story', 'book', lambda n=st.number: a.go('story', tab='stories', select=n), 3))
        for n in range(0, s.levels + 1):
            out.append(('Events of every level' if n == 0 else f'Events of level {n}', 'Events', 'bolt', lambda n=n: a.go('events', level=n), 3))
        for kind, title in (('floors', 'Floor'), ('walls', 'Wall'), ('decos', 'Decoration')):
            for r in p.tiles.get(kind, []):
                out.append((r.get('name') or f'#{r["id"]}', f'{title} {r["id"]}', 'tiles',
                            lambda k=kind, i=r['id']: a.go('tiles', kind=k, select=i), 3))
        return out

    def refresh(self):
        q = self.var.get().strip().lower()
        scored = []
        for title, sub, icon, fn, rank in self.candidates():
            t = title.lower()
            if not q:
                score = 100 + rank if rank == 0 else None
            elif t.startswith(q):
                score = 0 + rank / 10
            elif any(w.startswith(q) for w in t.replace('-', ' ').split()):
                score = 1 + rank / 10
            elif q in t:
                score = 2 + rank / 10
            elif q in f'{sub}'.lower():
                score = 3 + rank / 10
            else:
                continue
            if score is not None:
                scored.append((score, len(title), title, sub, icon, fn))
        scored.sort(key=lambda r: (r[0], r[1]))
        self.results = scored[:9]
        self.index = 0
        for w in self.list.winfo_children():
            w.destroy()
        self.rows = []
        if not self.results:
            tk.Label(self.list, text='Nothing found.', bg=C['panel'], fg=C['dim'], pady=px(20)).pack()
            return
        for i, (_, _, title, sub, icon, fn) in enumerate(self.results):
            row = tk.Frame(self.list, bg=C['panel'], cursor='hand2')
            row.pack(fill='x')
            img = tk.Label(row, image=icons.icon(icon, C['dim'], px(16)), bg=C['panel'])
            img.pack(side='left', padx=(px(16), px(10)), pady=px(7))
            t = tk.Label(row, text=title, bg=C['panel'], fg=C['text'], anchor='w', font=(theme.FONT, 11))
            t.pack(side='left')
            s2 = tk.Label(row, text=sub, bg=C['panel'], fg=C['faint'], anchor='e', font=(theme.FONT, 9))
            s2.pack(side='right', padx=px(16))
            for w in (row, img, t, s2):
                w.bind('<Button-1>', lambda e, i=i: self.run(i))
                w.bind('<Enter>', lambda e, i=i: self.set_index(i))
            self.rows.append((row, img, t, s2))
        self.set_index(0)

    def set_index(self, i):
        self.index = i
        for k, (row, img, t, s2) in enumerate(self.rows):
            bg = C['select'] if k == i else C['panel']
            for w in (row, img, t, s2):
                w.configure(bg=bg)

    def move(self, d):
        if self.rows:
            self.set_index((self.index + d) % len(self.rows))
        return 'break'

    def run(self, i=None):
        if not self.results:
            return
        fn = self.results[self.index if i is None else i][5]
        self.destroy()
        fn()
