"""The "What's new" box: the notes of an update (core/whatsnew.py) laid out in a themed window, alone or as part of the update question."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme, ui
from .theme import C, px

WIDTH = 66                                     # characters across


def dialog(parent, title, entries, intro='', outro='', yes='OK', no=None) -> bool:
    """Show the notes (core.whatsnew entries); with a `no` button it is a question and the answer is returned (True for `yes`)."""
    d = ui.Dialog(parent, title, width=px(560))
    if intro:
        ttk.Label(d.body, text=intro, wraplength=px(540), justify='left').pack(anchor='w', pady=(0, px(8)))
    frame = tk.Frame(d.body, bg=C['line'])
    frame.pack(fill='both', expand=True)
    lines = sum(2 + sum(-(-len(c) // (WIDTH - 5)) for c in e['changes']) for e in entries)
    txt = tk.Text(frame, wrap='word', width=WIDTH, height=max(4, min(lines, 20)), bg=C['raised'], fg=C['text'], relief='flat', bd=0,
                  padx=px(12), pady=px(8), font=(theme.FONT, 10), cursor='arrow', highlightthickness=0, takefocus=0)
    txt.tag_configure('title', font=(theme.FONT, 11, 'bold'), foreground=C['accent'], spacing1=px(8), spacing3=px(2))
    txt.tag_configure('change', lmargin1=px(14), lmargin2=px(28), spacing1=px(2))
    for e in entries:
        txt.insert('end', e['title'] + '\n', 'title')
        for c in e['changes']:
            txt.insert('end', '•  ' + c + '\n', 'change')
    txt.configure(state='disabled')
    if lines > 20:
        bar = ttk.Scrollbar(frame, command=txt.yview)
        txt.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y', padx=(0, 1), pady=1)
    txt.pack(side='left', fill='both', expand=True, padx=1, pady=1)
    if outro:
        ttk.Label(d.body, text=outro, wraplength=px(540), justify='left').pack(anchor='w', pady=(px(10), 0))
    d.add_buttons([(no, False, 'TButton'), (yes, True, 'Accent.TButton')] if no else [(yes, True, 'Accent.TButton')], default=True)
    return bool(d.run())
