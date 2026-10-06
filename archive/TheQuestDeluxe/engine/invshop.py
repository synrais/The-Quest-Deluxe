"""The original's inventory and shop pages, ported call for call: inventory() (the i key, and the
shop's "Store: Sell" page) and peddler() ("Store: Buy"), with dempty(), bagdraw() and itemdisp().

Both are generators. They draw through `h.g` (engine.bgi.BGI), play tones through `h.asound()` /
`h.nosound()` and yield each delay() in milliseconds, like engine.anim. When they need a key they
yield None and are resumed with the key the original's getch() would return: letters as ASCII,
Enter 13, Esc 27, Backspace 8, and the arrows as 0 followed by the scan code (72 up, 80 down,
75 left, 77 right). They return the last key, which the callers (the RPG.CPP wrappers) use to
switch between buying and selling.

What the host provides (`h`): bag and store (dicts (column, row) -> item, the original's `bag` and
`store` matrices), inv, skill, a copy of the hero (`hero`: the original passes it by value, so
nothing the pages do to it survives), level, tell(item, column) (itemtell), price(item) (pricetell),
recompute() (the inline statusupdate() on the copy), put3(item) (drop at the hero's square) and
bagdraw(i, ii, a) (the drawing of one item).

TheQuestClassic/tools/re/verify_invshop.py runs both next to the exe with scripted keys.
"""
from __future__ import annotations

KEY = None                   # yield KEY: wait for a key (getch())

BACKPACK_ROWS = range(8, 12)
BACKPACK_COLS = range(12, 16)


def free_cell(bag, default=(0, 0)):
    """The first empty backpack cell, row by row (the loops at the end of each equip case)."""
    for ii in BACKPACK_ROWS:
        for i in BACKPACK_COLS:
            if not bag.get((i, ii), 0):
                return i, ii
    return default


# ── drawing helpers ─────────────────────────────────────────────────────────────
def dempty(g, i, ii, x, y):
    """An empty cell: 40 grey lines and a black frame."""
    px, py = i * 40 + x - 50, ii * 40 + y - 40
    g.setcolor(8)
    for q in range(40):
        g.line(px, py + q, px + 39, py + q)
    g.setcolor(0)
    g.rectangle(px, py, px + 39, py + 39)


def bagdraw(h, i, ii, a):
    """bagdraw(): the item in bag cell (i, ii) (a = 0 worn, 1 backpack) or store cell (a = 2), drawn
    by the host (the original calls one drawing routine per item; the sprites are those drawings)."""
    h.bagdraw(i, ii, a)


def icon_pos(i, ii, a):
    """Where bagdraw() puts an item's 40x40 picture."""
    x, y = (-10, 0) if a == 0 else (10, 10)
    return (i - 1) * 40 + x, (ii - 1) * 40 + y


