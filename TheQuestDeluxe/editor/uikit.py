"""Small things every window of the editor shares: centring a window on the screen, and the mouse wheel.

The wheel: Windows and macOS send <MouseWheel> to the focused widget and X11 sends <Button-4>/<Button-5>,
and canvases that scroll (a form, the map) have no wheel bindings of their own. install() binds the wheel
once for the whole editor and sends each turn to whatever is under the pointer: a widget that has been
given a handler with on_wheel(), else the nearest parent that has one. Text boxes, lists and trees already
scroll themselves and are left alone.
"""
from __future__ import annotations

NATIVE = ('Text', 'Listbox', 'Treeview', 'TCombobox', 'Spinbox', 'TSpinbox')


def center(win, width: int | None = None, height: int | None = None, parent=None):
    """Put a window in the middle of the screen (of its parent window, if one is given), no bigger than the
    screen."""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = min(width or win.winfo_reqwidth(), sw - 40)
    h = min(height or win.winfo_reqheight(), sh - 100)
    if parent is not None:
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
    else:
        x, y = (sw - w) // 2, (sh - h) // 2 - 20
    win.geometry(f'{w}x{h}+{max(0, x)}+{max(0, y)}')


def on_wheel(widget, handler):
    """handler(steps, ctrl, shift) is called for the wheel over widget or anything inside it (steps: + is
    down). It stays in force until the widget goes."""
    widget._wheel_handler = handler


def _route(root, event, steps):
    w = root.winfo_containing(event.x_root, event.y_root)
    while w is not None:
        if w.winfo_class() in NATIVE:
            return None
        h = getattr(w, '_wheel_handler', None)
        if h is not None:
            h(steps, bool(event.state & 0x4), bool(event.state & 0x1))
            return 'break'
        w = w.master
    return None


def install(root):
    def turned(e):
        steps = -1 if e.delta > 0 else 1
        return _route(root, e, steps * max(1, abs(e.delta) // 120))

    root.bind_all('<MouseWheel>', turned, add='+')
    root.bind_all('<Button-4>', lambda e: _route(root, e, -1), add='+')
    root.bind_all('<Button-5>', lambda e: _route(root, e, 1), add='+')


def scroll_canvas(canvas, lines_per_step=3):
    """A wheel handler that scrolls a canvas up and down (sideways with Shift)."""
    def handler(steps, ctrl, shift):
        (canvas.xview_scroll if shift else canvas.yview_scroll)(steps * lines_per_step, 'units')
    return handler


# ── drop-downs that are wide enough for their longest choice ─────────────────
from tkinter import ttk  # noqa: E402

_Combobox = ttk.Combobox
MAX_WIDTH = 72


class FitCombobox(_Combobox):
    """A Combobox that is at least as wide as the width asked for, and wider when a choice is longer, so that
    a choice is never cut off. (Wider than the screen allows is left to scroll.)"""

    def __init__(self, master=None, **kw):
        self._asked = kw.get('width') or 10
        super().__init__(master, **kw)
        self._fit()

    def configure(self, cnf=None, **kw):
        if 'width' in kw:
            self._asked = kw['width']
        out = super().configure(cnf, **kw)
        if 'values' in kw or (isinstance(cnf, dict) and 'values' in cnf):
            self._fit()
        return out

    config = configure

    def _fit(self):
        try:
            values = self.tk.splitlist(self.cget('values'))
        except Exception:                           # noqa: BLE001
            return
        longest = max((len(str(v)) for v in values), default=0)
        super().configure(width=min(MAX_WIDTH, max(self._asked, longest + 2)))


ttk.Combobox = FitCombobox


def choose(parent, title: str, prompt: str, labels: list[str]) -> int | None:
    """Ask for one of several things from a drop-down; the number of the choice, or None if cancelled."""
    import tkinter as tk
    win = tk.Toplevel(parent)
    win.title(title)
    box = ttk.Frame(win, padding=12)
    box.pack()
    ttk.Label(box, text=prompt, justify='left').pack(anchor='w')
    combo = ttk.Combobox(box, values=labels, state='readonly', width=30)
    combo.current(0)
    combo.pack(fill='x', pady=8)
    answer = []
    row = ttk.Frame(box)
    row.pack(fill='x')
    ttk.Button(row, text='OK', command=lambda: (answer.append(combo.current()), win.destroy())).pack(side='left')
    ttk.Button(row, text='Cancel', command=win.destroy).pack(side='left', padx=6)
    center(win, parent=parent.winfo_toplevel())
    win.transient(parent.winfo_toplevel())
    win.grab_set()
    win.wait_window()
    return answer[0] if answer else None
