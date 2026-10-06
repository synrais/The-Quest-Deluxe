"""Colours, fonts and the ttk styles of the Studio (a dark theme and a light one)."""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

DARK = {
    'bg': '#14161a', 'panel': '#1b1e24', 'raised': '#242830', 'hover': '#2e333d', 'line': '#343a46',
    'text': '#e8eaee', 'dim': '#9aa3b2', 'faint': '#6d7686', 'accent': '#e9a23b', 'accent_text': '#1a1303',
    'ok': '#5fcf80', 'warn': '#f0b14a', 'bad': '#ef6b6b', 'info': '#5aa9ff', 'select': '#3a4152',
    'input': '#101215', 'canvas': '#0d0f12',
}
LIGHT = {
    'bg': '#eef0f3', 'panel': '#f8f9fb', 'raised': '#ffffff', 'hover': '#e4e8ee', 'line': '#cfd5de',
    'text': '#1d2330', 'dim': '#566074', 'faint': '#8a93a3', 'accent': '#c77a0a', 'accent_text': '#ffffff',
    'ok': '#1f9d55', 'warn': '#b7791f', 'bad': '#d64545', 'info': '#2b6cb0', 'select': '#d7deea',
    'input': '#ffffff', 'canvas': '#dfe3ea',
}

C = dict(DARK)                 # the colours in force (read these, e.g. theme.C['accent'])
_name = 'dark'
FONT = 'TkDefaultFont'
UI_SCALE = 1.0


def px(n: float) -> int:
    """Pixels at this screen's scale."""
    return int(round(n * UI_SCALE))


def pick_family(root) -> str:
    have = set(tkfont.families(root))
    order = ('Segoe UI', 'SF Pro Text', 'Helvetica Neue', 'Noto Sans', 'Ubuntu', 'Cantarell', 'DejaVu Sans', 'Arial')
    return next((f for f in order if f in have), 'TkDefaultFont')


def make_dpi_aware():
    """Windows: draw crisp text on a high-DPI screen (call before the first Tk window)."""
    if sys.platform.startswith('win'):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:                                     # noqa: BLE001
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:                                 # noqa: BLE001
                pass


def font(size=10, weight='normal', slant='roman', family=None) -> tuple:
    return (family or FONT, size, weight) if slant == 'roman' else (family or FONT, size, weight, slant)