def itemdisp(h, x, y, kind):
    """The strip under the map: the item's name (red when the hero can't use it), what it needs and
    what it gives, and a small badge for its weapon kind."""
    g = h.g
    g.setcolor(0)
    g.setfillstyle(1, 0)
    g.bar(0, 411, 399, 500)
    b = h.store.get((x, y), 0) if kind == 2 else h.bag.get((x, y), 0)
    t = h.tell
    st, intl = t(b, 1), t(b, 2)
    col = 4 if st > h.hero.str or intl > h.hero.intl else 9
    g.setcolor(col)
    g.settextstyle(1, 0, 3)
    name = h.pack.item(b).get('bag_name')
    if name:
        g.outtextxy(1, 425, name)
    if col != 4:
        g.setcolor(15)
    g.settextstyle(1, 0, 2)
    if st:
        g.outtextxy(200, 412, f'Str {st}')
        g.line(200, 435, 265, 435)
    if intl:
        g.outtextxy(200, 447, f'Int {intl}')
        g.line(200, 470, 265, 470)
    d = t(b, 4)
    if d:
        g.outtextxy(275, 412, f'Def+{d}' if d >= 0 else f'Def{d}')
    a = t(b, 12)
    if a:
        g.outtextxy(275, 412, f'Acc+{a}' if a > 0 else f'Acc {a}')
    a = t(b, 3)
    if a:
        g.outtextxy(275, 447, f'Atk+{a}' if a >= 0 else f'Atk{a}')
    a = t(b, 11)
    if a:
        g.outtextxy(275, 447, f'Dex+{a}' if a > 0 else f'Dex {a}')
    a = t(b, 5)
    if a:
        g.outtextxy(295, 412, f'WA+{a}')
    a = t(b, 6)
    if a:
        g.outtextxy(295, 447, f'MA+{a}')
    a = t(b, 7)
    if a:
        g.outtextxy(275, 412, f'Str+{a}')
    a = t(b, 8)
    if a:
        g.outtextxy(275, 447, f'Int+{a}')
    a = t(b, 9)
    if a:
        g.outtextxy(345, 430, f'P={a}' if h.pack.item_type(b) in ('weapon', 'launcher') else f'P+{a}')
    sp = t(b, 10)
    if sp == 1:                                                      # double strike: a red X
        g.setcolor(14)
        g.setfillstyle(1, 4)
        g.bar(360, 455, 379, 474)
        g.line(360, 455, 378, 473)
        g.line(360, 473, 378, 455)
    if sp in (2, 6):                                                 # parry: a shield
        g.setcolor(2)
        g.setfillstyle(1, 5)
        g.bar(360, 455, 381, 475)
        g.setcolor(15)
        g.setfillstyle(1, 4)
        g.fillellipse(370, 465, 7, 7)
        g.setfillstyle(1, 15)
        g.fillellipse(370, 465, 1, 1)
    if sp == 3:                                                      # magic: pierces armour
        g.setcolor(2)
        g.setfillstyle(1, 2)
        g.bar(360, 455, 381, 475)
        g.setcolor(0)
        g.rectangle(368, 460, 373, 470)
        g.setcolor(15)
        g.line(362, 456, 379, 474)
    if sp == 4:                                                      # ranged: a bow
        g.setcolor(2)
        g.setfillstyle(1, 3)
        g.bar(360, 455, 381, 475)
        g.setcolor(14)
        g.line(368, 466, 378, 462)
        g.setcolor(0)
        g.arc(365, 466, 320, 80, 9)
    if sp == 5:                                                      # two-handed: "2"
        g.settextstyle(1, 0, 3)
        g.setfillstyle(1, 1)
        g.bar(360, 455, 381, 475)
        g.setcolor(15)
        g.outtextxy(366, 449, '2')
        g.settextstyle(1, 0, 2)
    if sp == 6:                                                      # two-handed parry: "2" above
        g.settextstyle(1, 0, 3)
        g.setfillstyle(1, 1)
        g.bar(360, 414, 381, 434)
        g.setcolor(15)
        g.outtextxy(366, 408, '2')
        g.settextstyle(1, 0, 2)


def coin_line(h, price, colour, style=True):
    """'$price', a stack of coins and the hero's gold, at the bottom right. (inventory() leaves the
    text style as itemdisp() set it; peddler() sets it again.)"""
    g = h.g
    g.setcolor(colour)
    if style:
        g.settextstyle(1, 0, 2)
    g.outtextxy(460, 451, f'${price}')
    xx, yy = 465, 370
    g.setfillstyle(1, 5)
    g.bar(xx + 88, yy + 81, xx + 102, yy + 109)
    g.setcolor(0)
    g.setfillstyle(1, 14)
    for top, fy in ((107, 105), (104, 102), (101, 99), (98, 96), (95, 93), (92, 90), (89, 87), (86, 85)):
        g.rectangle(xx + 90, yy + top, xx + 100, yy + top - 3)
        g.floodfill(xx + (93 if fy in (105, 99, 90, 85) else 92), yy + fy, 0)
    g.setcolor(15)
    g.outtextxy(570, 451, f'{h.inv.coins}')


def cursor(g, x, y, colour, worn_offset, draw=True):
    i, ii = (x - 1) * 40 + 10, (y - 1) * 40 + 10
    if worn_offset and y < 8:
        i, ii = i - 20, ii - 10
    if colour is not None:
        g.setcolor(colour)
    if draw:
        g.rectangle(i, ii, i + 39, ii + 39)
        g.rectangle(i - 1, ii - 1, i + 40, ii + 40)


