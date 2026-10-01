"""The original's animations (FUNCS.CPP / FUNCS2.CPP), ported call for call.

Each animation is a generator. It draws through `h.g` (a engine.bgi.BGI on the real screen), plays
tones with `h.asound(freq)` / `h.nosound()`, and yields every delay() in milliseconds, so the caller
decides how to wait. A few animations also redraw a square (`h.clean2(x, y)`), the hero
(`h.guy2(x, y)`), or move the hero partway through (`h.move_hero(x, y)`).

Positions are 1-based screen squares, as in the original (`i = (x - 1) * 40`). Every function
is checked against TheQuest.exe by TheQuestClassic/tools/re/verify_anims.py: same BGI calls, tones and delays, in
the same order, with the same rand() draws.
"""
from __future__ import annotations

from . import rules


class Pace(int):
    """A wait the original doesn't have: some of its wipes draw as fast as the PC could, so their speed
    was the machine's. The port paces them (the verifier leaves these out of the delay() record)."""


class Host:
    """What an animation needs from the game. The game's own host draws on the screen and plays
    the speaker; the verifier's host records calls."""

    def __init__(self, g):
        self.g = g

    def asound(self, freq):
        pass

    def nosound(self):
        pass

    def clean2(self, x, y):
        pass

    def guy2(self, x, y):
        pass

    def move_hero(self, x, y):
        pass


def _px(x, y):
    return (x - 1) * 40, (y - 1) * 40


def _hit_lines(g, i, ii, where):
    """The white attack stroke of ahit()/bhit()/bhit2(): where 1-4 = from the right, below, left,
    above."""
    if where == 7:                               # FPS mode: a blow from behind, a stroke from each side
        _hit_lines(g, i, ii, 1)
        _hit_lines(g, i, ii, 3)
        return
    if where == 3:
        g.setcolor(15)
        g.line(i + 1, ii + 20, i + 22, ii + 20)
        g.line(i + 1, ii + 19, i + 22, ii + 19)
        g.line(i + 6, ii + 17, i + 6, ii + 22)
    if where == 1:
        g.setcolor(15)
        g.line(i + 38, ii + 20, i + 20, ii + 20)
        g.line(i + 38, ii + 19, i + 20, ii + 19)
        g.line(i + 33, ii + 17, i + 33, ii + 22)
    if where == 2:
        g.setcolor(15)
        g.line(i + 20, ii + 38, i + 20, ii + 20)
        g.line(i + 19, ii + 38, i + 19, ii + 20)
        g.line(i + 17, ii + 35, i + 22, ii + 35)
    if where == 4:
        g.setcolor(15)
        g.line(i + 20, ii + 1, i + 20, ii + 20)
        g.line(i + 19, ii + 1, i + 19, ii + 20)
        g.line(i + 17, ii + 6, i + 22, ii + 6)


# ── casting and hits ───────────────────────────────────────────────────────────
def dcast2(h, x, y):
    """Blue/white eyes flicker: a creature casts a spell."""
    g = h.g
    i, ii = _px(x, y)
    for u in range(10):
        g.setcolor(1)
        g.setfillstyle(1, 1)
        g.fillellipse(i + 13, ii + 22, 3, 3)
        g.fillellipse(i + 27, ii + 22, 3, 3)
        h.asound(u * 20 + 300)
        yield 25
        g.setcolor(15)
        g.setfillstyle(1, 15)
        g.fillellipse(i + 13, ii + 22, 3, 3)
        g.fillellipse(i + 27, ii + 22, 3, 3)
        h.asound(u * 20 + 400)
        yield 10
    h.nosound()


def ahit(h, x, y, where, t):
    """Melee blow on square (x, y); t = 1 is a hit (high tone), else a miss."""
    g = h.g
    i, ii = _px(x, y)
    t = 600 if t == 1 else 100
    _hit_lines(g, i, ii, where)
    h.asound(t)
    yield 50
    h.nosound()


def bhit(h, x, y, where):
    """Shield block (grey), or where = 5: a spell absorbed (white/yellow); 6: no stroke."""
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(7)
    if where == 5:
        g.setcolor(15)
    g.setfillstyle(1, 15)
    if where == 5:
        g.setfillstyle(1, 14)
    g.fillellipse(i + 20, ii + 20, 7, 7)
    g.setfillstyle(1, 7)
    if where == 5:
        g.setfillstyle(1, 15)
    g.fillellipse(i + 20, ii + 20, 1, 1)
    _hit_lines(g, i, ii, where)
    h.asound(300)
    yield 50
    if where == 5:
        yield 100
    h.nosound()


