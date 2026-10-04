"""The window that asks which pack to edit when the editor starts: the packs of Custom Maps, a New pack... button,
and with none yet, straight to naming the first one."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from . import custom
from .uikit import center


def ask_new_name(parent) -> str | None:
    """Ask for a new pack's name until it is a good one (None if cancelled)."""
    text = 'Name your pack. It starts as a copy of the 7 levels of The Quest, in its own folder in Custom Maps.'
    while True:
        name = simpledialog.askstring('New pack', text, parent=parent)
        if name is None:
            return None
        problem = custom.valid_name(name)
        if not problem:
            return name.strip()
        text = f'{problem}\n\nName your pack:'


def make_pack(parent) -> str | None:
    """Ask for a name and make the pack; its folder, or None."""
    name = ask_new_name(parent)
    if name is None:
        return None
    try:
        return custom.create(name)
    except (OSError, ValueError) as e:
        messagebox.showerror('New pack', f"Couldn't make the pack: {e}", parent=parent)
        return None


class PackChooser(tk.Toplevel):
    """result: the folder of the pack chosen (or just made), or None."""

    def __init__(self, parent, last: str | None = None):
        super().__init__(parent)
        self.title('Which pack?')
        self.result = None
        top = ttk.Frame(self, padding=12)
        top.pack(fill='both', expand=True)
        ttk.Label(top, justify='left', text='The first 7 levels of The Quest are locked: they are never changed.\n'
                  'Your own packs, in Custom Maps, start as copies of them. Which one do you want to edit?').pack(anchor='w')
        self.box = tk.Listbox(top, height=10, width=44, exportselection=False)
        self.box.pack(fill='both', expand=True, pady=8)
        self.names = custom.packs()
        for n in self.names:
            self.box.insert('end', n)
        if self.names:
            self.box.selection_set(self.names.index(last) if last in self.names else 0)
        self.box.bind('<Double-Button-1>', lambda e: self.open_chosen())
        self.box.bind('<Return>', lambda e: self.open_chosen())
        row = ttk.Frame(top)
        row.pack(fill='x')
        ttk.Button(row, text='Open', command=self.open_chosen).pack(side='left')
        ttk.Button(row, text='New pack...', command=self.new).pack(side='left', padx=6)
        ttk.Button(row, text='Quit', command=self.destroy).pack(side='right')
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.transient(parent)
        center(self, parent=parent)
        self.grab_set()
        self.box.focus_set()

    def open_chosen(self):
        sel = self.box.curselection()
        if sel:
            self.result = custom.pack_dir(self.names[sel[0]])
            self.destroy()

    def new(self):
        made = make_pack(self)
        if made:
            self.result = made
            self.destroy()


def choose_pack(parent, last: str | None = None) -> str | None:
    """Which pack to edit: with none yet, ask for the name of the first; otherwise the list. None if the person quits."""
    if not custom.packs():
        return make_pack(parent)
    win = PackChooser(parent, last)
    parent.wait_window(win)
    return win.result
