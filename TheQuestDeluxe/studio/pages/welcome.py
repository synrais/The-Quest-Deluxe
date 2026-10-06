"""Which quest to work on: the list of quests in Custom Maps, and making a new one."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from editor import custom
from editor.project import Project
from engine import packio
from engine.pack import DEFAULT_PACK

from .. import icons, theme, ui
from ..gallery import Entry, Gallery
from ..theme import C, px


def make_quest(name: str, blank: bool) -> str:
    """Custom Maps/<name>: a copy of The Quest's 7 levels, or the same things with one empty level."""
    name = name.strip()
    problem = custom.valid_name(name)
    if problem:
        raise ValueError(problem)
    if not blank:
        return custom.create(name)
    os.makedirs(custom.CUSTOM_DIR, exist_ok=True)
    dest = custom.pack_dir(name)
    Project.create(dest, DEFAULT_PACK, blank=True)
    q = packio.read_json(os.path.join(dest, 'quest.json'))
    q['title'] = name
    packio.write_json(os.path.join(dest, 'quest.json'), q)
    return dest


def new_pack_dialog(parent):
    """Ask for a name and what to start from; the folder made, or None."""
    d = ui.Dialog(parent, 'New quest', width=px(520))
    ttk.Label(d.body, text='Make a new quest', style='H2.TLabel').pack(anchor='w')
    ttk.Label(d.body, text='Name it (letters, numbers, spaces):', style='Dim.TLabel').pack(anchor='w', pady=(px(10), px(2)))
    var = tk.StringVar()
    e = ttk.Entry(d.body, textvariable=var, width=40)
    e.pack(fill='x')
    e.focus_set()
    kind = tk.StringVar(value='blank')
    for value, title, about in (('blank', 'Start blank', 'One empty level. The same creatures, items, spells and heroes as The Quest to build with, but none of its '
                                                         'levels or story. Best for making your own game.'),
                                ('copy', 'Start from The Quest', 'A copy of the 7 levels, all the stories and people, to change and build on.')):
        row = ttk.Frame(d.body)
        row.pack(fill='x', pady=(px(10), 0))
        ttk.Radiobutton(row, text=title, value=value, variable=kind).pack(anchor='w')
        ttk.Label(row, text=about, style='Dim.TLabel', wraplength=px(460), justify='left').pack(anchor='w', padx=px(22))
    msg = ttk.Label(d.body, text='', style='Bad.TLabel', wraplength=px(460))
    msg.pack(anchor='w', pady=(px(8), 0))
    made = []

    def go():
        problem = custom.valid_name(var.get())
        if problem:
            msg.configure(text=problem)
            return
        try:
            made.append(make_quest(var.get(), kind.get() == 'blank'))
        except (OSError, ValueError) as ex:
            msg.configure(text=f"Couldn't make it: {ex}")
            return
        d.close(True)
    d.add_buttons([('Cancel', None, 'TButton'), ('Make it', 'x', 'Accent.TButton')])
    for b in d.foot.winfo_children():
        if b.cget('text') == 'Make it':
            b.configure(command=go)
    d.bind('<Return>', lambda ev: go())
    d.run()
    return made[0] if made else None


def choose_pack(parent, last=None, force=False):
    """The window shown when Studio starts without a quest: pick one, or make one. The folder, or None to quit."""
    names = custom.packs()
    if not names:
        return new_pack_dialog(parent)
    d = ui.Dialog(parent, 'Quest Studio', width=px(560), height=px(520))
    ttk.Label(d.body, image=icons.icon('sparkle', C['accent'], px(40))).pack(pady=(px(4), px(4)))
    ttk.Label(d.body, text='Quest Studio', style='H1.TLabel').pack()
    ttk.Label(d.body, text='Pick a quest to work on, or start a new one.', style='Dim.TLabel').pack(pady=(0, px(10)))
    entries = []
    for n in names:
        title, levels = n, ''
        try:
            q = packio.read_json(os.path.join(custom.pack_dir(n), 'quest.json'))
            title = q.get('title') or n
            levels = f'{q.get("levels", "?")} levels'
        except (OSError, ValueError):
            pass
        entries.append(Entry(n, title, levels, icons.icon('map', C['accent'], px(24)), group='Your quests'))
    chosen = {'v': last if last in names else names[0]}
    gal = Gallery(d.body, on_select=lambda k: chosen.__setitem__('v', k), on_open=lambda k: d.close(k), list_mode=True)
    gal.pack(fill='both', expand=True)
    d.update_idletasks()
    gal.set_items(entries)
    gal.select(chosen['v'], scroll=False)
    d.foot.pack_forget()
    foot = ttk.Frame(d.frame)
    foot.pack(fill='x', pady=(px(14), 0))
    ttk.Button(foot, text='Quit', command=lambda: d.close(None)).pack(side='left')
    ttk.Button(foot, text='Open', style='Accent.TButton', command=lambda: d.close(chosen['v'])).pack(side='right')
    ttk.Button(foot, text='New quest…', command=lambda: d.close('__new__')).pack(side='right', padx=px(8))
    d.bind('<Return>', lambda e: d.close(chosen['v']))
    got = d.run()
    if got == '__new__':
        return new_pack_dialog(parent) or choose_pack(parent, last, force)
    return custom.pack_dir(got) if got else None