def bhit2(h, x, y, where):
    """bhit() in brown: a block by a wooden shield."""
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(15)
    if where == 5:
        g.setcolor(15)
    g.setfillstyle(1, 6)
    if where == 5:
        g.setfillstyle(1, 14)
    g.fillellipse(i + 20, ii + 20, 7, 7)
    g.setfillstyle(1, 7)
    if where == 5:
        g.setfillstyle(1, 15)
    g.fillellipse(i + 20, ii + 20, 1, 1)
    _hit_lines(g, i, ii, where)
    h.asound(300)
    yield 50
    h.asound(450)
    yield 50
    if where == 5:
        yield 100
    h.nosound()
    yield 50


def sthit(h, x, y, who):
    """A sling stone lands (who = 1: on the hero, faster)."""
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(0)
    g.setfillstyle(1, 8)
    g.fillellipse(i + 20, ii + 15, 2, 2)
    h.asound(450)
    yield 25 - who * 12
    h.asound(350)
    yield 35 - who * 17
    h.nosound()


def arhit(h, x, y, who):
    """An arrow lands."""
    g = h.g
    i, ii = _px(x, y)
    ii -= 8
    g.setcolor(0)
    g.line(i + 19, ii + 10, i + 21, ii + 20)
    g.line(i + 19, ii + 10, i + 17, ii + 9)
    g.line(i + 19, ii + 10, i + 20, ii + 9)
    g.putpixel(i + 21, ii + 20, 7)
    h.asound(550)
    yield 25 - who * 12
    h.asound(450)
    yield 35 - who * 17
    h.nosound()


def bolthit(h, x, y, who):
    """A crossbow bolt lands (drawn dark grey on a yellow background)."""
    g = h.g
    i, ii = _px(x, y)
    ii -= 8
    c = g.getpixel(i + 20, ii + 29)
    g.setcolor(7)
    if c == 14:
        g.setcolor(8)
    ii += 5
    g.line(i + 18, ii + 13, i + 23, ii + 18)
    h.asound(350)
    yield 25 - who * 12
    h.asound(250)
    yield 35 - who * 17
    h.nosound()


# ── spells ────────────────────────────────────────────────────────────────────
def _burst(h, x, y, n, first, second, who):
    g = h.g
    i, ii = _px(x, y)
    for w in range(n):
        h.asound(first[0])
        first[1](g)
        g.fillellipse(i + 20, ii + 20, w, w)
        yield 25 - who * 12
        h.asound(second[0])
        second[1](g)
        g.fillellipse(i + 20, ii + 20, w, w)
        yield 10 - who * 5
    h.nosound()


def afireball(h, x, y, who):
    """A red ball grows over 8 frames (who = 1: cast at the hero, faster)."""
    h.g.setcolor(4)
    yield from _burst(h, x, y, 8, (350, lambda g: g.setfillstyle(1, 4)), (850, lambda g: g.setfillstyle(1, 0)), who)


def aflame(h, x, y, who):
    h.g.setcolor(4)
    yield from _burst(h, x, y, 20, (350, lambda g: g.setfillstyle(1, 4)), (850, lambda g: g.setfillstyle(1, 0)), who)


def agflame(h, x, y, who):
    """Green flame."""
    def green(g):
        g.setfillstyle(1, 10)
        g.setcolor(10)
    yield from _burst(h, x, y, 8, (550, lambda g: g.setfillstyle(1, 0)), (750, green), who)


def _glow(h, x, y, r, n):
    """aheal()/aheal2()/arestore()/acure(): a blue and white disc flickers n times."""
    g = h.g
    i, ii = _px(x, y)
    for _ in range(n):
        g.setcolor(1)
        h.asound(500)
        g.setfillstyle(1, 1)
        g.fillellipse(i + 20, ii + 20, r, r)
        yield 25
        h.asound(500)
        g.setfillstyle(1, 15)
        g.setcolor(15)
        g.fillellipse(i + 20, ii + 20, r, r)
        yield 10
    h.asound(550)
    yield 50
    h.asound(700)
    yield 50
    h.nosound()


def aheal(h, x, y):
    yield from _glow(h, x, y, 7, 20)


def aheal2(h, x, y):
    yield from _glow(h, x, y, 5, 5)


def arestore(h, x, y):
    yield from _glow(h, x, y, 10, 25)


def acure(h, x, y):
    yield from _glow(h, x, y, 15, 30)


def aicering(h, x, y):
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(1)
    g.setfillstyle(1, 1)
    g.setlinestyle(0, 0, 3)
    h.asound(300)
    yield 100
    g.ellipse(i + 20, ii + 31, 0, 360, 15, 5)
    g.setcolor(15)
    yield 100
    g.ellipse(i + 20, ii + 28, 0, 360, 15, 5)
    g.putpixel(i + 20, ii + 22, 0)
    yield 100
    h.nosound()
    g.setlinestyle(0, 0, 1)


