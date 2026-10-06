"""The Level panel of the World page: name, start, stories, leaving, teleporters, screens, 3D look, death and respawn."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from studio.art import EGA
from engine.formats import parse_story

from .. import levelmeta, theme, ui
from ..gallery import Entry, choose
from ..theme import C, px

RETURNS = [('exit', 'at the level exit'), ('clear', 'when every monster is dead'), ('script', 'when an event calls revive()')]


class LevelPanel(ttk.Frame):
    def __init__(self, master, host):
        super().__init__(master)
        self.host, self.s = host, host.s
        self.scroll = ui.Scrolled(self)
        self.scroll.pack(fill='both', expand=True)
        self.b = self.scroll.body
        self._loading = False
        self._build()

    # ── build ───────────────────────────────────────────────────────────────
    def _head(self, text, sub=''):
        f = ttk.Frame(self.b)
        f.pack(fill='x', padx=px(12), pady=(px(16), px(4)))
        ttk.Label(f, text=text, style='H3.TLabel').pack(anchor='w')
        if sub:
            ttk.Label(f, text=sub, style='Faint.TLabel', wraplength=px(280), justify='left').pack(anchor='w')

    def _row(self, label, tip=''):
        r = ttk.Frame(self.b)
        r.pack(fill='x', padx=px(12), pady=2)
        lab = ttk.Label(r, text=label)
        lab.pack(side='left')
        if tip:
            ui.tip(lab, tip)
        return r

    def _build(self):
        b = self.b
        self._head('This level')
        r = ttk.Frame(b)
        r.pack(fill='x', padx=px(12))
        self.name = tk.StringVar()
        e = self.name_entry = ttk.Entry(r, textvariable=self.name)
        e.pack(fill='x')
        e.bind('<Return>', lambda ev: self._rename())
        e.bind('<FocusOut>', lambda ev: self._rename())
        ui.tip(e, 'A name for this level, to find it by in lists and menus. The game does not show it.')
        self.stats = ttk.Label(b, text='', style='Dim.TLabel', wraplength=px(290), justify='left')
        self.stats.pack(anchor='w', padx=px(12), pady=(px(6), 0))

        self._head('Where the hero starts')
        r = ttk.Frame(b)
        r.pack(fill='x', padx=px(12))
        self.start = ttk.Label(r, text='')
        self.start.pack(side='left')
        ui.button(r, 'Move', lambda: self.host.choose_tool('start'), None, 'TButton',
                  'Pick the square on the map.').pack(side='right')
        ui.button(r, '', lambda: self.host.show_square(*levelmeta.start_of(self.s, self.host.level)), 'eye', 'Tool.TButton',
                  'Show it on the map').pack(side='right', padx=px(4))

        self._head('Stories before the level', 'Screens of text and picture the hero reads before this level begins.')
        self.stories = ttk.Frame(b)
        self.stories.pack(fill='x', padx=px(12))

        self._head('Leaving')
        r = self._row('Ask before leaving', 'Ask "Want to travel further?" when the hero steps on the exit.')
        self.ask = ui.Switch(r, True, lambda v: self._flag('ASK_TO_LEAVE', v, 'Change asking at the exit'))
        self.ask.pack(side='right')
        r = self._row('Play the jingle', 'Play the jingle as the hero leaves the level.')
        self.jingle = ui.Switch(r, True, lambda v: self._flag('LEAVE_JINGLE', v, 'Change the leaving jingle'))
        self.jingle.pack(side='right')

        self._head('Teleporter pads', 'How far a teleporter pad throws the hero, in squares across and down.')
        r = self._row('Across')
        self.tx = ui.Number(r, -99, 99, 0, commit=lambda v: self._teleport(), width=4)
        self.tx.pack(side='right')
        r = self._row('Down')
        self.ty = ui.Number(r, -99, 99, 0, commit=lambda v: self._teleport(), width=4)
        self.ty.pack(side='right')

        self._head('Screens', 'Each block is one screen of 10 by 10 squares. Click one to go there.')
        self.grid = tk.Canvas(b, width=px(190), height=px(190), highlightthickness=0, bg=C['panel'])
        self.grid.pack(anchor='w', padx=px(12), pady=(px(4), 0))
        self.grid.bind('<Button-1>', self._grid_click)
        self.legend = ttk.Label(b, text='● start   ● exit   ● shop   ◼ peaceful   ◼ dark', style='Faint.TLabel')
        self.legend.pack(anchor='w', padx=px(12), pady=(px(4), 0))

        self._head('How it looks in 3D mode', 'Sky and fog colours for first-person mode. Empty means the quest\'s own.')
        self.looks = {}
        for name, label in (('SKY_3D', 'Sky'), ('FOG_3D', 'Fog')):
            r = self._row(label)
            row = ttk.Frame(r)
            row.pack(side='right')
            self.looks[name] = ColourRow(row, self.s.pictures, lambda v, n=name: self._look(n, v))
            self.looks[name].pack()
        r = self._row('How far you see (squares)')
        self.range = ui.Number(r, 2, 30, 8, commit=lambda v: self._range(v), width=3, slider=False)
        self.range.pack(side='right')
        ttk.Button(r, text='Reset', style='Flat.TButton', command=lambda: self._reset_range()).pack(side='right', padx=px(6))

        self._head('Dying here')
        self.death = ttk.Label(b, text='', style='Dim.TLabel', wraplength=px(290), justify='left')
        self.death.pack(anchor='w', padx=px(12))
        ui.button(b, 'Death and respawn…', self._death, None, 'TButton').pack(anchor='w', padx=px(12), pady=(px(6), px(24)))

    def _flag(self, name, on, label):
        """A setting that is on unless the script says False: on removes the line."""
        if not self._loading:
            levelmeta.put(self.s, self.host.level, name, None if on else False, label)

    # ── values ──────────────────────────────────────────────────────────────
    def refresh(self):
        if not self.winfo_exists():
            return
        s, n = self.s, self.host.level
        self._loading = True
        try:
            t = levelmeta.get(s, n, 'TITLE')
            if self.focus_get() is not self.name_entry:
                self.name.set(t if isinstance(t, str) else '')
            sx, sy = levelmeta.start_of(s, n)
            self.start.configure(text=f'Square ({sx}, {sy})')
            ui.tip(self.start, f'On screen {levelmeta.screen_of(sx, sy)}.')
            self.ask.set(levelmeta.get(s, n, 'ASK_TO_LEAVE', True) is not False)
            self.jingle.set(levelmeta.get(s, n, 'LEAVE_JINGLE', True) is not False)
            tp = levelmeta.get(s, n, 'TELEPORT', (0, 0)) or (0, 0)
            self.tx.set(tp[0])
            self.ty.set(tp[1])
            for name, w in self.looks.items():
                w.set(levelmeta.get(s, n, name))
            self.range.set(levelmeta.get(s, n, 'RANGE_3D') or self.default_range())
            self._stories()
            self._screens()
            self._death_text()
            self._stats()
        finally:
            self._loading = False

    def default_range(self):
        return int((self.s.project.quest.get('view3d') or {}).get('range', 8))

    def _stats(self):
        c = self.host.counts(self.host.level)
        bits = [f'{c["mon"]} creature{"s" if c["mon"] != 1 else ""}', f'{c["item"]} item{"s" if c["item"] != 1 else ""}',
                f'{c["gold"]} heap{"s" if c["gold"] != 1 else ""} of gold']
        self.stats.configure(text=' · '.join(bits))

    def _rename(self):
        if self._loading:
            return
        text = self.name.get().strip()
        levelmeta.put(self.s, self.host.level, 'TITLE', text or None, 'Rename the level')
        self.host.titles_changed()

    def _teleport(self):
        if self._loading:
            return
        v = (self.tx.get(), self.ty.get())
        levelmeta.put(self.s, self.host.level, 'TELEPORT', None if v == (0, 0) else v, 'Change the teleporter jump')

    def _look(self, name, v):
        if not self._loading:
            levelmeta.put(self.s, self.host.level, name, v, 'Change the 3D look')

    def _range(self, v):
        if not self._loading:
            levelmeta.put(self.s, self.host.level, 'RANGE_3D', v if v != self.default_range() else None, 'Change the 3D range')

    def _reset_range(self):
        levelmeta.put(self.s, self.host.level, 'RANGE_3D', None, 'Reset the 3D range')
        self.refresh()

    # ── stories ─────────────────────────────────────────────────────────────
    def _stories(self):
        for w in self.stories.winfo_children():
            w.destroy()
        s, n = self.s, self.host.level
        have = list(levelmeta.get(s, n, 'STORIES', []) or [])
        texts = parse_story(s.project.texts['stories'])
        for i, k in enumerate(have):
            row = tk.Frame(self.stories, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
            row.pack(fill='x', pady=2)
            first = (texts.get(k) or 'no such story yet').strip().split('\n')[0][:44]
            tk.Label(row, text=f'Story {k}', bg=C['raised'], fg=C['accent'], font=(theme.FONT, 9, 'bold')).pack(side='left', padx=px(8), pady=px(6))
            tk.Label(row, text=first, bg=C['raised'], fg=C['dim'], anchor='w', font=(theme.FONT, 9)).pack(side='left', fill='x', expand=True)
            ui.button(row, '', lambda i=i: self._drop_story(i), 'close', 'Tool.TButton', 'Take it away').pack(side='right')
        ui.button(self.stories, 'Add a story…', self._add_story, 'plus', 'TButton').pack(anchor='w', pady=(px(4), 0))

    def _add_story(self):
        s, n = self.s, self.host.level
        texts = parse_story(s.project.texts['stories'])
        entries = [Entry(k, f'Story {k}', v.strip().split('\n')[0][:60]) for k, v in sorted(texts.items())]
        if not entries:
            ui.inform(self.host.page, 'No stories yet', 'This quest has no story screens yet. Write one on the Story page.')
            self.host.app.go('story')
            return
        got = choose(self.host.page, 'Which story is shown before this level?', entries, ok='Add')
        if got is False or got is None:
            return
        have = list(levelmeta.get(s, n, 'STORIES', []) or [])
        if got not in have:
            levelmeta.put(s, n, 'STORIES', have + [got], 'Add a story to a level')

    def _drop_story(self, i):
        s, n = self.s, self.host.level
        have = list(levelmeta.get(s, n, 'STORIES', []) or [])
        del have[i]
        levelmeta.put(s, n, 'STORIES', have, 'Take a story from a level')

    # ── screens ─────────────────────────────────────────────────────────────
    def _screens(self):
        g, k = self.grid, px(19)
        g.delete('all')
        marks = levelmeta.landmarks(self.s, self.host.level)
        for sx in range(1, 11):
            for sy in range(1, 11):
                x0, y0 = (sx - 1) * k, (sy - 1) * k
                col = C['raised']
                if (sx, sy) in marks['dark']:
                    col = '#2a2a6a'
                g.create_rectangle(x0 + 1, y0 + 1, x0 + k - 1, y0 + k - 1, fill=col, outline=C['line'])
                if (sx, sy) in marks['peaceful']:
                    g.create_rectangle(x0 + 3, y0 + 3, x0 + k - 3, y0 + k - 3, outline=C['info'], width=2)
        for (sx, sy), kk in marks['shops'].items():
            g.create_text((sx - 1) * k + k // 2, (sy - 1) * k + k // 2, text=str(kk), fill=C['info'], font=(theme.FONT, 9, 'bold'))
        for x, y, item in marks['exits']:
            sx, sy = levelmeta.screen_of(x, y)
            g.create_oval((sx - 1) * k + k - 9, (sy - 1) * k + 3, (sx - 1) * k + k - 3, (sy - 1) * k + 9, fill=C['bad'], outline='')
        sx, sy = levelmeta.screen_of(*marks['start'])
        g.create_oval((sx - 1) * k + 3, (sy - 1) * k + 3, (sx - 1) * k + 10, (sy - 1) * k + 10, fill=C['accent'], outline='')
        vx, vy = self.host.map.visible_screens()
        g.create_rectangle((vx - 1) * k, (vy - 1) * k, vx * k, vy * k, outline=C['text'], width=2)

    def _grid_click(self, e):
        k = px(19)
        sx, sy = max(1, min(10, e.x // k + 1)), max(1, min(10, e.y // k + 1))
        self.host.show_screen(sx, sy)

    def view_moved(self):
        if self.winfo_ismapped():
            self._screens()

    # ── death ───────────────────────────────────────────────────────────────
    def _death_text(self):
        s, n = self.s, self.host.level
        bits = []
        if levelmeta.get(s, n, 'RESPAWN'):
            bits.append('He wakes again on this level after dying here.')
        if levelmeta.get(s, n, 'UNDERWORLD'):
            bits.append('This level is the Underworld.')
        self.death.configure(text=' '.join(bits) or 'Dying here is the real death (or the Underworld, if the quest has one).')

    def _death(self):
        DeathDialog(self.host.page, self.s, self.host.level).run()
        self.host.changed_places()


class ColourRow(ttk.Frame):
    """The 16 EGA colours to choose from; click the chosen one again for none."""

    def __init__(self, master, pictures, command):
        super().__init__(master)
        self.pictures, self.command, self.value = pictures, command, None
        self.labels = []
        for i in range(16):
            lab = tk.Label(self, image=pictures.colour_chip(i, px(12)), bd=0, highlightthickness=2, highlightbackground=C['panel'],
                           cursor='hand2')
            lab.grid(row=i // 8, column=i % 8, padx=1, pady=1)
            lab.bind('<Button-1>', lambda e, i=i: self._click(i))
            self.labels.append(lab)

    def set(self, v):
        self.value = v
        for i, lab in enumerate(self.labels):
            lab.configure(highlightbackground=C['accent'] if v == i else C['panel'])

    def _click(self, i):
        self.set(None if self.value == i else i)
        self.command(self.value)


class DeathDialog(ui.Dialog):
    """What happens on a level when the hero dies: waking again on it, and being the Underworld the dead wake in."""

    def __init__(self, parent, session, level):
        super().__init__(parent, f'Dying on level {level}', width=px(560))
        self.s, self.n = session, level
        g = lambda name, d=None: levelmeta.get(session, level, name, d)
        b = self.body
        ttk.Label(b, text='Wake again on this level', style='H3.TLabel').pack(anchor='w')
        ttk.Label(b, text='The hero wakes at the wake spot (or the start), his body left where he fell. Without this, dying here '
                          'sends him to the Underworld, if the quest has one, or ends the game.', style='Dim.TLabel',
                  wraplength=px(500), justify='left').pack(anchor='w', pady=(0, px(6)))
        self.respawn = self._switch(b, 'He wakes again here after dying', bool(g('RESPAWN')))
        self.life = self._number(b, 'Life when he wakes (percent)', g('RESPAWN_LIFE'), 50)
        self.lost = self._number(b, 'Gold lost each time (percent)', g('RESPAWN_GOLD_LOSS'), 0)
        self.limit = self._number(b, 'Times he may wake here (0 = always)', g('RESPAWN_LIMIT'), 0, hi=99)
        self.kit = self._kit(b, 'He wakes with', g('RESPAWN_KIT', []) or [])
        ui.hsep(b).pack(fill='x', pady=px(12))
        ttk.Label(b, text='This level is the Underworld', style='H3.TLabel').pack(anchor='w')
        ttk.Label(b, text='When the hero dies on another level he wakes here, and fights his way back to his body.',
                  style='Dim.TLabel', wraplength=px(500), justify='left').pack(anchor='w', pady=(0, px(6)))
        self.under = self._switch(b, 'The dead wake on this level', bool(g('UNDERWORLD', False)))
        r = ttk.Frame(b)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text='He gets back').pack(side='left')
        self.way = ttk.Combobox(r, state='readonly', width=28, values=[t for _, t in RETURNS])
        self.way.set(dict(RETURNS).get(g('UNDERWORLD_RETURN', 'exit'), RETURNS[0][1]))
        self.way.pack(side='right')
        self.uw_life = self._number(b, 'Life when he wakes here (percent)', g('UNDERWORLD_LIFE'), 50)
        self.back = self._number(b, 'Life he has on returning (percent, at least)', g('REVIVE_LIFE'), 50)
        self.uw_kit = self._kit(b, 'He wakes with', g('UNDERWORLD_KIT', []) or [])
        self.strip = self._switch(b, 'The Underworld takes his things until he returns', bool(g('UNDERWORLD_STRIP', False)))
        self.add_buttons([('Cancel', None, 'TButton'), ('Done', 'ok', 'Accent.TButton')], default='ok')

    def _switch(self, parent, text, value):
        r = ttk.Frame(parent)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text=text).pack(side='left')
        sw = ui.Switch(r, value)
        sw.pack(side='right')
        return sw

    def _number(self, parent, text, value, default, hi=100):
        r = ttk.Frame(parent)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text=text).pack(side='left')
        num = ui.Number(r, 0, hi, default if value is None else value, width=4, slider=False)
        num.pack(side='right')
        num.was_none = value is None
        num.default = default
        return num

    def _kit(self, parent, text, kit):
        r = ttk.Frame(parent)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text=text).pack(side='left')
        holder = ttk.Frame(r)
        holder.pack(side='right')
        box = {'items': list(kit)}
        lab = ttk.Label(holder, text='', style='Dim.TLabel', wraplength=px(260), justify='right')
        lab.pack(side='left', padx=px(8))

        def draw():
            names = [self.s.name_of('items', v) for v in box['items']]
            lab.configure(text=', '.join(names) or 'nothing')

        def add():
            from ..gallery import Entry
            entries = [Entry(r_['id'], r_.get('name') or f'#{r_["id"]}', r_.get('type', ''),
                             self.s.pictures.thumb('item', r_['id'], 32)) for r_ in self.s.project.entries('item')]
            got = choose(self, 'An item he starts with', entries, ok='Add')
            if got not in (False, None):
                box['items'].append(got)
                draw()

        def clear():
            box['items'].clear()
            draw()
        ttk.Button(holder, text='Add…', style='Flat.TButton', command=add).pack(side='left')
        ttk.Button(holder, text='Clear', style='Flat.TButton', command=clear).pack(side='left')
        draw()
        return box

    def close(self, value):
        if value == 'ok':
            s, n, p = self.s, self.n, self.s.project
            with s.edit('Change death and respawn', ('script', n)):
                def put(name, v, default=None):
                    levelmeta.raw_put(p, n, name, None if v in (None, default, [], False) else v)
                put('RESPAWN_LIFE', self.life.get(), 50 if self.life.was_none else None)
                put('RESPAWN_GOLD_LOSS', self.lost.get(), 0)
                put('RESPAWN_LIMIT', self.limit.get(), 0)
                put('RESPAWN_KIT', list(self.kit['items']))
                put('UNDERWORLD_LIFE', self.uw_life.get(), 50 if self.uw_life.was_none else None)
                put('REVIVE_LIFE', self.back.get(), 50 if self.back.was_none else None)
                put('UNDERWORLD_KIT', list(self.uw_kit['items']))
                if self.respawn.get():
                    if not levelmeta.get(s, n, 'RESPAWN'):
                        levelmeta.raw_put(p, n, 'RESPAWN', tuple(levelmeta.start_of(s, n)))
                else:
                    levelmeta.raw_put(p, n, 'RESPAWN', None)
                put('UNDERWORLD', True if self.under.get() else None)
                put('UNDERWORLD_STRIP', True if self.strip.get() else None)
                way = next((k for k, label in RETURNS if label == self.way.get()), 'exit')
                put('UNDERWORLD_RETURN', way, 'exit')
        super().close(value)
