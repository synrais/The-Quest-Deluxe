"""The questions a recording asks (a short form, one box for each), so the person who found a difference can say what it is in a few words."""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

from .record import CHOICES, QUESTIONS

REMEMBER = os.path.join(os.path.expanduser('~'), '.quest_compare.json')


def remembered() -> dict:
    try:
        with open(REMEMBER, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def remember(answers: dict):
    try:
        with open(REMEMBER, 'w', encoding='utf-8') as fh:
            json.dump({'name': answers.get('name', '')}, fh)
    except OSError:
        pass


def ask(summary: str = '', parent=None, scripted: dict | None = None) -> dict | None:
    """Show the form; the answers {key: text}, or None when it was cancelled. `scripted` answers it without a window (for tests)."""
    if scripted is not None:
        return dict(scripted)
    owner = parent or tk.Tk()
    if parent is None:
        owner.withdraw()
    win = tk.Toplevel(owner)
    win.title('Save the recording')
    win.attributes('-topmost', True)
    frame = ttk.Frame(win, padding=14)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Tell us what you found', font=('TkDefaultFont', 13, 'bold')).pack(anchor='w')
    if summary:
        ttk.Label(frame, text=summary, wraplength=520, justify='left').pack(anchor='w', pady=(2, 8))
    widgets = {}
    saved = remembered()
    for key, label, hint, rows in QUESTIONS:
        ttk.Label(frame, text=label, font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=(8, 0))
        ttk.Label(frame, text=hint, foreground='#666').pack(anchor='w')
        if key in CHOICES:
            w = ttk.Combobox(frame, values=CHOICES[key], state='readonly', width=48)
            w.pack(anchor='w')
        elif rows == 1:
            w = ttk.Entry(frame, width=60)
            w.insert(0, saved.get(key, ''))
            w.pack(anchor='w', fill='x')
        else:
            w = tk.Text(frame, width=60, height=rows + 1, wrap='word')
            w.pack(anchor='w', fill='x')
        widgets[key] = w
    result = {}

    def text_of(w):
        return w.get('1.0', 'end-1c').strip() if isinstance(w, tk.Text) else w.get().strip()

    def done(ok):
        if ok:
            result.update({k: text_of(w) for k, w in widgets.items()})
        win.destroy()
    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(12, 0))
    ttk.Button(bar, text='Save the recording', command=lambda: done(True)).pack(side='right')
    ttk.Button(bar, text='Cancel', command=lambda: done(False)).pack(side='right', padx=8)
    win.protocol('WM_DELETE_WINDOW', lambda: done(False))
    win.grab_set()
    win.wait_window()
    if parent is None:
        owner.destroy()
    if not result:
        return None
    remember(result)
    return result