def ablackward(h, x, y):
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(4)
    spots = ((10, 10), (10, 30), (30, 10), (30, 30))
    for _ in range(10):
        g.setfillstyle(1, 0)
        for dx, dy in spots:
            g.fillellipse(i + dx, ii + dy, 8, 8)
        h.asound(200)
        yield 5
        g.setfillstyle(1, 4)
        for dx, dy in spots:
            g.fillellipse(i + dx, ii + dy, 8, 8)
        h.asound(300)
        yield 5
    h.nosound()


def ainvisibility(h, x, y):
    """The square flashes black and white, then stays white."""
    g = h.g
    i, ii = _px(x, y)
    g.setfillstyle(1, 15)
    for _ in range(20):
        h.asound(300)
        g.setfillstyle(1, 0)
        g.bar(i, ii, i + 39, ii + 39)
        yield 25
        h.asound(400)
        g.setfillstyle(1, 15)
        g.bar(i, ii, i + 39, ii + 39)
        yield 10
    h.asound(750)
    yield 50
    h.asound(800)
    yield 50
    h.nosound()


def _dark_circle(h, i, ii, n, tone):
    g = h.g
    g.setcolor(0)
    g.setfillstyle(1, 0)
    for k in range(n):
        h.asound(tone(k))
        g.fillellipse(i + 20, ii + 20, k + 2, k + 2)
        yield 100
    h.nosound()


def asskeleton(h, x, y, wh):
    """A black circle opens and a skeleton rises: wh = 1 with sword and shield (summoned),
    2 a plain skeleton, 3 only the circle."""
    g = h.g
    i, ii = _px(x, y)
    yield from _dark_circle(h, i, ii, 12, lambda k: 100 if k % 2 == 0 else 150)
    if wh == 1:
        g.setcolor(15)
        g.rectangle(i + 18, ii + 15, i + 22, ii + 10)
        g.setfillstyle(1, 15)
        g.floodfill(i + 20, ii + 13, 15)
        g.putpixel(i + 19, ii + 11, 0)
        g.putpixel(i + 21, ii + 11, 0)
        g.setfillstyle(1, 0)
        g.fillellipse(i + 20, ii + 14, 2, 2)
        g.setcolor(15)
        for a, b, c, d in ((18, 30, 14, 39), (22, 30, 26, 39), (20, 15, 20, 30), (16, 18, 24, 18),
                           (16, 21, 24, 21), (16, 24, 24, 24), (16, 27, 24, 27), (18, 29, 22, 29),
                           (18, 30, 22, 30), (16, 18, 12, 25), (24, 18, 28, 25)):
            g.line(i + a, ii + b, i + c, ii + d)
        g.setcolor(7)
        g.line(i + 13, ii + 27, i + 9, ii + 14)
        g.line(i + 11, ii + 26, i + 14, ii + 24)
        g.setcolor(7)
        g.setfillstyle(1, 6)
        g.fillellipse(i + 28, ii + 25, 4, 4)
        g.setfillstyle(1, 7)
        g.fillellipse(i + 28, ii + 25, 1, 1)
    if wh == 2:
        g.setcolor(15)
        for a, b, c, d in ((16, 15, 24, 15), (16, 18, 21, 18), (16, 21, 24, 21), (18, 24, 24, 24),
                           (17, 27, 21, 27), (20, 12, 20, 30), (18, 29, 22, 29), (18, 30, 22, 30),
                           (18, 30, 14, 39), (22, 30, 26, 39)):
            g.line(i + a, ii + b, i + c, ii + d)
        ii -= 3
        g.setcolor(15)
        g.rectangle(i + 18, ii + 15, i + 22, ii + 10)
        g.setfillstyle(1, 15)
        g.floodfill(i + 20, ii + 13, 15)
        g.putpixel(i + 19, ii + 11, 0)
        g.putpixel(i + 21, ii + 11, 0)
        g.setfillstyle(1, 0)
        g.fillellipse(i + 20, ii + 14, 2, 2)
        for a in (19, 21, 18, 22):
            g.putpixel(i + a, ii + 11, 4)
        g.setcolor(15)
        g.line(i + 16, ii + 18, i + 14, ii + 22)
        g.line(i + 24, ii + 18, i + 29, ii + 26)
    yield 100


