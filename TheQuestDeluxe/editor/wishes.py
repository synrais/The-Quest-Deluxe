"""The Wishes window: somewhere to write what the editor or the game can't do yet (a spell that does this, a tile
that does that, a kind of creature ...). It is kept as WISHES.txt in the pack's folder; "Make Edits Zip.bat" puts it in
the zip, and its text at the top of WHAT_CHANGED.txt (tools/pack_edits_zip.py reads it)."""
from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import ttk

from .uikit import center, tip

FILE = 'WISHES.txt'
TEMPLATE = ('# Things I wish the editor or the game could do. Lines starting with # are ignored.\n'
            '# Write anything: what you want, what you tried, what was missing. One wish to a paragraph is plenty.\n\n')


class WishesWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.path = os.path.join(app.project.root, FILE)
        self.title(f'Wishes - {app.project.name}')
        top = ttk.Frame(self, padding=10)
        top.pack(fill='both', expand=True)
        ttk.Label(top, justify='left', wraplength=620,
                  text='What do you wish the editor or the game could do? A spell, a tile, a kind of creature, a '
                       'button, anything. Write it here and press Save: Make Edits Zip.bat sends it on with your '
                       'edits, so the game can be changed to do it.').pack(anchor='w')
        row = ttk.Frame(top)
        row.pack(fill='x', pady=(8, 2))
        ttk.Label(row, text='A wish:').pack(side='left')
        self.line = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.line)
        entry.pack(side='left', fill='x', expand=True, padx=6)
        entry.bind('<Return>', lambda e: self.add())
        ttk.Button(row, text='Add', command=self.add).pack(side='left')
        box = ttk.Frame(top)
        box.pack(fill='both', expand=True, pady=6)
        self.text = tk.Text(box, width=84, height=18, wrap='word', undo=True)
        bar = ttk.Scrollbar(box, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        self.text.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        try:
            with open(self.path, encoding='utf-8') as fh:
                self.text.insert('1.0', fh.read())
        except OSError:
            self.text.insert('1.0', TEMPLATE)
        buttons = ttk.Frame(top)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Save', command=self.save).pack(side='left')
        ttk.Button(buttons, text='Save and close', command=self.close).pack(side='left', padx=6)
        self.status = ttk.Label(buttons, text='', foreground='#060')
        self.status.pack(side='left', padx=10)
        tip(self.text, 'Free writing: wishes, ideas, what you tried and what was missing. Lines starting with # are '
                       'ignored.')
        tip(entry, 'Type one wish and press Enter (or Add): it goes at the end of the page with today\'s date.')
        self.bind('<Control-s>', lambda e: self.save())
        self.protocol('WM_DELETE_WINDOW', self.close)
        entry.focus_set()
        center(self, parent=app.root)

    def add(self):
        said = self.line.get().strip()
        if not said:
            return
        end = self.text.get('1.0', 'end-1c')
        if end and not end.endswith('\n'):
            self.text.insert('end', '\n')
        self.text.insert('end', f'- {time.strftime("%Y-%m-%d")}: {said}\n')
        self.text.see('end')
        self.line.set('')
        self.save()

    def save(self):
        text = self.text.get('1.0', 'end-1c')
        with open(self.path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text if text.endswith('\n') or not text else text + '\n')
        self.status.config(text='Saved. Make Edits Zip.bat sends it on.')

    def close(self):
        self.save()
        self.destroy()
