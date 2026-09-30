"""Level 5 events, ported from talk() and deadenemycheck() in TheQuest.exe.
Unlike levels 1-4, talk() here checks every case in turn; a later match overrides the message."""

START = (85, 95)
STORIES = [5]                      # newmap() shows story 5
SHOPS = {(4, 10): 1, (3, 10): 2, (9, 4): 2}
TELEPORT = (20, 0)                  # teleporter1(): the pad (item 999) moves the hero 20 squares east
LEAVE_JINGLE = False               # newmap() plays no jingle when leaving level 5


def talk(npc):
    if x == 38 and y == 98 and npc == -6 and m1 == 0:
        say(10)
        if take_any(9):
            put(ax, ay, 16)
            say(11)
            m1 = 1
    if x == 76 and y == 36 and npc == -6:
        say(12)
    if x == 84 and y == 23 and npc == -6:
        say(13)
        if coins >= 50 and take_any(16):
            put(ax, ay, 508)
            coins -= 50
            say(14)
    if x == 83 and y == 94 and npc == -6:
        say(15)
    if x == 29 and y == 94 and npc == -7:
        say(10)
    if x == 18 and y == 6 and npc == -7:
        say(11)
    if x == 56 and y == 62 and npc == -8:
        # the guards turn on you: the first two creatures become hostile knights
        say(10)
        slot(0).type = 18
        slot(1).type = 18
        slot(0).att = 9
        slot(1).att = 9
    if x == 96 and y == 79 and npc == -8:
        say(11)
        put(ax, ay, 12)
        remove(6, 9)
        change_rep(1)
    if x == 34 and y == 93 and npc == -9:
        say(10)
    if x == 89 and y == 27 and npc == -9:
        say(11)
    if x == 17 and y == 8 and npc == -9:
        say(12)
    if x == 17 and y == 3 and npc == -9:
        say(13)
    if x == 17 and y == 6 and npc == -10:
        say(10)
