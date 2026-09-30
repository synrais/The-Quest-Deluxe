"""Level 3 events, ported from talk() and deadenemycheck() in TheQuest.exe."""

START = (82, 2)
STORIES = [3]                      # newmap() shows story 3
SHOPS = {(7, 5): 1, (6, 5): 2}


def talk(npc):
    # an if/else chain: the first matching case wins
    if x == 86 and y == 3 and npc == -7:
        say(10)
    elif x == 62 and y == 49 and npc == -7:
        say(11)
    elif x == 59 and y == 56 and npc == -7:
        say(12)
    elif x == 99 and y == 46 and npc == -7:
        say(13)
    elif x == 67 and y == 39 and npc == -8:
        say(10)
    elif x == 69 and y == 39 and npc == -8:
        say(11)
    elif x == 52 and y == 62 and npc == -8:
        if map(96, 96).mon == -8:
            say(12)
    elif x == 96 and y == 96 and npc == -8:
        # the guard who comes back to his post
        say(13)
        change_rep(1)
        remove(6, 6)
        map(54, 62).mon = -8
        put(ax, ay, 2)
    elif x == 54 and y == 62 and npc == -8:
        say(14)
    elif m2 == 0 and x == 55 and y == 56 and npc == -8:
        say(15)
    elif x == 56 and y == 43 and npc == -9:
        say(10)
    elif x == 68 and y == 45 and npc == -10:
        say(10)
    elif x == 89 and y == 2 and npc == -10:
        say(11)
    elif m2 == 0 and x == 68 and y == 55 and npc == -10:
        say(12)
        map(55, 56).mon = -8
    elif m2 == 1 and x == 68 and y == 55 and npc == -10:
        say(21)
        change_rep(1)
        m2 = 3
    elif x == 53 and y == 47 and npc == -10:
        say(13)
    elif x == 52 and y == 47 and npc == -10:
        # the monk who wants the corrupt monks (14) gone
        left = count(14, 1, 1, 100, 100)
        if left != 0:
            say(14)
        elif m1 % 10 == 0:
            change_rep(1)
            say(15)
            m1 += 1
            put(ax, ay, 211)
        else:
            say(random(3) + 1)
    elif x == 98 and y == 45 and npc == -10:
        say(16)
    elif x == 98 and y == 46 and npc == -10:
        say(17)
    elif x == 98 and y == 47 and npc == -10:
        if m1 < 10:
            say(18)
            put(ax, ay, 505)
            m1 += 10
            change_rep(1)
        else:
            say(random(3) + 1)
    elif x == 58 and y == 48 and npc == -10:
        say(19)
    elif x == 8 and y == 7 and npc == -10:
        say(20)
    elif x == 62 and y == 46 and npc == -6:
        say(10)
    elif x == 64 and y == 49 and npc == -6:
        say(11)
    elif npc == 15:
        say(10)
        m2 = 2