def astoneknight(h, x, y):
    g = h.g
    i, ii = _px(x, y)
    yield from _dark_circle(h, i, ii, 15, lambda k: 100 if k % 2 == 0 else 150)
    g.setfillstyle(1, 8)
    for a, b, c, d in ((15, 39, 19, 29), (21, 39, 25, 29), (15, 10, 25, 29), (17, 10, 23, 3), (25, 10, 31, 13),
                       (28, 13, 31, 22), (15, 10, 9, 13), (12, 13, 9, 22)):
        g.bar(i + a, ii + b, i + c, ii + d)
    g.setcolor(0)
    for a, b, c, d in ((15, 39, 19, 29), (21, 39, 25, 29), (15, 39, 19, 35), (21, 39, 25, 35), (15, 10, 25, 29),
                       (17, 10, 23, 3), (25, 10, 31, 13), (28, 13, 31, 19), (15, 10, 9, 13), (12, 13, 9, 19),
                       (27, 22, 31, 19), (13, 22, 9, 19)):
        g.rectangle(i + a, ii + b, i + c, ii + d)
    g.line(i + 17, ii + 7, i + 23, ii + 7)
    g.line(i + 17, ii + 6, i + 23, ii + 6)


def asscorpion(h, x, y):
    g = h.g
    i, ii = _px(x, y)
    yield from _dark_circle(h, i, ii, 12, lambda k: 100 if k % 2 == 0 else 150)
    g.setfillstyle(1, 0)
    g.setcolor(0)
    g.fillellipse(i + 20, ii + 22, 1, 4)
    g.arc(i + 20, ii + 15, 180, 0, 3)
    g.arc(i + 20, ii + 22, 0, 180, 3)
    g.arc(i + 20, ii + 26, 0, 180, 3)
    g.arc(i + 23, ii + 26, 180, 20, 3)


def ainferno(h, x, y, who):
    """Ten red bursts at random spots around the square (uses rand())."""
    g = h.g
    bi, bii = _px(x, y)
    g.setcolor(4)
    for _ in range(10):
        i = rules.random(20) + bi - 10
        ii = rules.random(20) + bii - 10
        for w in range(8):
            h.asound(350)
            g.setfillstyle(1, 0)
            g.fillellipse(i + 20, ii + 20, w, w)
            yield 10 - who * 9
            h.asound(850)
            g.setfillstyle(1, 4)
            g.fillellipse(i + 20, ii + 20, w, w)
            yield 4 - who * 3
        h.nosound()


def athunder(h, x, y):
    """One thick white lightning bolt with a falling tone (uses rand())."""
    g = h.g
    i, ii = _px(x, y)
    yield 100
    r = rules.random(11) - 5
    g.setlinestyle(0, 0, 3)
    g.setcolor(15)
    g.line(i + r + 31, ii + 4, i + r + 15, ii + 20)
    for jj in range(10):
        h.asound(200 - jj * 4)
        yield 5
    g.line(i + r + 15, ii + 20, i + r + 30, ii + 20)
    for jj in range(10):
        h.asound(200 - jj * 4)
        yield 5
    g.line(i + r + 30, ii + 20, i + r + 14, ii + 36)
    h.asound(90)
    yield 50
    h.nosound()
    g.setlinestyle(0, 0, 1)
    yield 10


def alightning(h, x, y, who):
    """Lightning, drawn as double 1-pixel lines: 3 strikes on a creature, 1 on the hero (who = 1).
    The square is redrawn after each strike (and the hero, if it was them)."""
    g = h.g
    i, ii = _px(x, y)
    for _ in range(3 - 2 * who):
        r = rules.random(11) - 5
        g.setcolor(15)
        g.line(i + r + 31, ii + 4, i + r + 15, ii + 20)
        g.line(i - 1 + r + 31, ii + 4, i - 1 + r + 15, ii + 20)
        for jj in range(20):
            h.asound(500 - jj * 4)
            yield 5
        g.line(i + r + 15, ii + 20, i + r + 30, ii + 20)
        g.line(i - 1 + r + 15, ii + 20, i - 1 + r + 30, ii + 20)
        for jj in range(10):
            h.asound(500 - jj * 4)
            yield 5
        g.line(i + r + 30, ii + 20, i + r + 14, ii + 36)
        g.line(i - 1 + r + 30, ii + 20, i - 1 + r + 14, ii + 36)
        h.asound(90)
        yield 50
        h.nosound()
        h.clean2(x, y)
        if who == 1:
            h.guy2(x, y)
        else:
            yield 100


