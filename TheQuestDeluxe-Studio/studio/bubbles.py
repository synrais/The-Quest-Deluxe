"""The help bubbles: the little boxes that explain a widget while the pointer rests on it.

One switch turns them all off (the Studio's menu and the button in its top bar; it is remembered in the
Studio's settings). While they are on, a bubble:
  * only comes when the pointer has stopped (it waits for the pointer to rest, and starts again at every move);
  * goes away at the first real move, at a click, a key or the wheel, and by itself after a few seconds, so it
    is never left lying on what is being edited;
  * on a big surface to draw or edit on (a picture being painted, a map, a list) is put outside that surface,
    not next to the pointer, and comes later; if there is no room outside it goes to the corner furthest from the
    pointer;
  * on a small widget (a button, a label) sits below and to the right of the pointer, or to the left or above
    if there is no room, and never under the pointer.
"""
from __future__ import annotations

import tkinter as tk

from . import theme

_on = True                                  # the one switch
_current = None                             # the bubble on screen (there is never more than one)

BUTTONS_DOWN = 0x1F00                       # Tk's state bits for the mouse buttons 1 to 5
GAP = 8


def enabled() -> bool:
    return _on


def set_enabled(on: bool):
    """Turn every help bubble on or off (off also takes away the one on screen)."""
    global _on
    _on = bool(on)
    if not _on:
        hide()


def hide():
    """Take away the bubble on screen, if there is one."""
    if _current is not None:
        _current._hide()


def place(pointer, size, screen, area=None, big=False):
    """Where the top left of a bubble of `size` goes: pointer (x, y), size (w, h), screen (w, h), area the
    (x, y, w, h) of the widget on screen. Returns (x, y). Never under the pointer; on a big widget never over it
    if the screen has room outside it."""
    (mx, my), (w, h), (sw, sh) = pointer, size, screen
    if big and area:
        ax, ay, aw, ah = area
        x = max(GAP, min(mx - w // 2, sw - w - GAP))
        if ay + ah + GAP + h <= sh - GAP:                      # below the surface
            return x, ay + ah + GAP
        if ay - GAP - h >= GAP:                                # above it
            return x, ay - GAP - h
        y = max(GAP, min(my - h // 2, sh - h - GAP))
        if ax + aw + GAP + w <= sw - GAP:                      # to its right
            return ax + aw + GAP, y
        if ax - GAP - w >= GAP:                                # to its left
            return ax - GAP - w, y
        # no room outside: the corner of the surface furthest from the pointer
        cx = ax + GAP if mx > ax + aw // 2 else ax + aw - w - GAP
        cy = ay + GAP if my > ay + ah // 2 else ay + ah - h - GAP
        return max(0, cx), max(0, cy)
    x, y = mx + 14, my + 18
    if x + w > sw - GAP:
        x = mx - w - 14                                        # to the left of the pointer, not under it
    if y + h > sh - GAP:
        y = my - h - 14                                        # above it
    return max(0, x), max(0, y)


class Tooltip:
    """The bubble of one widget. `always`: it shows even while the bubbles are switched off (the switch's own)."""
    DELAY = 550                             # ms the pointer must rest
    DELAY_BIG = 1000                        # on a big surface
    LIFE = 9000                             # ms before it goes by itself
    MOVED = 6                               # pixels the pointer may move with the bubble up

    def __init__(self, widget, text, always=False):
        self.widget, self.text, self.always = widget, text, always
        self.box = self.job = self.life = None
        self.at = (0, 0)
        widget.bind('<Enter>', self._enter, add='+')
        widget.bind('<Leave>', self._leave, add='+')
        widget.bind('<Motion>', self._moved, add='+')
        widget.bind('<ButtonPress>', self._leave, add='+')
        widget.bind('<MouseWheel>', self._leave, add='+')
        widget.bind('<KeyPress>', self._leave, add='+')
        widget.bind('<Destroy>', self._leave, add='+')

    # ── events ──────────────────────────────────────────────────────────────
    def _enter(self, e=None):
        self._leave()
        self._arm(e)

    def _leave(self, e=None):
        self._cancel()
        self._hide()

    def _moved(self, e):
        if e.state & BUTTONS_DOWN:                       # painting or dragging: nothing is shown
            self._leave()
            return
        if self.box is not None:
            if abs(e.x_root - self.at[0]) + abs(e.y_root - self.at[1]) <= self.MOVED:
                return
            self._hide()
        self._arm(e)

    # ── showing ─────────────────────────────────────────────────────────────
    def big(self) -> bool:
        """A surface to draw or edit on, where a bubble next to the pointer would cover the work."""
        try:
            return self.widget.winfo_width() >= theme.px(180) and self.widget.winfo_height() >= theme.px(110)
        except tk.TclError:
            return False

    def _arm(self, e=None):
        self._cancel()
        if (_on or self.always) and self.text:
            try:
                self.job = self.widget.after(self.DELAY_BIG if self.big() else self.DELAY, self._show)
            except tk.TclError:
                self.job = None

    def _cancel(self):
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def _show(self):
        global _current
        self.job = None
        if not self.text or not (_on or self.always):
            return
        if _current is not None:
            _current._hide()
        try:
            mx, my = self.widget.winfo_pointerxy()
            box = tk.Toplevel(self.widget)
            box.wm_overrideredirect(True)
            box.configure(bg=theme.C['line'])
            tk.Label(box, text=self.text, bg=theme.C['raised'], fg=theme.C['text'], justify='left',
                     wraplength=theme.px(340), padx=theme.px(10), pady=theme.px(6), font=(theme.FONT, 9)).pack(padx=1, pady=1)
            box.update_idletasks()
            w, h = box.winfo_reqwidth(), box.winfo_reqheight()
            area = (self.widget.winfo_rootx(), self.widget.winfo_rooty(), self.widget.winfo_width(), self.widget.winfo_height())
            x, y = place((mx, my), (w, h), (box.winfo_screenwidth(), box.winfo_screenheight()), area, self.big())
            box.wm_geometry(f'+{x}+{y}')
        except tk.TclError:
            return
        self.box, self.at = box, (mx, my)
        _current = self
        self.life = self.widget.after(self.LIFE, self._hide)

    def _hide(self):
        global _current
        if self.life is not None:
            try:
                self.widget.after_cancel(self.life)
            except tk.TclError:
                pass
            self.life = None
        if self.box is not None:
            try:
                self.box.destroy()
            except tk.TclError:
                pass
            self.box = None
        if _current is self:
            _current = None


def tip(widget, text, always=False):
    """Explain a widget when the pointer rests on it. A second call changes the words."""
    if not text:
        return widget
    old = getattr(widget, '_tooltip', None)
    if old is not None:
        old.text = text
    else:
        widget._tooltip = Tooltip(widget, text, always)
    return widget
