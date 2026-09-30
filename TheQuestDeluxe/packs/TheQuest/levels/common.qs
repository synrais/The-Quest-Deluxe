"""Rules that run on every level, ported from deadenemycheck() in TheQuest.exe.

The engine walks the creatures on the screen by index w, like the original, and for each one calls
check(w) and then, if that creature is dead, dies(w). The original re-reads enemies[w] after every step
(a talk() can rebuild the list), so these handlers use slot(w) each time instead of keeping an object.
Level scripts may add their own check/dies handlers; they run after these.
"""


def check(w):
    # scripted conversations that start when the hero reaches a place (not while leaving a screen)
    if leaving == 0 and level == 1 and m2 == 0 and 80 < hx < 91 and 90 < hy < 101:
        talk(3)                                   # the bandit ambush
    if leaving == 0 and level == 2 and m2 == 0 and 0 < hx < 11 and 70 < hy < 81:
        talk(8)
    if leaving == 0 and level == 3 and m2 == 0 and 0 < hx < 11 and 70 < hy < 81:
        talk(15)
    if leaving == 0 and level == 4 and m2 == 0 and 70 < hx < 81 and 0 < hy < 11:
        talk(15)
    if slot(w).life < 1 and slot(w).type == -15:
        talk(-15)                                 # the priestess's last words
    if level == 7 and m1 == 0 and hx == 90 and (hy == 67 or hy == 68) and ax == 10:
        talk(41)                                  # Light Bringer
    if level == 7 and m2 == 0 and hx == 10 and 45 <= hy <= 47 and ax == 10:
        talk(43)                                  # the Spider Demon Ruler
    e = slot(w)
    if 0 < e.life < 40 and e.type == 45 and e.att == 8:
        # Death Bringer, badly hurt, drains the hero or heals itself
        effect('dcast2', e.x, e.y)
        e.moved = True
        if random(2) != 0:
            effect('adrain', ax, ay, 1)
            effect('adrain', e.x, e.y, 2)
            e.life += hurt_hero(60, 1, w)
        else:
            effect('acure', e.x, e.y)
            e.life += 100
        e.att = 9
    if level == 7 and m2 == 2 and hx == 80 and 5 <= hy <= 7 and ax == 10:
        talk(45)                                  # Death Bringer's lair
    if slot(w).life < 1 and slot(w).type == 45 and (m2 == 3 or m2 == 6):
        talk(slot(w).type)
    if slot(w).life < 1 and slot(w).type == 45 and m2 == 4:
        talk(slot(w).type)
    if slot(w).life < 1 and slot(w).type == 45 and m2 == 5:
        talk(slot(w).type)
    if slot(w).life < 1 and slot(w).type == 43 and m2 == 1:
        talk(slot(w).type)
    if slot(w).life < 1 and slot(w).type == 41 and m1 == 2:
        talk(slot(w).type)
    if slot(w).life < 1 and slot(w).type == 41 and m1 == 3:
        talk(slot(w).type)
        slot(w).life = 1
        slot(w).att = -1
    if slot(w).life < 1 and slot(w).type == 34 and 70 < hx < 81 and 50 < hy < 61 and level == 6:
        talk(slot(w).type)                        # the Skeleton Overlord
    if slot(w).life < 1 and slot(w).type == -7 and level == 6:
        # killing Marianne's double reveals Fatebringer
        e = slot(w)
        e.type = 35
        room(e.x, e.y).mon = 35
        room(7, 5).mon = 31
        talk(35)
        effect('screen_flash', 2)                 # the screen flashes green
        poison()
        restart()                                 # the original starts the scan again (at index 1)
        attacker = 0                              # ...and from now on credits kills to creature 0


def dies(w):
    """Story consequences of a death, before the body falls (the first matching case only)."""
    e = slot(w)
    if e.type == -9 and hx < 11 and hy < 11 and level == 2:
        change_rep(1)
    elif e.type == 15 and level == 3:
        m2 = 1
    elif e.type == -11 and 40 < hx < 51 and hy < 11 and level == 4:
        m1 = 1
        put(e.x, e.y, 506)
    elif e.type == 35 and level == 6:
        talk(e.type + 1)                          # Fatebringer falls: the way out appears
        room(5, 10).item = 1000
        map(55, 20).item = 1000


def level_start():
    # newmap(): Marianne (item 907) doesn't come along to the next level
    take(907)