WORN = ((14, 2), (14, 4), (12, 4), (16, 4), (14, 6))


def draw_bag(h):
    g = h.g
    for i, ii in WORN:
        dempty(g, i, ii, 0, 0)
    for i, ii in WORN:
        bagdraw(h, i, ii, 0)
    for i in BACKPACK_COLS:
        for ii in BACKPACK_ROWS:
            dempty(g, i, ii, 20, 10)
            bagdraw(h, i, ii, 1)


# ── inventory() ─────────────────────────────────────────────────────────────────
def inventory(h, mode):
    """mode 1: the i key; mode 2: the shop's selling page (Backspace sells)."""
    g, bag, t = h.g, h.bag, h.tell
    g.setcolor(0)
    g.setfillstyle(1, 0)
    g.bar(411, 0, 640, 500)
    g.bar(0, 411, 640, 500)
    g.setfillstyle(6, 15)
    g.bar(400, 0, 410, 500)
    g.setcolor(15)
    g.settextstyle(4, 0, 4)
    g.outtextxy(465, 0, 'Inventory') if mode == 1 else g.outtextxy(455, 0, 'Store: Sell')
    g.settextstyle(8, 0, 1)
    g.setcolor(14)
    for label, x, y in (('Head', 507, 74), ('Arm', 430, 153), ('Arm', 590, 153), ('Body', 509, 153),
                        ('Jewelry', 495, 233)):
        g.outtextxy(x, y, label)
    draw_bag(h)
    hit, x, y = 0, 12, 8
    cursor(g, x, y, 14, False)
    quit = False
    price = 0
    a = 0
    while True:
        show = False
        if hit != 1:
            itemdisp(h, x, y, 1)
            price = 0
            if mode == 2:
                price = h.price(bag.get((x, y), 0)) * 6 // 10
                g.setfillstyle(1, 0)
                g.bar(450, 451, 640, 500)
                coin_line(h, price, 14, style=False)
        lx, ly = x, y
        hit = yield KEY
        a = hit
        redraw_cursor = True
        if hit == 75 and x != 12 and y > 7:
            x -= 1
        elif hit == 77 and x != 15 and y > 7:
            x += 1
        elif hit == 72 and y > 8:
            y -= 1
        elif hit == 80 and y != 11 and y > 7:
            y += 1
        elif hit == 72 and y == 8:
            y, x = 6, 14
        elif hit == 72 and y == 6:
            y = 4
        elif hit == 72 and y == 4:
            y, x = 2, 14
        elif hit == 80 and y == 6:
            y, x = 8, 13
        elif hit == 80 and y == 4:
            y, x = 6, 14
        elif hit == 80 and y == 2:
            y = 4
        elif hit == 77 and y == 4 and x != 16:
            x += 2
        elif hit == 75 and y == 4 and x != 12:
            x -= 2
        elif a == 98 and mode == 2:                                  # b: back to buying
            quit = True
            redraw_cursor = False
        elif a == 105 or hit == 27:                                  # i / Esc
            quit = True
        elif hit == 8 and bag.get((x, y), 0) > 0 and (mode == 1 or y < 8):
            yield from take_off(h, x, y)
            show = True
        elif hit == 8 and bag.get((x, y), 0) > 0 and mode == 2 and not h.pack.is_quest_item(bag[(x, y)]):
            bag[(x, y)] = 0                                          # sell
            h.inv.coins += price
            show = True
            yield from tones(h, (700, 100), (600, 100))
        elif hit == 13 and bag.get((x, y), 0) > 0 and mode == 1 and y >= 8 and \
                h.pack.item(bag[(x, y)]).get('use'):
            use = h.pack.item(bag[(x, y)])['use']                    # food, a bandage ...: used up, here and now
            name = h.game.item_name(bag[(x, y)])
            bag[(x, y)] = 0
            said = h.game.apply_effect(use, f'You use the {name.lower() or "item"}.')
            h.hero.life, h.hero.mana = h.game.player.hero.life, h.game.player.hero.mana     # the page's copy
            g.setfillstyle(1, 0)
            g.bar(0, 411, 640, 500)
            g.settextstyle(8, 0, 1)
            g.setcolor(10)
            g.outtextxy(12, 440, said[:72])
            show = True
            yield from tones(h, (700, 80), (800, 80))
        elif hit == 13 and bag.get((x, y), 0) > 0:
            it = bag[(x, y)]
            if t(it, 1) <= h.hero.str and t(it, 2) <= h.hero.intl:
                yield from tones(h, (500, 50), (600, 50))
                equip(h, x, y)
                h.recompute()
                show = True
            else:
                yield from tones(h, (100, 300))                      # it can't be used
        else:
            hit = 1
        if show:
            draw_bag(h)
        if redraw_cursor:                        # the colours are set even when nothing is drawn
            cursor(g, lx, ly, 0, True, draw=hit != 1)
            cursor(g, x, y, 14, True, draw=hit != 1)
        if quit:
            return a


