"""Level 2 events, ported from talk() and deadenemycheck() in TheQuest.exe."""

START = (95, 5)
STORIES = [2]                      # newmap() shows story 2
SHOPS = {(7, 1): 1, (8, 1): 2, (6, 1): 3}


def talk(npc):
    # an if/else chain: the first matching case wins
    if x == 67 and y == 8 and npc == -6:
        say(10)
    elif x == 56 and y == 6 and npc == -6:
        say(11)
    elif x == 97 and y == 35:
        say(12)
    elif x == 75 and y == 5 and npc == -7:
        say(10)
    elif x == 62 and y == 5 and npc == -7:
        say(11)
    elif x == 26 and y == 36 and npc == -8:
        change_rep(1)
        say(10)
        remove(6, 6)
        room(6, 6).deco = 3
    elif x == 74 and y == 5 and npc == -9:
        say(10)
    elif x == 65 and y == 8 and npc == -9:
        say(11)
    elif x == 54 and y == 7 and npc == -9:
        say(12)
    elif x == 54 and y == 5 and npc == -9:
        say(13)
    elif x == 38 and y == 6 and npc == -9:
        # the fisherman who wants meat (item 11)
        if m1 == 1 and has(11):
            say(15)
            put(8, 6, 11)
            take(11)
        else:
            say(14)
            m1 = 1
    elif x < 11 and y < 11 and npc == -9:
        say(16)
        for e in enemies():
            if e.type > -100:
                e.att = 9
    elif x == 44 and y == 98 and npc == -9 and rep >= 4:
        say(17)
        put(4, 7, 6)
        remove(4, 8)
    elif npc == 8:
        say(10)
        m2 = 1
