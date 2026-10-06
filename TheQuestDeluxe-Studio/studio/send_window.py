"""The "Send my edits..." window: sends what was added or changed since the game came to the game's repository
(as a branch of its own), or makes a zip instead. The work is in send_edits.py and pack_edits.py."""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from core import pack_edits, send_edits
from .uikit import center, tip


class SendWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        app.save()
        cfg = send_edits.load_settings()
        self.title('Send my edits')
        top = ttk.Frame(self, padding=10)
        top.pack(fill='both', expand=True)
        self.name = tk.StringVar(value=cfg.get('name', ''))
        self.user = tk.StringVar(value=cfg.get('user', ''))
        self.key = tk.StringVar(value=cfg.get('key', ''))
        self.note = tk.StringVar()
        self.files, self.report = pack_edits.gather(note='')
        ttk.Label(top, justify='left', wraplength=560,
                  text='This sends everything you added or changed (pictures, tables, wishes) to the game\'s '
                       'maker. It never changes the game itself: it goes into a branch and folder of your own to be looked at first, and every send is kept.'
                  ).pack(anchor='w')
        grid = ttk.Frame(top)
        grid.pack(fill='x', pady=8)
        rows = (('Username:', self.user, ''), ('Your name:', self.name, ''), ('A note:', self.note, ''), ('Key:', self.key, '*'))
        self.entries = {}
        for i, (label, var, show) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky='w', pady=2)
            e = ttk.Entry(grid, textvariable=var, width=60, show=show)
            e.grid(row=i, column=1, sticky='ew', padx=6)
            self.entries[label] = e
        grid.columnconfigure(1, weight=1)
        tip(self.entries['Username:'], 'The username you were given: letters and numbers. Everything you send goes into a folder and a branch of that name, '
                                       'so it is kept apart from everyone else\'s.')
        tip(self.entries['Your name:'], 'So it is known who sent it.')
        tip(self.entries['A note:'], 'One line about what this is (optional).')
        tip(self.entries['Key:'], 'The long password you were given, pasted once. It is kept on this computer only, '
                                  'outside the game folder.')
        self.summary = tk.Text(top, width=80, height=14, wrap='word')
        self.summary.pack(fill='both', expand=True, pady=4)
        self.summary.insert('1.0', self.report)
        self.summary.config(state='disabled')
        self.status = ttk.Label(top, text='', wraplength=560)
        self.status.pack(anchor='w')
        row = ttk.Frame(top)
        row.pack(fill='x', pady=(6, 0))
        self.go = ttk.Button(row, text='Send', command=self.send)
        self.go.pack(side='left')
        ttk.Button(row, text='Make zip instead', command=self.zip).pack(side='left', padx=6)
        ttk.Button(row, text='Close', command=self.destroy).pack(side='right')
        if not self.files:
            self.go.state(['disabled'])
        center(self, parent=app.root)

    def say(self, text: str):
        self.after(0, lambda: self.status.config(text=text))

    def zip(self):
        path, report = pack_edits.build(note=self.note.get())
        if path:
            messagebox.showinfo('Zip made', 'Made:\n%s\n\nSend this zip on.' % path, parent=self)
        else:
            messagebox.showinfo('Nothing to send', report, parent=self)

    def send(self):
        name, key, user = self.name.get().strip(), self.key.get().strip(), send_edits.username(self.user.get())
        if not user:
            messagebox.showinfo('Your username', 'Please type your username first (letters and numbers).', parent=self)
            return
        self.user.set(user)
        if send_edits.total_size(self.files) > send_edits.BIG and not messagebox.askyesno(
                'A lot of pictures', 'This is a big one. Send it anyway?', parent=self):
            return
        send_edits.save_settings({'name': name, 'key': key, 'user': user})
        _, report = pack_edits.gather(note=self.note.get())
        self.go.state(['disabled'])

        def work():
            try:
                branch = send_edits.send(self.files, report, key, name, progress=self.say, user=user)
                send_edits.save_settings({'last_sent': time.time()})
                self.after(0, lambda: self.done('Sent! It is in the game\'s repository, branch "%s", folder edits_inbox/%s.' % (branch, user)))
            except send_edits.SendError as e:
                self.after(0, lambda: self.done(str(e), failed=True))
            except Exception as e:  # noqa: BLE001 - whatever it was, say it rather than hang
                self.after(0, lambda: self.done('Something went wrong: %s' % e, failed=True))
        threading.Thread(target=work, daemon=True).start()

    def done(self, text: str, failed: bool = False):
        self.status.config(text=text, foreground='#a00' if failed else '#060')
        self.go.state(['!disabled'])
        if failed:
            messagebox.showwarning('Not sent', text + '\n\nYou can press "Make zip instead".', parent=self)
