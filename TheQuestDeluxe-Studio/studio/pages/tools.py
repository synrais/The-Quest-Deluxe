"""Small things from the menu: restoring saved edits, recovering pictures, the help window."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk

from core import recover, side_save

from .. import ui
from ..theme import px


def restore_edits(app, path=None):
    """Put the additions of a saved zip back (after a new game was dragged over this one)."""
    if path is None:
        start = side_save.home_dir()
        path = filedialog.askopenfilename(title='A saved zip of your additions', initialdir=start if os.path.isdir(start) else None,
                                          filetypes=[('Zips', '*.zip')])
    if not path:
        return
    deluxe = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    s = app.session
    s.autosave()
    try:
        todo = side_save.apply(deluxe, path, into=s.project.root)
    except (OSError, ValueError, KeyError) as e:
        ui.inform(app.root, 'Restore', f"Couldn't read {path}: {e}")
        return
    if not todo:
        ui.inform(app.root, 'Restore', 'Everything in that zip is already here.')
        return
    shown = '\n'.join(todo[:15]) + (f'\n... and {len(todo) - 15} more' if len(todo) > 15 else '')
    if not ui.confirm(app.root, 'Restore my edits', f'Put back {len(todo)} things from\n{path}?\n\n{shown}', yes='Put them back'):
        return
    side_save.apply(deluxe, path, write=True, into=s.project.root)
    app.open(s.project.root)
    app.say(f'Put back {len(todo)} things.', 'ok')


def recover_pictures(app):
    """Make an entry for every picture that has none (the tables were replaced, the pictures stayed)."""
    s = app.session
    found = recover.orphans(s.project)
    count = sum(len(v) for v in found.values())
    if not count:
        ui.inform(app.root, 'Recover pictures', 'Every picture already has an entry.')
        return
    if not ui.confirm(app.root, 'Recover pictures', f'{count} pictures have no entry (their creature, item, spell or class is '
                      'missing). Make an entry for each, called "Recovered ...", to fill in again?', yes='Make them'):
        return
    with s.edit('Recover pictures', 'items', 'creatures', 'spells', 'classes'):
        recover.recover(s.project)
    app.reload_all()
    app.say(f'Made {count} entries: look for "Recovered" in the lists.', 'ok')


HELP = [
    ('Everywhere', [('Ctrl+K', 'Search: jump to any level, creature, item, spell ... or run a command'), ('Ctrl+Z / Ctrl+Y', 'Undo / redo (everything, not only the map)'),
                    ('Ctrl+S', 'Save now and make the zip of your additions (it also saves by itself as you go)'),
                    ('F5', 'Play the game')]),
    ('The map', [('Left button', 'Use the tool'), ('Right button', 'Pick what is under the pointer'), ('Space + drag / middle button', 'Move the map'),
                 ('Mouse wheel', 'Scroll;  Ctrl+wheel zooms;  Shift+wheel scrolls sideways'),
                 ('B  E  R  L  G  I  S', 'Brush, Eraser, Rectangle, Line, Fill, Pick (eyedropper), Select'),
                 ('Ctrl+C / Ctrl+X / Ctrl+V', 'Copy, cut and paste what you selected'), ('Ctrl+A', 'Select the whole level'),
                 ('Delete', 'Clear what you selected'), ('Arrow keys', 'Move what you selected one square'),
                 ('+  /  -', 'Zoom in and out'), ('Esc', 'Let go of what you were doing')]),
]


def show_help(app):
    d = ui.Dialog(app.root, 'Shortcuts and help')
    for title, rows in HELP:
        ttk.Label(d.body, text=title, style='H3.TLabel').pack(anchor='w', pady=(px(8), px(2)))
        for key, text in rows:
            r = ttk.Frame(d.body)
            r.pack(fill='x', pady=1)
            ttk.Label(r, text=key, width=26, style='Accent.TLabel').pack(side='left')
            ttk.Label(r, text=text, style='Dim.TLabel', wraplength=px(420), justify='left').pack(side='left')
    ttk.Label(d.body, text='Everything is saved as you go. Ctrl+S also makes a zip of your additions (Send my edits sends it).',
              style='Dim.TLabel', wraplength=px(560)).pack(anchor='w', pady=(px(12), 0))
    d.add_buttons([('Close', True, 'Accent.TButton')], default=True)
    d.run()