def apply(root, name: str | None = None):
    """Configure every ttk style for the theme ('dark' or 'light')."""
    global _name, FONT, UI_SCALE
    if name:
        _name = name
    C.clear()
    C.update(DARK if _name == 'dark' else LIGHT)
    FONT = pick_family(root)
    try:
        UI_SCALE = max(1.0, float(root.tk.call('tk', 'scaling')) / 1.333333)
    except tk.TclError:
        UI_SCALE = 1.0
    for f in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkCaptionFont', 'TkTooltipFont'):
        try:
            tkfont.nametofont(f).configure(family=FONT, size=10)
        except tk.TclError:
            pass
    root.configure(bg=C['bg'])
    root.option_add('*Font', (FONT, 10))
    root.option_add('*Menu.background', C['panel'])
    root.option_add('*Menu.foreground', C['text'])
    root.option_add('*Menu.activeBackground', C['accent'])
    root.option_add('*Menu.activeForeground', C['accent_text'])
    root.option_add('*Menu.relief', 'flat')
    root.option_add('*TCombobox*Listbox.background', C['input'])
    root.option_add('*TCombobox*Listbox.foreground', C['text'])
    root.option_add('*TCombobox*Listbox.selectBackground', C['accent'])
    root.option_add('*TCombobox*Listbox.selectForeground', C['accent_text'])
    root.option_add('*TCombobox*Listbox.font', (FONT, 10))
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', background=C['panel'], foreground=C['text'], fieldbackground=C['input'],
                bordercolor=C['line'], lightcolor=C['panel'], darkcolor=C['panel'], troughcolor=C['bg'],
                focuscolor=C['accent'], selectbackground=C['accent'], selectforeground=C['accent_text'],
                insertcolor=C['text'], font=(FONT, 10))
    s.configure('TFrame', background=C['panel'])
    s.configure('Bg.TFrame', background=C['bg'])
    s.configure('Raised.TFrame', background=C['raised'])
    s.configure('Card.TFrame', background=C['raised'], bordercolor=C['line'], relief='flat')
    s.configure('Side.TFrame', background=C['bg'])
    s.configure('TLabel', background=C['panel'], foreground=C['text'])
    s.configure('Bg.TLabel', background=C['bg'])
    s.configure('Raised.TLabel', background=C['raised'])
    s.configure('Dim.TLabel', foreground=C['dim'])
    s.configure('Faint.TLabel', foreground=C['faint'])
    s.configure('Raised.Dim.TLabel', background=C['raised'], foreground=C['dim'])
    s.configure('H1.TLabel', font=(FONT, 20, 'bold'))
    s.configure('H2.TLabel', font=(FONT, 14, 'bold'))
    s.configure('H3.TLabel', font=(FONT, 11, 'bold'))
    s.configure('Bg.H1.TLabel', background=C['bg'], font=(FONT, 20, 'bold'))
    s.configure('Accent.TLabel', foreground=C['accent'])
    s.configure('Ok.TLabel', foreground=C['ok'])
    s.configure('Warn.TLabel', foreground=C['warn'])
    s.configure('Bad.TLabel', foreground=C['bad'])
    s.configure('TButton', background=C['raised'], foreground=C['text'], bordercolor=C['line'], padding=(px(12), px(6)),
                relief='flat', borderwidth=1, focusthickness=0)
    s.map('TButton', background=[('pressed', C['select']), ('active', C['hover']), ('disabled', C['panel'])],
          foreground=[('disabled', C['faint'])], bordercolor=[('focus', C['accent'])])
    s.configure('Accent.TButton', background=C['accent'], foreground=C['accent_text'], bordercolor=C['accent'],
                font=(FONT, 10, 'bold'))
    s.map('Accent.TButton', background=[('pressed', C['accent']), ('active', C['accent']), ('disabled', C['line'])],
          foreground=[('disabled', C['faint'])])
    s.configure('Flat.TButton', background=C['panel'], bordercolor=C['panel'], padding=(px(8), px(4)))
    s.map('Flat.TButton', background=[('pressed', C['select']), ('active', C['hover'])])
    s.configure('Tool.TButton', background=C['panel'], bordercolor=C['panel'], padding=px(5))
    s.map('Tool.TButton', background=[('pressed', C['select']), ('active', C['hover'])])
    s.configure('Small.TButton', padding=(px(8), px(3)))
    s.configure('ToolOn.TButton', background=C['accent'], bordercolor=C['accent'], padding=px(5))
    s.map('ToolOn.TButton', background=[('pressed', C['accent']), ('active', C['accent'])])
    s.configure('Danger.TButton', foreground=C['bad'])
    s.configure('TEntry', fieldbackground=C['input'], foreground=C['text'], bordercolor=C['line'], padding=px(5),
                insertcolor=C['text'])
    s.map('TEntry', bordercolor=[('focus', C['accent'])], fieldbackground=[('disabled', C['panel'])])
    s.configure('TSpinbox', fieldbackground=C['input'], foreground=C['text'], bordercolor=C['line'], padding=px(4),
                arrowcolor=C['dim'], background=C['raised'])
    s.map('TSpinbox', bordercolor=[('focus', C['accent'])])
    s.configure('TCombobox', fieldbackground=C['input'], foreground=C['text'], bordercolor=C['line'], padding=px(5),
                arrowcolor=C['dim'], background=C['raised'])
    s.map('TCombobox', fieldbackground=[('readonly', C['input'])], bordercolor=[('focus', C['accent'])],
          foreground=[('readonly', C['text'])], selectbackground=[('readonly', C['input'])],
          selectforeground=[('readonly', C['text'])])
    s.configure('TCheckbutton', background=C['panel'], foreground=C['text'], focuscolor=C['panel'])
    s.map('TCheckbutton', background=[('active', C['panel'])], indicatorcolor=[('selected', C['accent']),
                                                                              ('!selected', C['input'])])
    s.configure('Raised.TCheckbutton', background=C['raised'])
    s.map('Raised.TCheckbutton', background=[('active', C['raised'])])
    s.configure('TRadiobutton', background=C['panel'], foreground=C['text'])
    s.map('TRadiobutton', background=[('active', C['panel'])], indicatorcolor=[('selected', C['accent']),
                                                                              ('!selected', C['input'])])
    s.configure('TScale', background=C['panel'], troughcolor=C['line'])
    s.configure('Horizontal.TScale', background=C['panel'], troughcolor=C['line'])
    s.configure('Raised.Horizontal.TScale', background=C['raised'], troughcolor=C['line'])
    s.configure('TProgressbar', background=C['accent'], troughcolor=C['line'], bordercolor=C['line'])
    s.configure('TSeparator', background=C['line'])
    s.configure('Vertical.TScrollbar', background=C['raised'], troughcolor=C['bg'], bordercolor=C['bg'],
                arrowcolor=C['dim'], lightcolor=C['raised'], darkcolor=C['raised'], gripcount=0, arrowsize=px(12))
    s.configure('Horizontal.TScrollbar', background=C['raised'], troughcolor=C['bg'], bordercolor=C['bg'],
                arrowcolor=C['dim'], lightcolor=C['raised'], darkcolor=C['raised'], gripcount=0, arrowsize=px(12))
    s.map('Vertical.TScrollbar', background=[('active', C['hover'])])
    s.map('Horizontal.TScrollbar', background=[('active', C['hover'])])
    s.configure('Treeview', background=C['input'], fieldbackground=C['input'], foreground=C['text'],
                bordercolor=C['line'], rowheight=px(26), relief='flat')
    s.map('Treeview', background=[('selected', C['select'])], foreground=[('selected', C['text'])])
    s.configure('Treeview.Heading', background=C['raised'], foreground=C['dim'], relief='flat', padding=px(5))
    s.configure('TNotebook', background=C['panel'], bordercolor=C['line'], tabmargins=0)
    s.configure('TNotebook.Tab', background=C['panel'], foreground=C['dim'], padding=(px(12), px(6)), borderwidth=0)
    s.map('TNotebook.Tab', background=[('selected', C['raised'])], foreground=[('selected', C['accent'])])
    s.configure('TLabelframe', background=C['panel'], bordercolor=C['line'])
    s.configure('TLabelframe.Label', background=C['panel'], foreground=C['dim'])
    s.configure('TPanedwindow', background=C['bg'])
    s.configure('Sash', sashthickness=px(5), background=C['bg'])
    return s


def toggle(root):
    apply(root, 'light' if _name == 'dark' else 'dark')
    return _name


def name() -> str:
    return _name
