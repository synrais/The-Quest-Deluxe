"""What every page of the Studio is: built on first show, told when it is shown, hidden or the pack changed."""
from __future__ import annotations

from tkinter import ttk

from .. import theme, ui
from ..theme import px


class Page(ttk.Frame):
    key = 'page'
    title = 'Page'
    icon = 'home'
    blurb = ''
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
        self.on_show(**where)

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