def tones(h, *seq):
    for f, ms in seq:
        h.asound(f)
        yield ms
    h.nosound()


def take_off(h, x, y):
    """Backspace on a worn item: into the first free backpack cell (with Ambidexterity, taking off
    the main weapon brings the second weapon into the main hand); with no room, or on a backpack
    item, it is dropped on the ground (quest items, 900 and up, can't be: a beep)."""
    bag = h.bag
    q = (0, 0)
    if y < 8:
        q = free_cell(bag)
        if q != (0, 0):
            off = bag.get((16, 4), 0)
            if (x, y) == (12, 4) and h.skill.amb and h.pack.item_type(off) == 'weapon':
                bag[q] = bag[(12, 4)]
                bag[(12, 4)] = off
                bag[(16, 4)] = 0
            else:
                bag[q] = bag[(x, y)]
                bag[(x, y)] = 0
    if y >= 8 or q == (0, 0):
        if not h.pack.is_quest_item(bag[(x, y)]):
            h.put3(bag[(x, y)])
            bag[(x, y)] = 0
        else:
            yield from tones(h, (100, 300))
    h.recompute()


def swap_into(bag, slot, x, y):
    """Put bag[x][y] into slot; what was there goes to the first free backpack cell (which may be
    the cell just emptied)."""
    w = bag.get(slot, 0)
    bag[slot] = bag[(x, y)]
    bag[(x, y)] = 0
    bag[free_cell(bag, (x, y))] = w


STACK = 20                  # a full stack of ammunition


def equip(h, x, y):
    """Enter on an item the hero can use: where it goes depends on its number."""
    bag, t, sk, pk = h.bag, h.tell, h.skill, h.pack
    v = bag[(x, y)]
    kind = pk.item_type(v)
    if kind == 'armour':
        swap_into(bag, (14, 4), x, y)
    elif kind in ('weapon', 'launcher'):
        wep = bag.get((12, 4), 0)
        if (kind == 'weapon' and t(v, 10) != 5 and t(wep, 10) != 5 and pk.item_type(wep) == 'weapon'
                and sk.amb == 1 and t(v, 1) <= int(h.hero.str / 2)):
            swap_into(bag, (16, 4), x, y)                            # a second weapon (Ambidexterity)
        else:
            swap_into(bag, (12, 4), x, y)
        if t(bag.get((12, 4), 0), 10) > 4:                           # two-handed: the off-hand empties
            q = free_cell(bag)
            if q == (0, 0) and bag.get((16, 4), 0):
                swap_into(bag, (12, 4), x, y)                        # no room: undone
            else:
                bag[q] = bag.get((16, 4), 0)
                bag[(16, 4)] = 0
    elif kind == 'shield':
        if t(bag.get((12, 4), 0), 10) < 5:
            off = bag.get((16, 4), 0)
            if sk.amb == 1 and bag.get((12, 4), 0) == 0 and pk.item_type(off) == 'shield' and t(v, 1) <= h.hero.str:
                swap_into(bag, (12, 4), x, y)                        # a second shield in the main hand
            else:
                swap_into(bag, (16, 4), x, y)
    elif kind == 'helmet':
        swap_into(bag, (14, 2), x, y)
    elif kind == 'amulet':
        swap_into(bag, (14, 6), x, y)
    elif kind == 'ammo':                                             # fills the worn stack of the same kind
        if t(bag.get((12, 4), 0), 10) < 5:
            off = bag.get((16, 4), 0)
            worn, new = pk.item(off), pk.item(v)
            if pk.item_type(off) == 'ammo' and worn['count'] < STACK and worn['ammo'] == new['ammo'] and y != 4:
                a1, a2 = worn['count'], new['count']
                while a1 < STACK and a2 > 0:
                    a1 += 1
                    a2 -= 1
                bag[(16, 4)] = pk.ammo_id(new['ammo'], a2)
                bag[(x, y)] = pk.ammo_id(worn['ammo'], a1)
            swap_into(bag, (16, 4), x, y)


