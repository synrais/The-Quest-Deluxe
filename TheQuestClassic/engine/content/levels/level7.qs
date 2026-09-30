"""Level 7 events, ported from talk() and deadenemycheck() in TheQuest.exe.
talk() here checks every case in turn; a later match overrides the message."""

START = (36, 98)
STORIES = [7]                      # newmap() shows story 7
SHOPS = {(3, 9): 1, (5, 9): 2}
ASK_TO_LEAVE = False                # newmap() doesn't ask "Want to travel further?" on level 7
LEAVE_JINGLE = False               # nor when leaving level 7


def talk(npc):
    if x == 38 and y == 94 and npc == -6:
        say(10)
    if x == 38 and y == 83 and npc == -6:
        say(11)
    if x == 26 and y == 94 and npc == -6:
        say(12)
    if x == 38 and y == 88 and npc == -7:
        say(10)
    if x == 47 and y == 87 and npc == -7:
        say(11)
    if x == 33 and y == 93 and npc == -9:
        say(10)
    if x == 24 and y == 94 and npc == -9:
        say(11)
    if x == 33 and y == 88 and npc == -10:
        say(10)
    if x == 27 and y == 84 and npc == -11:
        say(11)
        if count(-14, 91, 91, 100, 100) > 0:
            say(10)
        if m1 == 1 and said() == 11:
            say(12)
        if said() == 11:
            remove(7, 4)
            room(7, 4).gold += 400
            room(7, 4).item = 5
    if x == 98 and y == 39 and npc == -11 and rep >= 6:
        say(13)
        put(8, 9, 16)
        put(8, 9, 5)
        remove(8, 9)
    if x == 98 and y == 39 and npc == -11 and rep < 6:
        say(14)
    if x == 48 and y == 87 and npc == -12:
        say(10)
    elif x == 25 and y == 96 and npc == -12:
        say(11)
    if x == 49 and y == 96 and npc == -14:
        say(10)
        for e in enemies():
            e.type = 37
            e.att = 9
    if x == 98 and y == 96 and npc == -14:
        say(11)
        if m1 == 2:
            say(12)
        elif m1 == 1:
            say(13)
    if x == 5 and y == 35 and npc == -15:
        say(10)
        remove(5, 5)
        put(ax, ay, 511)
    elif npc == -15:
        say(11)
        put(5, 5, 511)
    if npc == 41:
        # Light Bringer's three stages
        if m1 == 0:
            say(10)
            m1 = 3
        elif m1 == 3:
            say(11)
            m1 = 2
            put(ax - 1, ay, 14)
        elif m1 == 2:
            say(12)
            m1 = 1
    if npc == 43:
        # the Spider Demon Ruler
        if m2 == 0:
            say(10)
            m2 = 1
        else:
            say(11)
            m2 = 2
            put(ax, ay, 13)
            if room(ax, ay).deco > 0:
                room(ax, ay).deco = 0
    if npc == 45:
        # Death Bringer: each time it falls it comes back stronger
        k = -1
        n = 0
        for e in enemies():
            if e.type == 45:
                k = n
                e.moved = True
                break
            n += 1
        boss = slot(len(enemies()) if k < 0 else k)
        bx = 0
        by = 0
        if k >= 0:
            bx = boss.x
            by = boss.y
        if m2 < 3:
            say(10)
            m2 = 3
            effect('dcast2', bx, by)
            hero_step(-1, 0)
            room(10, 5).wall = -2
            room(10, 6).wall = -2
            room(10, 7).wall = -2
            effect('ainvisibility', 10, 5)
            effect('ainvisibility', 10, 6)
            effect('ainvisibility', 10, 7)
            boss.power = 35
            boss.range = 9
            boss.atk = 0
        elif m2 == 3:
            say(11)
            m2 = 4
            effect('dcast2', bx, by)
            room(bx, by).mon = 0
            for sx, sy in [(5, 2), (5, 9), (10, 6)]:
                effect('asskeleton', sx, sy, 3)
                room(sx, sy).mon = 46
            if random(3) == 1:
                room(5, 2).mon = 45
            elif random(2) == 1:
                room(5, 9).mon = 45
            else:
                room(10, 6).mon = 45
            refresh()
        elif m2 == 4:
            say(12)
            m2 = 5
            effect('dcast2', bx, by)
            for sx, sy in [(4, 1), (6, 1), (4, 10), (6, 10), (1, 4), (10, 4), (1, 8), (10, 8)]:
                effect('asskeleton', sx, sy, 3)
                room(sx, sy).mon = 12
            refresh()
            for e in enemies():
                if e.type == 12:
                    e.att = 9
                elif e.type == 45:
                    e.power = 35
                    e.range = 9
                    e.atk = 0
            autosave(1)
            for e in enemies():
                e.moved = True
        elif m2 == 5:
            say(13)
            m2 = 6
            effect('dcast2', bx, by)
            effect('ashield', bx, by, 1)
            effect('ashield', bx, by, 2)
            boss.life = boss.mlife
            boss.power = 120
            boss.warm = boss.warm * 2
            boss.marm = boss.marm * 2
            boss.att = 8
            boss.atk = 150
            boss.range = 1
        elif m2 == 6:
            say(14)
            m2 = 7


def after_action(key):
    # main2(): once Death Bringer is gone for good (m2 == 7) the game ends after any key but Space
    if m2 == 7 and key != 'space':
        next_level()
