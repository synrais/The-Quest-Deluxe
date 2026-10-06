"""Home: what is in the quest, what to make next, and the things that are missing."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import icons, theme, ui
from ..theme import C, px
from .base import Page


class HomePage(Page):
    key, title, icon = 'home', 'Home', 'home'

    def build(self):
        self.scroller = ui.Scrolled(self)
        self.scroller.pack(fill='both', expand=True)
        self.s.on('any', self._changed)

    def _changed(self, scope, source):
        if self.visible:
            self.on_show()

    def on_show(self, **where):
        body = self.scroller.body
        self.scroller.clear()
        s, p = self.s, self.s.project
        title = p.quest.get('title') or p.name
        head = ttk.Frame(body)
        head.pack(fill='x', padx=px(28), pady=(px(22), px(4)))
        ttk.Label(head, text=title, style='H1.TLabel').pack(anchor='w')
        by = p.quest.get('author')
        ttk.Label(head, text=(f'by {by}  ·  ' if by else '') + f'{s.levels} level{"s" if s.levels != 1 else ""}',
                  style='Dim.TLabel').pack(anchor='w')
        # counts
        cards = ttk.Frame(body)
        cards.pack(fill='x', padx=px(24), pady=(px(14), px(4)))
        monsters = [r for r in p.tables['creatures'] if r['id'] > 0]
        people = [r for r in p.tables['creatures'] if -100 < r['id'] < 0]
        items = [r for r in p.tables['items'] if r['id']]
        for i, (icon, n, text, page) in enumerate((('map', s.levels, 'levels', 'world'), ('skull', len(monsters), 'monsters', 'creatures'),
                                                   ('person', len(people), 'people', 'creatures'), ('sword', len(items), 'items', 'items'),
                                                   ('helmet', len(p.tables['classes']), 'heroes', 'heroes'),
                                                   ('wand', len(p.tables['spells']), 'spells', 'spells'))):
            card = ui.Card(cards, pad=px(12))
            card.grid(row=0, column=i, padx=px(4), sticky='nsew')
            cards.columnconfigure(i, weight=1, uniform='c')
            ttk.Label(card.inner, image=icons.icon(icon, C['accent'], px(26)), style='Raised.TLabel').pack(anchor='w')
            ttk.Label(card.inner, text=str(n), style='Raised.TLabel', font=(theme.FONT, 22, 'bold')).pack(anchor='w')
            ttk.Label(card.inner, text=text, style='Raised.Dim.TLabel').pack(anchor='w')
            for w in [card] + list(card.inner.winfo_children()):
                w.bind('<Button-1>', lambda e, pg=page: self.app.go(pg))
                w.configure(cursor='hand2')
        # make something
        ttk.Label(body, text='Make something', style='H2.TLabel').pack(anchor='w', padx=px(28), pady=(px(22), px(6)))
        row = ttk.Frame(body)
        row.pack(fill='x', padx=px(24))
        acts = (('wand', 'Level wizard', 'A whole level, start to end, in a few clicks', lambda: self.app.go('world', wizard=True)),
                ('skull', 'New creature', 'A monster, a person or an ally', lambda: self.app.go('creatures', new=True)),
                ('sword', 'New item', 'A weapon, armour, a potion ...', lambda: self.app.go('items', new=True)),
                ('play', 'Play', 'Try the game as it is now', lambda: self.app.play(from_start=True)))
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
