"""Home: the quest at a glance, what to make next, what is wrong, and the last things changed."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import doctor, icons, levelmeta, theme, ui
from ..theme import C, px
from .base import Page


class HomePage(Page):
    key, title, icon = 'home', 'Home', 'home'

    def build(self):
        self.scroller = ui.Scrolled(self)
        self.scroller.pack(fill='both', expand=True)
        self._job = None
        self._thumbs = {}
        self.s.on('any', self._changed)
        self._per = 0
        self.scroller.canvas.bind('<Configure>', lambda e: self._resized(), add='+')

    def _changed(self, scope, source):
        if isinstance(scope, tuple) and scope[0] == 'map':
            self._thumbs.pop(scope[1], None)
        if self.visible and self._job is None:
            self._job = self.after(300, self._redraw)

    def per_row(self) -> int:
        """How many level cards fit across (so the whole world is on one row when the window is wide: nothing to scroll to)."""
        w = self.scroller.canvas.winfo_width()
        if w < 300:                                                   # not laid out yet: the window's width less the menu on the left
            w = max(self.app.root.winfo_width(), min(self.app.root.winfo_screenwidth(), 1500)) - px(240)
        return max(4, (w - px(60)) // px(150))

    def _resized(self):
        if self.visible and self._job is None and self.per_row() != self._per:
            self._job = self.after(200, self._redraw)

    def _redraw(self):
        self._job = None
        if self.visible:
            self.on_show()

    def render(self):
        self.on_show()

    # ── the page ────────────────────────────────────────────────────────────
    def on_show(self, **where):
        body = self.scroller.body
        self.scroller.clear()
        s, p = self.s, self.s.project
        # header: title, author, play
        head = ttk.Frame(body)
        head.pack(fill='x', padx=px(28), pady=(px(14), px(2)))
        left = ttk.Frame(head)
        left.pack(side='left')
        ttk.Label(left, text=p.quest.get('title') or p.name, style='H1.TLabel').pack(anchor='w')
        by = p.quest.get('author')
        ttk.Label(left, text=(f'by {by}  ·  ' if by else '') + f'{s.levels} level{"s" if s.levels != 1 else ""}', style='Dim.TLabel').pack(anchor='w')
        right = ttk.Frame(head)
        right.pack(side='right')
        ui.button(right, 'Play from the start', lambda: self.app.play(from_start=True), 'play', 'Accent.TButton').pack(side='left')
        ui.button(right, 'Play level…', self._play_menu, 'play', 'TButton').pack(side='left', padx=px(8))
        self._health(body)
        self._next_steps(body)
        self._world(body)
        self._make(body)
        self._counts(body)
        self._recent(body)
        ttk.Frame(body, height=px(10)).pack()
        self.after(250, self._resized)                               # (once the window has its real size, the cards may fit more to a row)

    def _health(self, body):
        problems = [pr for pr in self.app.problems if pr.key not in set(self.app.settings.get('ignored', {}).get(self.s.project.root, []))]
        c = doctor.counts(problems)
        card = tk.Frame(body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'], cursor='hand2')
        card.pack(fill='x', padx=px(28), pady=(px(12), px(4)))
        if c['error'] or c['warn']:
            bits = ([f'{c["error"]} thing{"s" if c["error"] != 1 else ""} to fix'] if c['error'] else []) + \
                   ([f'{c["warn"]} probable mistake{"s" if c["warn"] != 1 else ""}'] if c['warn'] else [])
            colour, icon, text = (C['bad'] if c['error'] else C['warn']), 'warn', ', '.join(bits)
            sub = 'Open the Quest Doctor to see what and where.'
        else:
            colour, icon, text = C['ok'], 'check', 'The Quest Doctor finds nothing wrong'
            sub = f'{c["info"]} thing{"s" if c["info"] != 1 else ""} worth knowing.' if c['info'] else 'Every level, creature, item, shop and story checks out.'
        tk.Frame(card, bg=colour, width=5).pack(side='left', fill='y')
        tk.Label(card, image=icons.icon(icon, colour, px(30)), bg=C['raised']).pack(side='left', padx=px(14), pady=px(10))
        col = tk.Frame(card, bg=C['raised'])
        col.pack(side='left', pady=px(8))
        tk.Label(col, text=text, bg=C['raised'], fg=C['text'], font=(theme.FONT, 11, 'bold'), anchor='w').pack(fill='x')
        tk.Label(col, text=sub, bg=C['raised'], fg=C['dim'], anchor='w').pack(fill='x')
        for w in [card] + list(card.winfo_children()) + list(col.winfo_children()):
            w.bind('<Button-1>', lambda e: self.app.go('doctor'))

    def _next_steps(self, body):
        s, p = self.s, self.s.project
        steps = []
        for pr in self.app.problems:
            if pr.severity == 'error' and pr.go:
                steps.append(('warn', pr.title, 'Show me', lambda pr=pr: self.app.go(pr.go[0], **pr.go[1])))
                if len(steps) >= 2:
                    break
        if s.levels:
            last = s.levels
            empty = sum(1 for x in range(1, 101) for y in range(1, 101) if p.grid(last).sq[x][y][3] > 0) == 0
            if empty:
                steps.append(('wand', f'Level {last} has no creatures yet: let the wizard populate a new level, or paint some in', 'Level wizard',
                              lambda: self.app.go('world', wizard=True)))
        mons = [c for c in p.tables['creatures'] if c['id'] > 0]
        nopic = [c for c in mons if p.picture('creatures', c['id']) is None]
        if nopic:
            steps.append(('skull', f'{nopic[0].get("name") or "A creature"} has no picture yet', 'Paint it', lambda c=nopic[0]: self.app.go('creatures', select=c['id'])))
        if not steps and s.levels == 1 and not any(p.grid(1).sq[x][y][1] or p.grid(1).sq[x][y][3] for x in range(1, 101) for y in range(1, 101)):
            steps.append(('sparkle', 'A blank quest: let the wizard make a whole one, level after level, and look at every level before it exists',
                          'Quest wizard', lambda: self.app.go('world', quest=True)))
        if not steps:
            steps.append(('sparkle', 'Make a new level with the wizard: pick a place, the creatures and the treasure, and look at it before it exists', 'Level wizard',
                          lambda: self.app.go('world', wizard=True)))
            steps.append(('skull', 'Make a creature of your own: pick a kind, give it a name, and the Fight check says how it fares against your hero', 'New creature',
                          lambda: self.app.go('creatures', new=True)))
        ttk.Label(body, text='What to do next', style='H2.TLabel').pack(anchor='w', padx=px(28), pady=(px(14), px(4)))
        for icon, text, label, fn in steps[:3]:
            row = tk.Frame(body, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
            row.pack(fill='x', padx=px(28), pady=2)
            tk.Label(row, image=icons.icon(icon, C['accent'], px(22)), bg=C['raised']).pack(side='left', padx=px(12), pady=px(8))
            tk.Label(row, text=text, bg=C['raised'], fg=C['text'], anchor='w', justify='left', wraplength=px(820)).pack(side='left', fill='x', expand=True)
            ttk.Button(row, text=label, style='Accent.TButton' if icon == 'warn' else 'TButton', command=fn).pack(side='right', padx=px(12))

    def _world(self, body):
        s, p = self.s, self.s.project
        ttk.Label(body, text='The world', style='H2.TLabel').pack(anchor='w', padx=px(28), pady=(px(14), px(4)))
        wrap = tk.Frame(body, bg=C['panel'])
        wrap.pack(fill='x', padx=px(24))
        per = self._per = self.per_row()
        marks_by = {n: levelmeta.landmarks(s, n) for n in range(1, s.levels + 1)}
        pos = {}
        cells = []
        for n in range(1, s.levels + 1):
            r, cidx = divmod(n - 1, per)
            card = ui.Card(wrap, pad=8)
            card.grid(row=r, column=cidx, padx=px(5), pady=px(5))
            pos[n] = (r, cidx)
            if n not in self._thumbs:
                self._thumbs[n] = s.pictures.level_thumb(p.grid(n), px(120))
            tk.Label(card.inner, image=self._thumbs[n], bg=C['raised'], bd=0).pack()
            tk.Label(card.inner, text=levelmeta.title(s, n), bg=C['raised'], fg=C['text'], font=(theme.FONT, 10, 'bold')).pack(anchor='w', pady=(px(4), 0))
            m = marks_by[n]
            dests = []
            for x, y, item in m['exits']:
                link = (m['links_map'] or {}).get((x, y))
                dests.append(f'level {link[0]}' if link else (f'level {n + 1}' if n < s.levels else 'the end'))
            tk.Label(card.inner, text=('→ ' + ', '.join(dict.fromkeys(dests))) if dests else 'no exit', bg=C['raised'], fg=C['dim'], anchor='w',
                     font=(theme.FONT, 9)).pack(anchor='w')
            for w in [card] + list(card.inner.winfo_children()):
                w.bind('<Button-1>', lambda e, n=n: self.app.go('world', level=n))
                w.configure(cursor='hand2')
        add = ui.Card(wrap, pad=8)
        r, cidx = divmod(s.levels, per)
        add.grid(row=r, column=cidx, padx=px(5), pady=px(5), sticky='nsew')
        tk.Label(add.inner, image=icons.icon('plus', C['accent'], px(30)), bg=C['raised']).pack(pady=(px(20), px(4)))
        tk.Label(add.inner, text='New level', bg=C['raised'], fg=C['accent'], font=(theme.FONT, 10, 'bold')).pack()
        for w in [add] + list(add.inner.winfo_children()):
            w.bind('<Button-1>', lambda e: self.app.go('world', wizard=True))
            w.configure(cursor='hand2')

    def _make(self, body):
        ttk.Label(body, text='Make something', style='H2.TLabel').pack(anchor='w', padx=px(28), pady=(px(14), px(4)))
        row = ttk.Frame(body)
        row.pack(fill='x', padx=px(24))
        acts = (('sparkle', 'Quest wizard', 'A whole quest, level after level, in a few clicks', lambda: self.app.go('world', quest=True)),
                ('wand', 'Level wizard', 'A whole level, start to end, in a few clicks', lambda: self.app.go('world', wizard=True)),
                ('skull', 'New creature', 'A monster, a person or an ally', lambda: self.app.go('creatures', new=True)),
                ('sword', 'New item', 'A weapon, armour, a charm, food ...', lambda: self.app.go('items', new=True)),
                ('wand', 'New spell', 'Fire, frost, healing, summoning ...', lambda: self.app.go('spells', new=True)))
        for i, (icon, name, about, fn) in enumerate(acts):
            c = ui.Card(row, pad=px(14))
            c.grid(row=0, column=i, padx=px(4), sticky='nsew')
            row.columnconfigure(i, weight=1, uniform='a')
            ttk.Label(c.inner, image=icons.icon(icon, C['accent'], px(30)), style='Raised.TLabel').pack(anchor='w')
            ttk.Label(c.inner, text=name, style='H3.TLabel', background=C['raised']).pack(anchor='w', pady=(px(6), 0))
            ttk.Label(c.inner, text=about, style='Raised.Dim.TLabel', wraplength=px(200), justify='left').pack(anchor='w')
            for w in [c] + list(c.inner.winfo_children()):
                w.bind('<Button-1>', lambda e, f=fn: f())
                w.configure(cursor='hand2')

    def _counts(self, body):
        s, p = self.s, self.s.project
        cards = ttk.Frame(body)
        cards.pack(fill='x', padx=px(24), pady=(px(12), px(4)))
        monsters = [r for r in p.tables['creatures'] if r['id'] > 0]
        people = [r for r in p.tables['creatures'] if -100 < r['id'] < 0]
        items = [r for r in p.tables['items'] if r['id']]
        shops = sum(len(v) for v in p.shops.values())
        for i, (icon, n, text, page) in enumerate((('map', s.levels, 'levels', 'world'), ('skull', len(monsters), 'monsters', 'creatures'),
                                                   ('person', len(people), 'people', 'creatures'), ('sword', len(items), 'items', 'items'),
                                                   ('helmet', len(p.tables['classes']), 'heroes', 'heroes'),
                                                   ('wand', len(p.tables['spells']), 'spells', 'spells'), ('coin', shops, 'shops', 'shops'))):
            card = ui.Card(cards, pad=px(10))
            card.grid(row=0, column=i, padx=px(4), sticky='nsew')
            cards.columnconfigure(i, weight=1, uniform='c')
            ttk.Label(card.inner, image=icons.icon(icon, C['dim'], px(20)), style='Raised.TLabel').pack(anchor='w')
            ttk.Label(card.inner, text=str(n), style='Raised.TLabel', font=(theme.FONT, 18, 'bold')).pack(anchor='w')
            ttk.Label(card.inner, text=text, style='Raised.Dim.TLabel').pack(anchor='w')
            for w in [card] + list(card.inner.winfo_children()):
                w.bind('<Button-1>', lambda e, pg=page: self.app.go(pg))
                w.configure(cursor='hand2')

    def _recent(self, body):
        h = self.s.history
        if not h.undo_stack:
            return
        ttk.Label(body, text='Recent changes', style='H2.TLabel').pack(anchor='w', padx=px(28), pady=(px(20), px(6)))
        box = ui.Card(body, pad=10)
        box.pack(fill='x', padx=px(28))
        for e in reversed(h.undo_stack[-6:]):
            ttk.Label(box.inner, text='•  ' + e['label'], style='Raised.TLabel').pack(anchor='w')
        ui.button(box.inner, 'Undo the last one', lambda: self.app._undo(False), 'undo', 'Small.TButton').pack(anchor='w', pady=(px(8), 0))

    def _play_menu(self):
        m = tk.Menu(self, tearoff=False)
        for n in range(1, self.s.levels + 1):
            m.add_command(label=f'Level {n}  {levelmeta.title(self.s, n)}', command=lambda n=n: self.app.play(n))
        w = self.winfo_toplevel()
        m.tk_popup(w.winfo_pointerx(), w.winfo_pointery())

    def reload(self):
        self._thumbs.clear()
        self.on_show()

    def search(self, q):
        return []
