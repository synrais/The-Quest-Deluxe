"""The help bubbles (studio/bubbles.py): they come only when the pointer rests, go at the first move, click or key, never lie on a surface being edited,
never sit under the pointer, and one switch turns them all off.

Run:  xvfb-run -a python tests/test_bubbles.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
except Exception as e:                          # noqa: BLE001
    print(f'skipped: no tkinter or no display ({e})')
    sys.exit(0)

from studio import bubbles, theme, ui, uikit      # noqa: E402

# the one implementation behind every spelling of tip()
assert ui.tip is bubbles.tip and uikit.tip is bubbles.tip and ui.Tooltip is bubbles.Tooltip

# ── where a bubble goes ──────────────────────────────────────────────────────
SCREEN = (1000, 800)


def inside(pt, rect):
    return rect[0] <= pt[0] < rect[0] + rect[2] and rect[1] <= pt[1] < rect[1] + rect[3]


import itertools                                  # noqa: E402
for mx, my in itertools.product((0, 5, 300, 700, 990), (0, 5, 400, 790)):
    for size in ((150, 40), (340, 90)):
        x, y = bubbles.place((mx, my), size, SCREEN)
        assert not inside((mx, my), (x, y, *size)), ('under the pointer', (mx, my), size, (x, y))
        assert 0 <= x and x + size[0] <= SCREEN[0] and 0 <= y and y + size[1] <= SCREEN[1], ('off the screen', (mx, my), size, (x, y))
        area = (100, 100, 500, 400)
        x, y = bubbles.place((mx, my), size, SCREEN, area, True)
        rect = (x, y, *size)
        overlap = not (x + size[0] <= area[0] or x >= area[0] + area[2] or y + size[1] <= area[1] or y >= area[1] + area[3])
        assert not overlap, ('on the surface being edited', (mx, my), size, (x, y))
        assert 0 <= x and x + size[0] <= SCREEN[0] and 0 <= y and y + size[1] <= SCREEN[1], ('off the screen', (mx, my), size, (x, y))
        assert not inside((mx, my), rect), ('under the pointer', (mx, my), size, (x, y))
full = (0, 0, *SCREEN)                            # a surface that fills the screen: the corner furthest from the pointer
x, y = bubbles.place((100, 100), (200, 50), SCREEN, full, True)
assert x > SCREEN[0] // 2 and y > SCREEN[1] // 2, (x, y)
x, y = bubbles.place((900, 700), (200, 50), SCREEN, full, True)
assert x < SCREEN[0] // 2 and y < SCREEN[1] // 2, (x, y)
print('bubbles: a bubble is never under the pointer, never off the screen, and never on a surface being edited when the screen has room outside it: ok')

# ── on screen, with the real pointer ─────────────────────────────────────────
theme.apply(root, 'dark')
root.geometry('700x500+40+30')
bubbles.Tooltip.DELAY, bubbles.Tooltip.DELAY_BIG, bubbles.Tooltip.LIFE = 70, 140, 700
canvas = tk.Canvas(root, width=420, height=260, bg='#223')
canvas.pack(padx=20, pady=20)
button = ttk.Button(root, text='A button')
button.pack(pady=4)
bubbles.tip(canvas, 'Pencil: the left button paints.')
bubbles.tip(button, 'Does a thing.')
root.update()


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def point(widget, x, y, **kw):
    """Move the real pointer to (x, y) in the widget."""
    widget.event_generate('<Motion>', x=x, y=y, warp=True, **kw)
    root.update()


def box():
    return bubbles._current.box if bubbles._current is not None else None


def rect(b):
    return (b.winfo_rootx(), b.winfo_rooty(), b.winfo_width(), b.winfo_height())


point(canvas, 210, 130)
assert box() is None, 'not at once: the pointer must rest'
pump(60)
assert box() is None
pump(250)
b = box()
assert b is not None, 'it came once the pointer had rested'
area = (canvas.winfo_rootx(), canvas.winfo_rooty(), canvas.winfo_width(), canvas.winfo_height())
r = rect(b)
assert r[1] >= area[1] + area[3] or r[1] + r[3] <= area[1], ('over the canvas being edited', r, area)
point(canvas, 214, 131)                             # a move of a few pixels: it stays
assert box() is b
point(canvas, 300, 160)
assert box() is None, 'it goes at the first real move'
pump(60)
assert box() is None, 'and does not come back until the pointer rests again'
pump(250)
assert box() is not None
canvas.event_generate('<ButtonPress-1>', x=300, y=160)
root.update()
assert box() is None, 'a click takes it away'
point(canvas, 100, 100)
pump(450)
assert box() is not None
canvas.event_generate('<Motion>', x=110, y=110, state=0x100)       # moving with a button down (painting): nothing
root.update()
assert box() is None
pump(450)
assert box() is None, 'while a button is down, none comes'
canvas.event_generate('<ButtonRelease-1>', x=110, y=110)
point(canvas, 120, 120)
pump(450)
b = box()
assert b is not None
pump(900)
assert box() is None, 'and one that is left alone goes by itself'

point(button, 20, 10)
pump(250)
b = box()
assert b is not None, 'a small widget gets its bubble'
pointer = root.winfo_pointerxy()
assert not inside(pointer, rect(b)), 'never under the pointer'
assert rect(b)[0] >= pointer[0] and rect(b)[1] >= pointer[1], 'below and to the right of the pointer'
assert ui.tip(button, 'Does another thing.') is button and button._tooltip.text == 'Does another thing.', 'a second tip() changes the words'

# the switch
bubbles.set_enabled(False)
assert box() is None and not bubbles.enabled(), 'off takes away the one that is up'
point(button, 24, 12)
pump(300)
assert box() is None, 'off: none comes'
point(canvas, 150, 150)
pump(450)
assert box() is None
always = ttk.Button(root, text='Bubbles')
always.pack()
bubbles.tip(always, 'Click to turn the bubbles on.', always=True)
root.update()
point(always, 10, 10)
pump(250)
assert box() is not None, "the switch's own button still explains itself while they are off"
bubbles.set_enabled(True)
assert box() is None or bubbles.enabled()
point(button, 20, 10)
pump(300)
assert box() is not None, 'on again: they come again'

# a widget that goes away takes its bubble with it
b = box()
button.destroy()
root.update()
assert box() is None and not b.winfo_exists() if b is not None else True
root.destroy()
print('bubbles: they come when the pointer rests, go at a move, a click or by themselves, stay off a surface being edited, and one switch turns them off: ok')
