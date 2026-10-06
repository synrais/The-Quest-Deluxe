"""The Places panel: start, exits, stairs, entries, shops and the wake spot of a level, and the windows that set where they lead."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core.project import SIZE

from .. import icons, levelmeta, theme, ui
from ..theme import C, px

TOOLS = [('start', 'Start', 'flag', 'Where the hero arrives on this level.'),
         ('exit', 'Exit', 'door', 'A way out: to the next level, or to any level and place you choose.'),
         ('link', 'Stairs', 'link', 'A ladder, rope, stairs, hole or jump pad to somewhere else.'),
         ('entry', 'Entry', 'star', 'A named way in, so other levels can lead here.'),
         ('respawn', 'Wake spot', 'heart', 'Where the hero wakes after dying on this level.')]
SCREEN_TOOLS = [('peaceful', 'Peaceful', 'shield', 'Screens where people and allies do not attack monsters.'),
                ('dark', 'Dark', 'moon', 'Screens where only the hero and his light show.'),
                ('shop', 'Shop', 'coin', 'Screens that hold a shop.')]
HOW = {'start': 'Click the square where the hero should arrive.',
       'exit': 'Click a square for an exit. Then say where it leads.',
       'link': 'Click a square for the ladder, stairs, rope, hole or pad. Then say where it leads.',
       'entry': 'Click a square to name it as a way in. Click a named one again to rename or remove it.',
       'respawn': 'Click the square where the hero wakes after dying here. Click it again to take it away.',
       'peaceful': 'Click a screen to make it peaceful, again to undo.',
       'dark': 'Click a screen to make it dark, again to undo.',
       'shop': 'Click a screen to give it a shop, or change which shop it has.'}
LINK_KINDS = [('stairs', 'Stairs'), ('ladder', 'Ladder'), ('rope', 'Rope'), ('hole', 'Hole'), ('jump_pad', 'Jump pad')]
ICON_OF = {'exit': 'door', 'ladder': 'link', 'rope': 'link', 'stairs': 'link', 'hole': 'link', 'jump_pad': 'link',
           'teleporter': 'sparkle'}


def pretty(kind):
    return {'exit': 'Exit', 'jump_pad': 'Jump pad', 'teleporter': 'Teleporter'}.get(kind, kind.title())


class PlacesPanel(ttk.Frame):
    def __init__(self, master, host):
        super().__init__(master)
        self.host, self.s = host, host.s
        self.kind = tk.StringVar(value='Stairs')
        self.scroll = ui.Scrolled(self)
        self.scroll.pack(fill='both', expand=True)
        self.body = self.scroll.body
        self.buttons = {}
        self._job = None
        self._build()

    # ── build ───────────────────────────────────────────────────────────────
    def _build(self):
        b = self.body
        pad = dict(padx=px(12))
        ttk.Label(b, text='Put on the map', style='H3.TLabel').pack(anchor='w', pady=(px(12), px(6)), **pad)
        grid = ttk.Frame(b)
        grid.pack(fill='x', **pad)
        for i, (key, text, icon, about) in enumerate(TOOLS):
            btn = ttk.Button(grid, text=text, style='Small.TButton', compound='left', command=lambda k=key: self.host.choose_tool(k))
            ui.tip(btn, about)
            btn.grid(row=i // 2, column=i % 2, sticky='ew', padx=2, pady=2)
            self.buttons[key] = (btn, icon)
        for c in range(2):
            grid.columnconfigure(c, weight=1)
        kind_row = ttk.Frame(b)
        kind_row.pack(fill='x', pady=(px(6), 0), **pad)
        ttk.Label(kind_row, text='Stairs are a', style='Dim.TLabel').pack(side='left')
        self.kind_box = ttk.Combobox(kind_row, state='readonly', width=10, values=[t for _, t in LINK_KINDS],
                                     textvariable=self.kind)
        self.kind_box.pack(side='left', padx=px(8))
        ttk.Label(b, text='Whole screens', style='H3.TLabel').pack(anchor='w', pady=(px(12), px(6)), **pad)
        sg = ttk.Frame(b)
        sg.pack(fill='x', **pad)
        for i, (key, text, icon, about) in enumerate(SCREEN_TOOLS):
            btn = ttk.Button(sg, text=text, style='Small.TButton', compound='left', command=lambda k=key: self.host.choose_tool(k))
            ui.tip(btn, about)
            btn.grid(row=0, column=i, sticky='ew', padx=2, pady=2)
            self.buttons[key] = (btn, icon)
            sg.columnconfigure(i, weight=1)
        self.how = ttk.Label(b, text='', style='Accent.TLabel', wraplength=px(280), justify='left')
        self.how.pack(anchor='w', pady=(px(8), 0), **pad)
        self.list = ttk.Frame(b)
        self.list.pack(fill='x', pady=(px(6), px(20)))
        self.paint_tools()
        self.refresh()

    def paint_tools(self):
        tool = self.host.map.tool
        for key, (btn, icon) in self.buttons.items():
            on = key == tool
            btn.configure(style='Accent.TButton' if on else 'Small.TButton',
                          image=icons.icon(icon, C['accent_text'] if on else C['text'], px(16)))
        self.how.configure(text=HOW.get(tool, ''))

    # ── lists ───────────────────────────────────────────────────────────────
    def schedule(self):
        if self._job is None:
            self._job = self.after(120, self.refresh)

    def refresh(self):
        self._job = None
        if not self.winfo_exists():
            return
        for w in self.list.winfo_children():
            w.destroy()
        n = self.host.level
        marks = levelmeta.landmarks(self.s, n)
        pad = dict(padx=px(12))
        ttk.Label(self.list, text='On this level', style='H3.TLabel').pack(anchor='w', pady=(px(10), px(4)), **pad)
        sx, sy = marks['start']
        self._row('flag', C['accent'], 'Start', f'where the hero arrives: ({sx}, {sy})', go=(sx, sy),
                  edit=lambda: self.host.choose_tool('start'))
        if not marks['exits'] and not marks['links']:
            self._note('No way out yet. Put an Exit on the map, so the hero can finish the level.')
        for x, y, item in marks['exits']:
            self._row('door', C['bad'], f'Exit at ({x}, {y})', levelmeta.describe_destination(self.s, n, x, y, 'exit'),
                      go=(x, y), edit=lambda x=x, y=y: self.edit_link(x, y))
        for x, y, item in marks['links']:
            kind = self.s.project.item_type(item)
            self._row('link', C['warn'], f'{pretty(kind)} at ({x}, {y})',
                      levelmeta.describe_destination(self.s, n, x, y, kind), go=(x, y),
                      edit=lambda x=x, y=y: self.edit_link(x, y))
        for x, y, item in marks['teleporters']:
            self._row('sparkle', C['info'], f'Teleporter at ({x}, {y})', 'moves the hero (Level tab: how far)', go=(x, y))
        for name, (x, y) in sorted(marks['entries'].items()):
            users = self.users_of_entry(n, name)
            self._row('star', C['ok'], f'Entry "{name}"', f'({x}, {y})' + (f' · used by {users}' if users else ' · nothing leads here yet'),
                      go=(x, y), edit=lambda x=x, y=y: self.host.on_marker('entry', x, y))
        if marks['respawn']:
            x, y = marks['respawn']
            self._row('heart', '#e65aa0', 'Wake spot', f'({x}, {y})', go=(x, y), edit=lambda: self.host.choose_tool('respawn'))
        for (sx, sy), k in sorted(marks['shops'].items()):
            self._row('coin', C['info'], f'Shop {k} on screen ({sx}, {sy})', 'its wares are on the Shops page',
                      go=((sx - 1) * 10 + 5, (sy - 1) * 10 + 5), edit=lambda k=k: self.host.app.go('shops', level=n, shop=k))
        for label, key, colour, icon in (('Peaceful', 'peaceful', C['info'], 'shield'), ('Dark', 'dark', C['info'], 'moon')):
            for sx, sy in marks[key]:
                self._row(icon, colour, f'{label} screen ({sx}, {sy})', '', go=((sx - 1) * 10 + 5, (sy - 1) * 10 + 5))

    def users_of_entry(self, n, name):
        used = []
        for lv in range(1, self.s.levels + 1):
            for sq, link in (levelmeta.get(self.s, lv, 'LINKS', {}) or {}).items():
                if link and link[0] == n and len(link) == 2 and link[1] == name:
                    used.append(f'level {lv}')
        return ', '.join(dict.fromkeys(used))

    def _note(self, text):
        ttk.Label(self.list, text=text, style='Warn.TLabel', wraplength=px(280), justify='left').pack(anchor='w', padx=px(12), pady=px(4))

    def _row(self, icon, colour, title, sub, go=None, edit=None):
        row = tk.Frame(self.list, bg=C['raised'], highlightthickness=1, highlightbackground=C['line'])
        row.pack(fill='x', padx=px(10), pady=2)
        tk.Label(row, image=icons.icon(icon, colour, px(18)), bg=C['raised']).pack(side='left', padx=px(8), pady=px(6))
        col = tk.Frame(row, bg=C['raised'])
        col.pack(side='left', fill='x', expand=True)
        tk.Label(col, text=title, bg=C['raised'], fg=C['text'], anchor='w', font=(theme.FONT, 10, 'bold')).pack(fill='x')
        if sub:
            tk.Label(col, text=sub, bg=C['raised'], fg=C['dim'], anchor='w', font=(theme.FONT, 9), wraplength=px(170),
                     justify='left').pack(fill='x')
        if edit:
            e = ttk.Button(row, text='Edit', style='Flat.TButton', command=edit, width=5)
            e.pack(side='right', padx=(0, px(4)))
        if go:
            g = ui.button(row, '', lambda: self.host.show_square(*go), 'eye', 'Tool.TButton', 'Show it on the map')
            g.pack(side='right', padx=px(2))

    # ── the map tools ───────────────────────────────────────────────────────
    def handle(self, tool, x, y):
        s, n = self.s, self.host.level
        if tool == 'start':
            levelmeta.put(s, n, 'START', (x, y), 'Move the start')
            self.host.say(f'The hero now starts at ({x}, {y}).')
        elif tool == 'respawn':
            cur = levelmeta.get(s, n, 'RESPAWN')
            if cur and tuple(cur) == (x, y):
                levelmeta.put(s, n, 'RESPAWN', None, 'Take away the wake spot')
                self.host.say('Wake spot taken away.')
            else:
                levelmeta.put(s, n, 'RESPAWN', (x, y), 'Move the wake spot')
                self.host.say(f'He wakes at ({x}, {y}) after dying here.')
        elif tool in ('peaceful', 'dark'):
            sc = levelmeta.screen_of(x, y)
            name, label = ('PEACEFUL_SCREENS', 'peaceful') if tool == 'peaceful' else ('DARK_SCREENS', 'dark')
            on = levelmeta.toggle_screen(s, n, name, sc, f'Make a screen {label}' )
            self.host.say(f'Screen {sc[0]}, {sc[1]} is {"now" if on else "no longer"} {label}.')
        elif tool == 'shop':
            self.shop_here(x, y)
        elif tool == 'entry':
            self.entry_here(x, y)
        elif tool in ('exit', 'link'):
            self.link_here(tool, x, y)
        self.refresh()
        self.host.map.refresh()
        self.host.changed_places()

    def entry_here(self, x, y):
        s, n = self.s, self.host.level
        entries = dict(levelmeta.get(s, n, 'ENTRIES', {}) or {})
        here = next((k for k, v in entries.items() if tuple(v) == (x, y)), None)
        free = next(f'entry {i}' for i in range(1, 1000) if f'entry {i}' not in entries)
        name = ui.ask_text(self.host.page, 'A way in', f'Name of the way in at ({x}, {y}) on level {n}.\n'
                           'Other levels link to it by this name.   (Leave it empty to take the entry away.)', here or free)
        if name is None:
            return
        if here:
            entries.pop(here)
        if name:
            entries[name] = (x, y)
        levelmeta.put(s, n, 'ENTRIES', entries, 'Name a way in')
        if here and name and here != name:
            self.rename_entry_users(n, here, name)

    def rename_entry_users(self, n, old, new):
        s = self.s
        for lv in range(1, s.levels + 1):
            links = dict(levelmeta.get(s, lv, 'LINKS', {}) or {})
            hit = {k: (v[0], new) for k, v in links.items() if v and v[0] == n and len(v) == 2 and v[1] == old}
            if hit:
                links.update(hit)
                levelmeta.put(s, lv, 'LINKS', links, 'Rename an entry')

    def shop_here(self, x, y):
        s, n = self.s, self.host.level
        sc = levelmeta.screen_of(x, y)
        shops = dict(levelmeta.get(s, n, 'SHOPS', {}) or {})
        cur = shops.get(sc, 0)
        k = ui.ask_text(self.host.page, 'A shop', f'Which shop does screen ({sc[0]}, {sc[1]}) have?\n'
                        f'(Its wares are level {n}, shop number k.  0 means no shop here.)', str(cur or 1))
        if k is None:
            return
        try:
            k = max(0, min(9, int(k)))
        except ValueError:
            self.host.say('A shop number is 0 to 9.', 'warn')
            return
        with s.edit('Change a shop', ('script', n), ('shops', n)):
            if k:
                shops[sc] = k
                if k not in s.project.shops.setdefault(n, {}):
                    s.project.shops[n][k] = '1 3\n'
            else:
                shops.pop(sc, None)
            levelmeta.raw_put(s.project, n, 'SHOPS', shops)
        self.host.say(f'Screen ({sc[0]}, {sc[1]}) has shop {k}.' if k else 'No shop on that screen now.')

    def link_here(self, tool, x, y):
        s, n = self.s, self.host.level
        cell = s.project.grid(n).sq[x][y]
        kind_now = s.project.item_type(cell[2])
        if tool == 'exit':
            kind = 'exit'
        elif kind_now in levelmeta.LINK_TYPES:
            kind = kind_now
        else:
            kind = {t: k for k, t in LINK_KINDS}[self.kind.get()]
        item = None
        if kind_now != kind and not (tool == 'link' and kind_now in levelmeta.LINK_TYPES):
            item = levelmeta.exit_item(s) if kind == 'exit' else levelmeta.link_item(s, kind)
            if item is None:
                ui.inform(self.host.page, 'No such item', f'This quest has no item of the type "{kind}" yet. '
                          'Make one on the Items page (its Type), then put it here.')
                return
        edit_link(self.host, x, y, kind, item)

    def edit_link(self, x, y):
        kind = self.s.project.item_type(self.s.project.grid(self.host.level).sq[x][y][2])
        edit_link(self.host, x, y, kind or 'exit', None)


def edit_link(host, x, y, kind, item):
    """Ask where the exit or stairs at (x, y) leads, and make it so."""
    s, n = host.s, host.level
    dlg = LinkEditor(host.page, s, n, x, y, kind)
    result = dlg.run()
    if result is None:
        return False
    if result == 'remove':
        levelmeta.apply_link(s, n, x, y, item, None, kind)
        host.say('That one leads nowhere special now.' if kind != 'exit' else 'It goes on to the next level again.')
    else:
        spec, back = result
        levelmeta.apply_link(s, n, x, y, item, spec, kind, back)
        host.say(f'Leads to {levelmeta.describe_destination(s, n, x, y, kind)}.')
    host.changed_places(map_too=item is not None)
    return True


class LinkEditor(ui.Dialog):
    """Where an exit, ladder, stairs, rope, hole or pad leads: a level, and the start of it, a named entry or an exact square."""

    def __init__(self, parent, session, level, x, y, kind):
        super().__init__(parent, 'Where does it lead?', width=px(520))
        self.s, self.level, self.x, self.y, self.kind = session, level, x, y, kind
        self.exit = kind == 'exit'
        cur = levelmeta.link_spec(session, level, x, y)
        what = {'exit': 'This exit', 'jump_pad': 'This jump pad'}.get(kind, f'This {kind}')
        ttk.Label(self.body, text=f'{what}, at ({x}, {y}) on level {level}', style='H2.TLabel').pack(anchor='w')
        ttk.Label(self.body, text='It leads to…', style='Dim.TLabel').pack(anchor='w', pady=(px(10), px(2)))
        self.levels = [f'{k}   {levelmeta.title(session, k)}' for k in range(1, session.levels + 1)]
        self.target = ttk.Combobox(self.body, state='readonly', values=(['The next level (or the ending)'] if self.exit else []) + self.levels,
                                   width=40)
        self.target.pack(anchor='w')
        self.target.set(self.levels[cur['level'] - 1] if cur and 1 <= cur['level'] <= len(self.levels) else
                        ('The next level (or the ending)' if self.exit else self.levels[min(level, len(self.levels)) - 1]))
        self.target.bind('<<ComboboxSelected>>', lambda e: self._changed())
        self.box = ttk.Frame(self.body)
        self.box.pack(fill='x', pady=(px(10), 0))
        self.mode = tk.StringVar(value=cur['mode'] if cur else 'start')
        self.entry_var = tk.StringVar(value=cur['entry'] if cur else '')
        self.x_var = tk.StringVar(value=str(cur['x'] if cur and cur['mode'] == 'square' else 5))
        self.y_var = tk.StringVar(value=str(cur['y'] if cur and cur['mode'] == 'square' else 5))
        self.text_var = tk.StringVar(value=cur['text'] if cur else '')
        self.back_var = tk.BooleanVar(value=not cur and not self.exit and kind not in ('hole', 'jump_pad'))
        self._build_modes()
        self.has_link = bool(cur)
        buttons = [('Cancel', None, 'TButton'), ('Done', 'ok', 'Accent.TButton')]
        if cur:
            buttons.insert(0, ('Take the link away', 'remove', 'Danger.TButton'))
        self.add_buttons(buttons, default='ok')
        self._changed()

    def _build_modes(self):
        b = self.box
        ttk.Label(b, text='…and arrives', style='Dim.TLabel').pack(anchor='w', pady=(0, px(2)))
        self.r_start = ttk.Radiobutton(b, text='at the start of that level (its story screens come first)', value='start',
                                       variable=self.mode, command=self._changed)
        self.r_start.pack(anchor='w')
        row = ttk.Frame(b)
        row.pack(anchor='w', fill='x', pady=2)
        self.r_entry = ttk.Radiobutton(row, text='at a named entry', value='entry', variable=self.mode, command=self._changed)
        self.r_entry.pack(side='left')
        self.entry_box = ttk.Combobox(row, textvariable=self.entry_var, state='readonly', width=20)
        self.entry_box.pack(side='left', padx=px(8))
        row = ttk.Frame(b)
        row.pack(anchor='w', fill='x', pady=2)
        self.r_square = ttk.Radiobutton(row, text='on the square', value='square', variable=self.mode, command=self._changed)
        self.r_square.pack(side='left')
        ttk.Label(row, text='x').pack(side='left', padx=(px(8), 2))
        self.x_box = ttk.Entry(row, textvariable=self.x_var, width=5)
        self.x_box.pack(side='left')
        ttk.Label(row, text='y').pack(side='left', padx=(px(8), 2))
        self.y_box = ttk.Entry(row, textvariable=self.y_var, width=5)
        self.y_box.pack(side='left')
        self.pick_btn = ttk.Button(row, text='Pick on the map…', command=self._pick)
        self.pick_btn.pack(side='left', padx=px(10))
        self.words_row = ttk.Frame(b)
        self.words_row.pack(anchor='w', fill='x', pady=(px(8), 0))
        ttk.Label(self.words_row, text='Words shown when taken').pack(side='left')
        self.words = ttk.Entry(self.words_row, textvariable=self.text_var, width=30)
        self.words.pack(side='left', padx=px(8))
        ui.tip(self.words, 'Shown at the bottom of the screen when the hero takes it. Empty: the usual words ("You climb the ladder.").')
        self.back_check = ttk.Checkbutton(b, text='Also make the way back (the same item at the other end, leading back here)',
                                          variable=self.back_var)
        self.back_check.pack(anchor='w', pady=(px(10), 0))
        self.note = ttk.Label(b, text='', style='Dim.TLabel', wraplength=px(480), justify='left')
        self.note.pack(anchor='w', pady=(px(8), 0))

    def _target_level(self):
        v = self.target.get()
        if not v[:1].isdigit():
            return None
        return int(v.split()[0])

    def _changed(self):
        lv = self._target_level()
        default = lv is None
        entries = sorted((levelmeta.get(self.s, lv, 'ENTRIES', {}) or {}).keys()) if lv else []
        self.entry_box.configure(values=entries)
        if entries and self.entry_var.get() not in entries:
            self.entry_var.set(entries[0])
        if not entries:
            self.entry_var.set('')
            if self.mode.get() == 'entry':
                self.mode.set('start')
        for w, on in ((self.r_start, not default), (self.r_entry, bool(entries)), (self.r_square, not default),
                      (self.entry_box, bool(entries) and self.mode.get() == 'entry'),
                      (self.x_box, not default and self.mode.get() == 'square'),
                      (self.y_box, not default and self.mode.get() == 'square'),
                      (self.pick_btn, not default and self.mode.get() == 'square'),
                      (self.words, not default and self.mode.get() == 'square'),
                      (self.back_check, not default and not self.exit and self.kind not in ('hole', 'jump_pad'))):
            try:
                w.state(['!disabled'] if on else ['disabled'])
            except (AttributeError, tk.TclError):
                w.configure(state='normal' if on else 'disabled')
        if default:
            self.note.configure(text='With nothing chosen the exit does what it does in the original game: on to the next level, '
                                     'and after the last one, the ending.')
        elif not entries:
            self.note.configure(text='Level %d has no named entries yet. Make one with the Entry tool on that level, '
                                     'and other levels can lead to it by name.' % lv)
        else:
            self.note.configure(text='')

    def _pick(self):
        lv = self._target_level()
        if lv is None:
            return
        try:
            x0, y0 = int(self.x_var.get()), int(self.y_var.get())
        except ValueError:
            x0, y0 = 5, 5
        got = SquarePicker(self, self.s, lv, x0, y0).run()
        if got:
            self.x_var.set(str(got[0]))
            self.y_var.set(str(got[1]))
            self.mode.set('square')
            self._changed()

    def close(self, value):
        if value == 'ok':
            lv = self._target_level()
            if lv is None:
                value = 'remove' if self.has_link else None
            else:
                spec = {'level': lv, 'mode': self.mode.get(), 'entry': self.entry_var.get(), 'x': 0, 'y': 0, 'text': ''}
                if spec['mode'] == 'square':
                    try:
                        spec['x'], spec['y'] = int(self.x_var.get()), int(self.y_var.get())
                        assert 1 <= spec['x'] <= SIZE and 1 <= spec['y'] <= SIZE
                    except (ValueError, AssertionError):
                        self.note.configure(text=f'x and y are numbers from 1 to {SIZE}.', style='Bad.TLabel')
                        return
                    spec['text'] = self.text_var.get().strip()
                if spec['mode'] == 'entry' and not spec['entry']:
                    spec['mode'] = 'start'
                back = self.back_var.get() and not self.exit and self.kind not in ('hole', 'jump_pad')
                value = (spec, back)
        super().close(value)


class SquarePicker(ui.Dialog):
    """A small map of a level to click a square on."""
    SCALE = 6

    def __init__(self, parent, session, level, x, y):
        super().__init__(parent, f'Pick a square on level {level}')
        self.s, self.level, self.pos = session, level, (x, y)
        ttk.Label(self.body, text='Click the square where it should arrive.', style='Dim.TLabel').pack(anchor='w', pady=(0, px(6)))
        side = SIZE * self.SCALE
        self.img = session.pictures.level_thumb(session.project.grid(level), side)
        self.canvas = tk.Canvas(self.body, width=side, height=side, highlightthickness=1, highlightbackground=C['line'],
                                bg=C['canvas'], cursor='crosshair')
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.img, anchor='nw')
        k = self.SCALE * 10
        for i in range(1, 10):
            self.canvas.create_line(i * k, 0, i * k, side, fill='#ffffff', stipple='gray25')
            self.canvas.create_line(0, i * k, side, i * k, fill='#ffffff', stipple='gray25')
        sx, sy = levelmeta.start_of(session, level)
        self._mark(sx, sy, C['accent'], 'start')
        self.cross = self.canvas.create_rectangle(0, 0, 0, 0, outline='#ff3030', width=2)
        self.label = ttk.Label(self.body, text='', style='Dim.TLabel')
        self.label.pack(anchor='w', pady=(px(6), 0))
        self.canvas.bind('<Button-1>', self._click)
        self.canvas.bind('<B1-Motion>', self._click)
        self.canvas.bind('<Motion>', self._hover)
        self._at(x, y)
        self.add_buttons([('Cancel', None, 'TButton'), ('Use this square', 'ok', 'Accent.TButton')], default='ok')

    def _mark(self, x, y, colour, tag):
        k = self.SCALE
        self.canvas.create_rectangle((x - 1) * k - 2, (y - 1) * k - 2, x * k + 2, y * k + 2, outline=colour, width=2)

    def _sq(self, e):
        return max(1, min(SIZE, e.x // self.SCALE + 1)), max(1, min(SIZE, e.y // self.SCALE + 1))

    def _hover(self, e):
        x, y = self._sq(e)
        self.label.configure(text=f'({x}, {y})   screen ({(x - 1) // 10 + 1}, {(y - 1) // 10 + 1})')

    def _click(self, e):
        self._at(*self._sq(e))

    def _at(self, x, y):
        self.pos = (x, y)
        k = self.SCALE
        self.canvas.coords(self.cross, (x - 1) * k - 3, (y - 1) * k - 3, x * k + 3, y * k + 3)
        self.label.configure(text=f'Chosen: ({x}, {y})')

    def close(self, value):
        super().close(self.pos if value == 'ok' else None)