def ashield(h, x, y, kind):
    """A yellow (kind 1) or red (kind 2) disc grows inside a ring."""
    g = h.g
    i, ii = _px(x, y)
    c = 4 if kind == 2 else 14
    for k in range(18):
        for _ in range(2):
            h.asound(350)
            g.setcolor(c)
            g.setfillstyle(1, c)
            g.fillellipse(i + 20, ii + 20, k, k)
            for r in (18, 17, 16):
                g.ellipse(i + 20, ii + 20, 0, 360, r, r)
            yield 10
    h.nosound()


def adeteriorate(h, x, y, dur):
    g = h.g
    i, ii = _px(x, y)
    g.setfillstyle(1, 15)
    n = int(dur / 2) + 1
    for _ in range(n):
        h.asound(300)
        g.setfillstyle(1, 0)
        g.bar(i, ii, i + 39, ii + 39)
        yield 25
        h.asound(250)
        g.setfillstyle(1, 2)
        g.bar(i, ii, i + 39, ii + 39)
        h.asound(150)
        yield 40
        g.setfillstyle(1, 4)
        g.bar(i, ii, i + 39, ii + 39)
        yield 40
    h.asound(50)
    yield 50
    h.asound(100)
    yield 50
    h.nosound()


_QUAKE = ((26, 0, 18, 10), (18, 10, 19, 16), (19, 16, 16, 25), (16, 25, 20, 34), (20, 34, 16, 38))


def aearthq(h, x, y):
    """The square flashes yellow while a crack shakes across it."""
    g = h.g
    i, ii = _px(x, y)
    for k in range(10):
        g.setfillstyle(1, 0)
        if k % 2 == 1:
            g.setfillstyle(1, 14)
        g.bar(i, ii, i + 39, ii + 39)
        h.asound(100)
        yield 15
        g.setlinestyle(0, 0, 3)
        g.setcolor(0)
        i += 2 * k - 11
        i += 2
        for a, b, c, d in _QUAKE:
            g.line(i + a, ii + b, i + c, ii + d)
        g.setcolor(14)
        i += 2
        for a, b, c, d in _QUAKE:
            g.line(i + a, ii + b, i + c, ii + d)
        g.setlinestyle(0, 0, 1)
        i -= 4
        i -= 2 * k - 11
        h.asound(350)
        yield 25
    h.nosound()


def adrain(h, x, y, wh):
    """Life drain: wh 1 = the white disc shrinks away (the victim), 2 = it fills up (the drainer).
    3 and 4 are the same, faster (cast by a monster)."""
    g = h.g
    off = 0
    if wh > 2:
        off = 75
        wh -= 2
    i, ii = _px(x, y)
    g.setcolor(15)
    g.setfillstyle(1, 15)
    g.fillellipse(i + 20, ii + 20, 11, 11)
    g.setfillstyle(1, 0)
    if wh == 1:
        for w in range(11):
            g.setcolor(0)
            g.setfillstyle(1, 0)
            if w % 2 == 1:
                g.setfillstyle(1, 15)
            g.setcolor(15)
            g.fillellipse(i + 20, ii + 20, w + 1, w + 1)
            h.asound(150 - w * 10)
            if w % 2 == 1:
                h.asound(450 - w * 10)
            yield 100 - off
    elif wh == 2:
        for w in range(11):
            g.setfillstyle(1, 0)
            g.setcolor(0)
            g.fillellipse(i + 20, ii + 20, 11 - w, 11 - w)
            h.asound(w * 20 + 40)
            if w % 2 == 1:
                h.asound(w * 20 + 340)
            yield 100 - off
            g.setfillstyle(1, 1)
            g.setcolor(1)
            if w % 2 == 1:
                g.setfillstyle(1, 15)
            g.setcolor(15)
            g.fillellipse(i + 20, ii + 20, 11, 11)
    h.nosound()


