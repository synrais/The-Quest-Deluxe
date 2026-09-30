"""Level 1 events, ported from talk() and deadenemycheck() in TheQuest.exe.
In talk(), (x, y) is the NPC's square and (ax, ay) is the hero's square on the screen."""

START = (5, 5)                      # where newmap() puts the hero
STORIES = [1]                      # newmap() shows story 1
SHOPS = {(3, 2): 1, (6, 7): 2}      # screen (column, row) -> S00001N.dat


def talk(npc):
    # talk() on level 1 is an if/else chain: the first matching case wins.
    if (x == 24 and y == 13) or (x == 25 and y == 28 and m1 == 0 and npc == -6):
        # the farmers whose daughter was kidnapped: do we bring her back (item 907, her "token")?
        if take(907):
            m1 = 1
            rx = (x - 1) % 10 + 1
            ry = (y - 1) % 10 + 1
            if rx == 5 and ry == 8 and npc == -6:
                say(13)
                remove(5, 8)
                put(ax, ay, 501)
            else:
                room(rx + 1, ry).mon = -7
                map(25, 13).mon = -7
                refresh()
                hero_step(0, -1)
                room(ax, ay).gold += 60
                say(11)
                change_rep(1)
        elif x == 24 and y == 13:
            say(10)
        elif x == 25 and y == 28:
            say(12)
    elif x == 39 and y == 47 and m1 == 0 and npc == -6:
        say(15)
    elif x == 25 and y == 28:
        say(14)
    elif x == 36 and y == 99:
        # the kidnapped daughter: she joins the hero (item 907) if the backpack has room
        if give(907):
            remove((x - 1) % 10 + 1, (y - 1) % 10 + 1)
            say(10)
        else:
            effect('tones', (100, 300))              # no room: a low beep
    elif x == 87 and y == 56:
        say(10)
        remove(7, 6)
        room(7, 6).deco = 3
    elif x == 83 and y == 57:
        change_rep(1)
        say(11)
        remove(3, 7)
        room(3, 7).deco = 3
        put(ax, ay, 205)
    elif x == 8 and y == 95 and npc == -6:
        say(16)
    elif x == 24 and y == 25 and npc == -6:
        say(17)
    elif x == 25 and y == 25 and npc == -7:
        say(11)
    elif npc == 3:
        # the bandit ambush (deadenemycheck() calls talk(3))
        say(10)
        m2 = 1


def before_pickup():
    # main2(): taking the 40 gold in the house at (5, 95) is stealing
    if hx == 5 and hy == 95 and room(5, 5).gold == 40:
        effect('pause', 500)                  # delay(500), then reput(-1)
        change_rep(-1)
