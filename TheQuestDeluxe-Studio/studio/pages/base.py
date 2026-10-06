"""What every page of the Studio is: built on first show, told when it is shown, hidden or the pack changed."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import icons, theme, ui
from ..model import save_settings
from ..theme import C, px


class Page(ttk.Frame):
    key = 'page'
    title = 'Page'
    icon = 'home'
    blurb = ''
    intro = ''                        # a few words the first time the page is opened (a bar that can be put away)
    section = 'make'                  # where the sidebar lists it

    def __init__(self, master, app):
        super().__init__(master, style='TFrame')
        self.app = app
        self.s = app.session
        self.built = False
        self.visible = False

    # ── life cycle ──────────────────────────────────────────────────────────
    def build(self):
        """Make the widgets (once)."""

    def show(self, **where):
        if not self.built:
            self.built = True
            self.build()
        self.visible = True
        self._show_intro()
        self.on_show(**where)

    def _show_intro(self):
        seen = self.app.settings.setdefault('seen', [])
        if not self.intro or self.key in seen or getattr(self, '_intro_bar', None) is not None:
            return
        bar = tk.Frame(self, bg=C['raised'], highlightthickness=1, highlightbackground=C['accent'])
        tk.Label(bar, image=icons.icon('info', C['accent'], px(18)), bg=C['raised']).pack(side='left', padx=(px(12), px(8)), pady=px(8))
        tk.Label(bar, text=self.intro, bg=C['raised'], fg=C['text'], anchor='w', justify='left', wraplength=px(900)).pack(
            side='left', fill='x', expand=True, pady=px(6))
        ttk.Button(bar, text='Got it', style='Small.TButton', command=self._put_away_intro).pack(side='right', padx=px(12))
        kids = self.pack_slaves()
        bar.pack(side='top', fill='x', padx=px(10), pady=(px(8), 0), **({'before': kids[0]} if kids else {}))
        self._intro_bar = bar

    def _put_away_intro(self):
        bar = getattr(self, '_intro_bar', None)
        if bar is not None:
            bar.destroy()
        self._intro_bar = None
        seen = self.app.settings.setdefault('seen', [])
        if self.key not in seen:
            seen.append(self.key)
            save_settings(self.app.settings)

    def hide(self):
        self.visible = False
        self.on_hide()

    def on_show(self, **where):
        """The page is on screen (with `where` if something asked for a particular thing)."""

    def on_hide(self):
        pass

    def reload(self):
        """The pack was replaced or changed wholesale: draw it again."""

    def search(self, q: str) -> list:
        """Things on this page to jump to: [(title, subtitle, icon, callable)]."""
        return []

    # ── layout helpers ──────────────────────────────────────────────────────
    def header(self, parent, title=None, blurb=None):
        row = ttk.Frame(parent)
        row.pack(fill='x', padx=px(20), pady=(px(16), px(8)))
        ttk.Label(row, text=title or self.title, style='H1.TLabel').pack(side='left')
        if blurb or self.blurb:
            ttk.Label(row, text=blurb or self.blurb, style='Dim.TLabel').pack(side='left', padx=px(14), pady=(px(8), 0))
        return row


class Placeholder(Page):
    """A page that is not built yet."""

    def build(self):
        self.header(self)
        ui.EmptyState(self, self.icon, f'The {self.title} page is coming.').pack(expand=True)
