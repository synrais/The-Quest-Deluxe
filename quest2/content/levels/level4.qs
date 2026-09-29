"""Level 4 events, ported from talk() and deadenemycheck() in TheQuest.exe."""

START = (5, 95)
STORIES = [4]                      # newmap() shows story 4
SHOPS = {(5, 9): 1, (4, 9): 2, (6, 3): 2, (6, 5): 3}


def talk(npc):
    # an if/else chain: the first matching case wins
    if x == 35 and y == 82 and npc == -6:
        say(10)
    elif x == 67 and y == 84 and npc == -6 and m1 == 0:
        say(12)
    elif x == 63 and y == 88 and npc == -6 and m1 == 0:
        say(13)
    elif x == 64 and y == 84 and npc == -6:
        say(22 if m1 > 0 else 11)
    elif x == 53 and y == 54 and npc == -6:
        say(14)
    elif x == 92 and y == 49 and npc == -6:
        # bring back the Amulet of Fury (507): 370 gold
        if take_any(507):
            room(ax, ay).gold += 370
            say(16)
            remove(2, 9)
        else:
            say(15)
    elif x == 64 and y == 95 and npc == -6:
        say(17)
    elif x == 64 and y == 86 and npc == -6 and m1 > 0:
        say(21)
    elif x == 62 and y == 85 and npc == -6:
        if visited(5, 1) and m1 != 1:
            say(18)
            remove(2, 5)
            m1 = 2
            map(46, 3).deco = 5
            for i in range(41, 51):
                for j in range(1, 11):
                    if map(i, j).mon == -11:
                        map(i, j).mon = 0
            for i in range(1, 101):
                for j in range(1, 101):
                    if map(i, j).mon == -8:
                        map(i, j).mon = 18
        elif m1 == 1:
            say(19)
            remove(2, 5)
            for i in range(1, 101):
                for j in range(1, 101):
                    if map(i, j).mon == -8:
                        map(i, j).mon = 18
        else:
            say(20)
    elif x == 28 and y == 88 and npc == -7:
        say(10)
    elif x == 35 and y == 89 and npc == -7:
        say(11)
    elif x == 66 and y == 88 and npc == -7 and m1 == 0:
        say(12)
    elif x == 58 and y == 57 and npc == -7:
        say(13)
    elif x == 67 and y == 56 and npc == -7:
        say(14)
    elif x == 66 and y == 95 and npc == -7:
        say(15)
    elif x == 17 and y == 83 and npc == -8:
        say(10)
    elif x == 18 and y == 87 and npc == -8:
        say(11)
    elif x == 24 and y == 84 and npc == -8:
        say(12)
    elif x == 24 and y == 87 and npc == -8:
        say(13)
    elif x == 57 and y == 84 and npc == -8:
        say(14)
    elif x == 55 and y == 52 and npc == -8:
        say(15)
    elif x == 56 and y == 52 and npc == -8:
        say(16)
    elif x == 47 and y == 22 and npc == -8:
        say(17)
    elif x == 45 and y == 22 and npc == -8:
        say(18)
    elif x == 34 and y == 2 and npc == -8:
        say(19)
    elif x == 25 and y == 2 and npc == -8:
        say(20)
    elif x == 17 and y == 2 and npc == -8:
        say(21)
    elif x == 8 and y == 5 and npc == -8:
        say(22)
    elif x == 5 and y == 13 and npc == -8:
        say(23)
        put(ax, ay, 12)
        remove(5, 3)
        map(63, 88).mon = 0
        map(62, 85).mon = -6
    elif x == 66 and y == 12 and npc == -8:
        say(24)
    elif x == 37 and y == 35 and npc == -8:
        say(25)
    elif x == 46 and y == 8 and npc == -8:
        say(26)
    elif x == 44 and y == 89 and npc == -9:
        say(10)
    elif x == 48 and y == 89 and npc == -9:
        say(11)
    elif x == 67 and y == 86 and npc == -9 and m1 == 0:
        say(12)
    elif x == 33 and y == 72 and npc == -9:
        say(13 if ems > 0 else 14)
    elif x == 75 and y == 49 and npc == -9:
        say(15)
    elif x == 79 and y == 86 and npc == -9:
        say(16)
    elif x == 38 and y == 93 and npc == -10:
        say(10)
    elif x == 65 and y == 94 and npc == -10:
        say(11)
    elif x == 65 and y == 45 and npc == -11:
        say(10)
    elif x == 67 and y == 46 and npc == -11:
        say(11)
    elif x == 55 and y == 24 and npc == -11:
        say(12)
    elif x == 86 and y == 24 and npc == -11:
        say(13)
    elif x == 46 and y == 3 and npc == -11:
        say(14)
    elif x == 55 and y == 37 and npc == -12:
        say(10)
    elif x == 54 and y == 46 and npc == -12:
        say(11)
    elif x == 3 and y == 37 and npc == -12:
        say(12)
    elif npc == 15:
        say(10)
        m2 = 1


def opened_chest():
    # main2(): these chests belong to someone
    if (hx == 84 and hy == 32) or (hx == 55 and hy == 16) or (hx == 58 and hy == 17):
        change_rep(-1)


def took(item):
    # main2(): taking the emerald at (64, 95) or the Amulet of Fury at (3, 37) is stealing
    if hx == 64 and hy == 95 and item == 9:
        change_rep(-1)
    if hx == 3 and hy == 37 and item == 507:
        change_rep(-1)
