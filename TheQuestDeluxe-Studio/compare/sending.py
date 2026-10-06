"""After a recording is saved: offer to send it (with the rest of the edits) to the game's maker, the same way "Send my edits..." does."""
from __future__ import annotations

import time


def offer(path: str) -> str:
    """Ask, and send if the person says yes. Returns what happened, in a sentence (also shown to the person)."""
    import tkinter
    from tkinter import messagebox

    from core import pack_edits, send_edits
    cfg = send_edits.load_settings()
    user, key = send_edits.username(cfg.get('user', '')), (cfg.get('key') or '').strip()
    root = tkinter.Tk()
    root.withdraw()
    try:
        if not (user and key):
            text = ('Saved. To send it on, open The Quest Studio, press "Send my edits..." and type your username and key once; '
                    'after that this window can send for you.')
            messagebox.showinfo('Compare to DOS', text, parent=root)
            return text
        if not messagebox.askyesno('Compare to DOS', f'Saved.\n\nSend it now, as "{user}", to the game\'s maker?', parent=root):
            return 'Saved, not sent.'
        files, report = pack_edits.gather(note='a comparison with the DOS game')
        try:
            branch = send_edits.send(files, report, key, cfg.get('name', ''), user=user)
        except send_edits.SendError as e:
            text = f'Not sent: {e}\n\nIt is saved, and goes with the next "Send my edits".'
        else:
            send_edits.save_settings({'last_sent': time.time()})
            text = f'Sent, to branch "{branch}".'
        messagebox.showinfo('Compare to DOS', text, parent=root)
        return text
    finally:
        root.destroy()