def adeaths(h, x, y):
    """Death Spell: a black pit opens, then a red/black skull flashes."""
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(0)
    g.setfillstyle(1, 0)
    for k in range(400):
        g.fillellipse(i + 20, ii + 31, k // 35 + 2, k // 55 + 1)
        h.asound(600 - k)
        yield 2
    g.setcolor(0)
    for k in range(30):
        g.setfillstyle(1, 0)
        if k % 2 == 1:
            g.setfillstyle(1, 4)
        g.bar(i, ii, i + 39, ii + 39)
        h.asound(100)
        yield 7
        g.arc(i + 20, ii + 23, 180, 360, 16)
        for a, b, c, d in ((4, 23, 10, 10), (10, 10, 15, 8), (15, 8, 22, 7), (22, 7, 29, 9), (29, 9, 35, 14),
                           (35, 14, 36, 23)):
            g.line(i + a, ii + b, i + c, ii + d)
        g.setfillstyle(1, 0)
        g.floodfill(i + 20, ii + 25, 0)
        h.asound(180)
        yield 12
    h.nosound()


def adarkhour(h, x, y):
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(15)
    d = 10
    for w in range(16):
        for tone in (400, 300):
            g.setcolor(0)
            g.setfillstyle(1, 0)
            g.fillellipse(i + 20, ii + 20, w + 3, w + 3)
            g.setcolor(1)
            h.asound(tone)
            yield 10 // d
            g.setfillstyle(1, 1)
            g.fillellipse(i + 20, ii + 20, w + 3, w + 3)
        h.asound(400)
        yield 5 // d
    h.nosound()


# ── teleporters ───────────────────────────────────────────────────────────────
def _rings(h, i, ii):
    g = h.g
    for dy in (9, 18, 27):
        g.ellipse(i + 20, ii + dy, 0, 360, 10, 2)
        yield 250


def teleporter1(h, x, y):
    """Stepping on a teleporter pad (the level 5 jump itself is done by the game)."""
    g = h.g
    i, ii = _px(x, y)
    yield 500
    h.asound(500)
    g.setcolor(1)
    g.setfillstyle(1, 15)
    yield from _rings(h, i, ii)
    h.nosound()


def teleporter2(h, x, y):
    """Arriving by teleporter."""
    g = h.g
    i, ii = _px(x, y)
    g.setcolor(1)
    h.asound(500)
    yield from _rings(h, i, ii)
    h.nosound()


def ateleport(h, x, y, ax, ay):
    """The Teleport spell: rings at the hero's square (ax, ay), the hero moves to (x, y), rings again."""
    g = h.g
    for n, (px, py) in enumerate(((ax, ay), (x, y))):
        if n:
            h.move_hero(x, y)
            yield 200
        i, ii = _px(px, py)
        h.asound(500)
        g.setcolor(1)
        g.setfillstyle(1, 15)
        yield from _rings(h, i, ii)
        h.nosound()
        h.clean2(px, py)
    h.guy2(x, y)


# ── message-strip animations ───────────────────────────────────────────────────
def _strip(g):
    g.setfillstyle(1, 0)
    g.bar(0, 410, 640, 500)
    g.settextstyle(7, 0, 2)


def alevelup(h):
    g = h.g
    _strip(g)
    g.setcolor(2)
    g.outtextxy(9, 413, 'Level Up!')
    return
    yield


def ampoisoned2(h, n):
    """n = 1: poisoned, else cured."""
    g = h.g
    _strip(g)
    if n == 1:
        g.setcolor(4)
        g.outtextxy(9, 413, 'You have been poisoned!')
        h.asound(400)
        yield 300
        h.asound(300)
        yield 300
        h.asound(400)
    else:
        g.setcolor(2)
        g.outtextxy(9, 413, 'The poison is cured!')
        h.asound(400)
        yield 300
        h.asound(500)
        yield 300
        h.asound(600)
    yield 300
    h.nosound()


def dying2(h):
    g = h.g
    g.setfillstyle(1, 0)
    g.setcolor(4)
    g.bar(0, 410, 640, 500)
    g.settextstyle(7, 0, 2)
    g.outtextxy(9, 413, 'You are bleeding!')
    for f in (400, 300, 400):
        h.asound(f)
        yield 300
    h.nosound()


DEATH_LINES = ('You fell to the ground at the feet of your enemies...', 'How does the agony of defeat taste?',
               'Life is a dream. One day we must all wake up. (WoT)')


def death2(h):
    g = h.g
    g.setfillstyle(1, 0)
    g.setcolor(15)
    g.bar(0, 410, 640, 500)
    g.settextstyle(7, 0, 2)
    g.outtextxy(9, 413, DEATH_LINES[rules.random(3)])
    for f in (200, 150, 100):
        h.asound(f)
        yield 1000
    h.nosound()
    yield 3000


# ── short sequences written inline in main2() and friends ─────────────────────
def tones(h, *seq):
    """asound(f); delay(ms) for each (f, ms) pair, then nosound(): the game's one-off beeps."""
    for f, ms in seq:
        h.asound(f)
        yield ms
    h.nosound()


def pause(h, ms):
    """A bare delay(ms)."""
    yield ms


def screen_flash(h, colour):
    """The map flashes colour/black 30 times with a rising tone: the Deceiver (45) turning summons
    into demons (purple, main2()), and Fatebringer appearing on level 6 (green, deadenemycheck()).
    The game redraws the map afterwards."""
    g = h.g
    for j in range(30):
        g.setfillstyle(1, colour)
        if j % 2 == 1:
            g.setfillstyle(1, 0)
        g.bar(0, 0, 400, 400)
        h.asound(j * 10 + 100)
        yield 30
    h.nosound()


def death_wipe(h):
    """death(), after 'No' to loading: a black box grows from the middle of the screen."""
    g = h.g
    g.setfillstyle(1, 0)
    for i in range(350):
        g.bar(320 - i, 250 - i, 320 + i, 250 + i)
        yield Pace(2)                                   # about 0.7 s


def story_circle(h):
    """story(): a black circle grows from the middle of the screen until everything is black, before
    a story page shows and again as it closes."""
    g = h.g
    g.setcolor(0)
    g.setfillstyle(1, 0)
    for i in range(410):
        g.fillellipse(320, 250, i, i)
        yield Pace(1)                                   # with the drawing, about 0.9 s


# ── the jingles (song_key(), song_jazz(), song_bevcop()) ────────────────────────
# Scores recorded from the exe: aF = asound(F), dMS = delay(MS), n = nosound().
SONGS = {
    'song_key': (
        'a415 d113 n d38 a330 d113 n d38 a415 d113 n d38 a494 d113 n d38 a415 d113 n d38 a494 d113 '
        'n d38 a659 d113 n d38 '
    ),
    'song_jazz': (
        'a494 d150 n a659 d150 n a784 d150 n a880 d150 n a932 d150 n a988 d150 n a932 d150 n a880 '
        'd150 n a784 d300 n a494 d300 n a587 d300 n a659 d900 n '
    ),
    'song_bevcop': (
        'a370 d175 n d25 n d200 a440 d263 n d38 a370 d88 n d13 a370 d88 n d13 a370 d88 n d13 a494 '
        'd175 n d25 a370 d175 n d25 a330 d175 n d25 a370 d175 n d25 n d200 a554 d175 n d25 a370 d88 '
        'n d13 a370 d88 n d13 a370 d88 n d13 a587 d175 n d25 a554 d175 n d25 a440 d175 n d25 a370 '
        'd175 n d25 a554 d175 n d25 a740 d175 n d25 a370 d88 n d13 a330 d88 n d13 a330 d88 n d13 '
        'a330 d88 n d13 a277 d175 n d25 a415 d175 n d25 a370 d175 n d25 n '
    ),
}


def _score(h, score):
    for tok in score.split():
        if tok[0] == 'a':
            h.asound(int(tok[1:]))
        elif tok[0] == 'd':
            yield int(tok[1:])
        else:
            h.nosound()


def song_key(h):
    yield from _score(h, SONGS['song_key'])


def song_jazz(h):
    yield from _score(h, SONGS['song_jazz'])


def song_bevcop(h):
    yield from _score(h, SONGS['song_bevcop'])


# ── the hero ───────────────────────────────────────────────────────────────────
HERO_COLOURS = {1: 5, 2: 4, 3: 8, 4: 15}           # Knight purple, Mage red, Rogue grey, Monk white


def draw_guy2(g, x, y, htype, invisible, poisoned, killer, powboost, shield, fshield, look=None):
    """guy2(): the hero at screen square (x, y). While invisible only the eyes are drawn. The eyes
    are green when poisoned, red with the killer switch on, light red under a Berserker potion; the
    Shield spell adds a yellow ring, Shield of Fire a red one."""
    i, ii = (x - 1) * 40, y * 40 - 39
    c = HERO_COLOURS.get(htype, 0) if look is None else look.get('colour', 0)
    armed = htype == 1 if look is None else look.get('shield_and_sword', False)
    if invisible <= 0:
        g.setfillstyle(1, 7)
        g.setcolor(7)
        for col in (7, c):
            if col == c:
                g.setcolor(c)
            g.line(i + 16, ii + 10, i + 24, ii + 10)
            g.line(i + 16, ii + 10, i + 5, ii + 38)
            g.line(i + 24, ii + 10, i + 35, ii + 38)
            g.ellipse(i + 20, ii + 38, 0, 180, 15, 4)
            if col == c:
                g.setfillstyle(1, c)
            g.floodfill(i + 20, ii + 20, col)
        g.setcolor(c)
        for a, b in ((7, 34), (7, 35), (6, 36), (6, 37), (33, 34), (33, 35), (34, 36), (34, 37)):
            g.putpixel(i + a, ii + b, c)
        g.setfillstyle(1, 0)
        g.fillellipse(i + 20, ii + 18, 4, 11)
        g.setlinestyle(0, 0, 1)
        g.setcolor(0)
        g.setfillstyle(1, c)
        g.bar(i + 17, ii + 27, i + 23, ii + 30)
        g.setfillstyle(1, 0)
        g.line(i + 15, ii + 13, i + 13, ii + 22)
        g.line(i + 25, ii + 13, i + 27, ii + 22)
        g.setcolor(c)
        g.fillellipse(i + 20, ii + 7, 3, 4)
        g.setcolor(c)
        g.line(i + 18, ii + 4, i + 22, ii + 4)
        g.putpixel(i + 20, ii + 11, 14)
        g.setcolor(0)
        for a in (17, 23, 18, 22):
            g.line(i + a, ii + 23, i + a, ii + 38)
        g.setcolor(6)
        g.setfillstyle(1, 8)
        g.bar(i + 17, ii + 38, i + 18, ii + 38)
        g.bar(i + 23, ii + 38, i + 22, ii + 38)
        if armed:                                       # the Knight's shield and sword
            g.setcolor(15)
            g.setfillstyle(1, 4)
            g.fillellipse(i + 26, ii + 20, 5, 5)
            g.setfillstyle(1, 15)
            g.fillellipse(i + 26, ii + 20, 1, 1)
            i -= 17
            ii += 5
            g.setcolor(15)
            g.line(i + 29, ii + 17, i + 29, ii + 1)
            g.line(i + 30, ii + 17, i + 30, ii + 1)
            g.line(i + 27, ii + 15, i + 32, ii + 15)
            g.setcolor(0)
            g.line(i + 29, ii + 18, i + 29, ii + 16)
            g.line(i + 30, ii + 18, i + 30, ii + 16)
            i += 17
            ii -= 5
    eye = 15
    if poisoned > 0 and invisible == -1:
        eye = 2
    elif killer == 1:
        eye = 4
    elif powboost > 0:
        eye = 12
    for a in (18, 19, 21, 22):
        g.putpixel(i + a, ii + 7, eye)
    if shield > 0:
        for r in (18, 17, 16):
            g.setcolor(14)
            g.arc(i + 20, ii + 20, 0, 360, r)
    if fshield > 0:
        for r in (18, 16, 17):
            g.setcolor(4)
            g.arc(i + 20, ii + 20, 0, 360, r)


def guy2(h, x, y, *state):
    """draw_guy2() as an animation step (for the verifier)."""
    draw_guy2(h.g, x, y, *state)
    return
    yield


# ── message-strip warnings (each is followed by the potion belt again) ─────────
def _warn(h, colour, text):
    g = h.g
    _strip(g)
    g.setcolor(colour)
    g.outtextxy(9, 413, text)


def reput2(h, n):
    """reput(): 'Your reputation has become better!' (n > 0, rising) or '...worse!' (falling)."""
    if n > 0:
        _warn(h, 2, 'Your reputation has become better!')
        seq = (400, 500, 600)
    else:
        _warn(h, 4, 'Your reputation has become worse!')
        seq = (300, 200, 100)
    for f in seq:
        h.asound(f)
        yield 300
    h.nosound()
    yield 500


_FALL = ((400, 150), (350, 150), (300, 150), (250, 150))


def honor(h):
    """Leaving a fight with the Honor fault."""
    g = h.g
    _strip(g)
    g.setcolor(14)
    h.asound(500)
    yield 50
    g.outtextxy(9, 413, 'It is not honorable to flee from your enemy!')
    h.asound(450)
    yield 50
    yield from tones(h, *_FALL)


def cantsave(h):
    _warn(h, 14, 'You cannot save right now, there are enemies near!')
    h.asound(450)
    yield 50
    yield from tones(h, *_FALL)


def noarrows2(h):
    _warn(h, 14, 'You have run out of ammo!')
    yield from tones(h, (400, 100), (300, 150), (400, 150))


def class_change(h, t, name=None):
    """levelup(): the class follows the stats. Written over the level-up page, then a rising scale.
    The Quest Deluxe passes the name of a pack's own class."""
    g = h.g
    g.setfillstyle(1, 0)
    g.bar(0, 410, 399, 500)
    g.settextstyle(7, 0, 2)
    g.setcolor(14)
    g.outtextxy(9, 413, 'You have become a %s!' % (name or {1: 'Knight', 2: 'Mage', 3: 'Rogue', 4: 'Monk'}[t]))
    for f in (300, 400, 500, 600, 700, 800):
        h.asound(f)
        yield 300
    h.nosound()


def strip_text(h, text):
    """A white line in the message strip ('Saving. . .', 'Loading. . .')."""
    g = h.g
    g.setfillstyle(1, 0)
    g.setcolor(15)
    g.bar(0, 410, 640, 500)
    g.settextstyle(7, 0, 2)
    g.outtextxy(9, 413, text)
    return
    yield