# ── peddler() ───────────────────────────────────────────────────────────────────
def peddler(h):
    """The shop's buying page: 4 x 10 wares, a red X on what the hero can't afford."""
    g, store = h.g, h.store

    pk = h.pack

    def cost(it):
        p = h.price(it)
        potion = pk.item_type(it) == 'potion'
        if potion and h.level != 1:
            p = p * 2 * (h.level - 1)
        if h.skill.bar == 1 and it and not potion:
            p = p * 7 // 10
        return p

    def wares():
        for i in range(12, 16):
            for ii in range(2, 12):
                dempty(g, i, ii, 20, 10)
                bagdraw(h, i, ii, 2)
                if h.inv.coins < cost(store.get((i, ii), 0)):
                    g.setlinestyle(0, 0, 3)
                    g.setcolor(4)
                    px, py = (i - 1) * 40 + 8, (ii - 1) * 40 + 11
                    g.line(px + 35, py, px + 39, py + 5)
                    g.line(px + 39, py, px + 35, py + 5)
                    g.setlinestyle(0, 0, 1)

    g.setcolor(0)
    g.setfillstyle(1, 0)
    g.bar(411, 0, 640, 500)
    g.bar(0, 411, 640, 500)
    g.setfillstyle(6, 15)
    g.bar(400, 0, 410, 500)
    g.setcolor(15)
    g.settextstyle(4, 0, 4)
    g.outtextxy(455, 0, 'Store: Buy')
    wares()
    hit, x, y = 0, 12, 2
    cursor(g, x, y, 14, False)
    price = 0
    while True:
        if hit != 1:
            itemdisp(h, x, y, 2)
            price = cost(store.get((x, y), 0))
            g.setfillstyle(1, 0)
            g.bar(450, 451, 640, 500)
            coin_line(h, price, 14 if h.inv.coins >= price else 4)
        lx, ly = x, y
        hit = yield KEY
        a = hit
        if hit == 75 and x != 12:
            x -= 1
        elif hit == 77 and x != 15:
            x += 1
        elif hit == 72 and y > 2:
            y -= 1
        elif hit == 80 and y != 11:
            y += 1
        elif a in (105, 115):                                        # i / s: to the selling page
            return a
        elif hit == 27:
            g.setcolor(0)
            cursor(g, lx, ly, None, False)
            g.setcolor(14)
            cursor(g, x, y, None, False)
            return a
        elif hit == 13 and store.get((x, y), 0) > 0:
            it = store[(x, y)]
            s = free_cell(h.bag)
            potion = pk.item(it).get('potion')
            if h.inv.coins >= price and (s != (0, 0) or potion):
                h.inv.coins -= price
                if potion:
                    from .state import add_potions
                    add_potions(h, potion)                   # 9 and 10: The Quest Deluxe's own
                else:
                    h.bag[s] = it
                yield from tones(h, (600, 100), (700, 100))
                wares()
            else:
                yield from tones(h, (100, 200))                      # can't afford it, or no room
        else:
            hit = 1
        g.setcolor(0)                            # peddler(): only the first colour is set every time
        if hit != 1:
            cursor(g, lx, ly, None, False)
            g.setcolor(14)
            cursor(g, x, y, None, False)
