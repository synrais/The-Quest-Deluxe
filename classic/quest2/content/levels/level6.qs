"""Level 6 events, ported from talk() and deadenemycheck() in TheQuest.exe.
talk() here checks every case in turn; a later match overrides the message."""

START = (55, 4)
SHOPS = {(6, 2): 1, (9, 2): 2}
STORIES = [6, 10, 11]               # newmap() shows story 6, then 10 and 11


def talk(npc):
    if x == 53 and y == 15 and npc == -6:
        say(10)
        if take(907):
            # Marianne is returned to her father
            m1 = 1
            room(3, 6).mon = -7
            refresh()
            hero_step(1, 0)
            change_rep(1)
        if m1 == 1:
            say(11)
    if x == 69 and y == 55 and npc == -7:
        # Marianne joins the hero (item 907) if there is room
        say(10)
        if give(907):
            remove(9, 5)
    if x == 53 and y == 16 and npc == -7:
        say(11)
    if x == 97 and y == 34 and npc == -8:
        say(10)
        if take_any(17):
            change_rep(1)
            say(13)
            put(7, 4, 114)
            remove(7, 4)
    if x == 7 and y == 93 and npc == -8:
        say(11)
    if x == 6 and y == 95 and npc == -8:
        say(12)
    if x == 53 and y == 18 and npc == -9:
        say(10)
    if x == 75 and y == 49 and npc == -9:
        say(11)
    if x == 57 and y == 18 and npc == -10:
        say(10)
    if x == 57 and y == 14 and npc == -11:
        say(10)
    if x == 58 and y == 16 and npc == -12:
        say(10)
    if x == 22 and y == 52 and npc == -12:
        say(11)
    if npc == 34:
        # the Skeleton Overlord rises again the first time it falls
        say(10)
        if m2 == 0:
            m2 = 2
        else:
            m2 -= 1
        if m2 == 2:
            say(11)
            for e in enemies():
                if e.type == 34:
                    e.life = e.mlife
                    effect('asskeleton', e.x, e.y, 2)
                    break
    if npc == 35:
        # Fatebringer appears: everyone else on the screen dies
        say(10)
        refresh()
        for e in enemies():
            if e.type != 35 and e.type != 31:
                e.life = 0
    if npc == 36:
        say(10)


def killer_allowed():
    # main2(): on level 6 the killer switch only works once Marianne's quest is done
    return m1 == 1 and m2 == 1
