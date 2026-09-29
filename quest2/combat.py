"""Combat: ports of hurt(), deadenemycheck(), the hero's melee/ranged attacks (main2)
and the enemies' attack phase (main2, after the hero acts)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import rules
from .rules import random, distance, LOW_HEALTH
from .state import (Enemy, SLOT_WEAPON, SLOT_OFFHAND, IT_KIND, KIND_RANGED)

if TYPE_CHECKING:
    from .game import Game

NO_BLOOD = (6, 7, -100, -101)          # skeletons / stone creatures don't bleed


def bleeds(e: Enemy) -> bool:
    return e.type not in NO_BLOOD and not 28 <= e.type <= 34


class Combat:
    def __init__(self, game: 'Game'):
        self.g = game

    # shortcuts
    @property
    def w(self):
        return self.g.world

    @property
    def p(self):
        return self.g.player

    def say(self, text: str):
        self.g.log(text)

    def anger_npcs(self):
        for o in self.w.enemies:
            if o.is_npc and o.att > -10:
                o.att = 9

    # ── hurt() ────────────────────────────────────────────────────────────────
    def hurt(self, dmg: int, target: Enemy | None, kind: int, attacker: Enemy | None = None,
             by_hero: bool = False) -> int:
        """Deal `dmg` (± a third) to target (None = the hero). kind 0 weapon armour, 1 magic armour,
        2/3 ignore armour. Returns damage done."""
        h, st = self.p.hero, self.g.status
        if target is not None and target.att < -10 and h.invisible == -1:
            target.att = 9
        dam = rules.spread(dmg)
        warm, marm = (h.warm, h.marm) if target is None else (target.warm, target.marm)
        if target is None and st.Shield > 0 and self.g.spells.tell(5, rules.SP_POWER) >= dam:
            self.say('Your shield absorbs the blow.')
            return 0
        if kind == 0:
            dam -= warm
        elif kind == 1:
            dam -= marm
        dam = max(0, dam)
        if target is None:
            if dam > 0:
                h.life -= dam
            return dam
        target.life -= dam
        if (target.att == -1 or target.att < -10 or target.att == -3) and kind != 3 and h.invisible == -1:
            target.att = 9
        if target.is_npc and kind != 3:
            self.anger_npcs()
        self.check_dead(None if by_hero else attacker)
        return dam

    # ── deadenemycheck() ──────────────────────────────────────────────────────
    def check_dead(self, attacker: Enemy | None = None):
        """deadenemycheck(): walk the screen's creatures by index. For each, the level scripts' check()
        runs (scripted conversations, bosses); a dead one then gets its story consequences (dies()) and
        falls: a body, experience and loot when the hero or a summoned ally killed it, the witnesses'
        judgement, and removal. Like the original, the creature that slides into a removed one's place
        is not looked at until the next check."""
        w, ev = self.w, self.g.events
        ev.attacker = -1 if attacker is None or attacker not in w.enemies else w.enemies.index(attacker)
        i = 0
        while i < len(w.enemies):
            ev.run_check(i)
            if i < len(w.enemies):
                e = w.enemies[i]
                ox, oy = w.origin
                if e.life < 1 and e.x - ox + 1 > 0:
                    ev.run_dies(i)
                    if i < len(w.enemies):
                        self.fall(i, w.enemies[i])
            if ev.restart_scan:
                ev.restart_scan = False
                i = 0
            i += 1
        self.g.status.mons = len(w.enemies)

    def fall(self, i: int, e: Enemy):
        """The generic half of a death in deadenemycheck()."""
        w, h, ev = self.w, self.p.hero, self.g.events
        if self.g.target is e:
            self.g.target = None
        q = w.sq(e.x, e.y)
        q.mon = 0
        r = random(2)
        if q.deco in (0, 4):
            q.deco = 3 if r == 0 else 5
            if e.type in (6, 7, -100, -101) or 27 < e.type < 35:
                q.deco = 6
            if e.type in (22, 23, 46):
                q.deco = 0
        a = ev.attacker
        by_ally = 0 <= a < len(w.enemies) and w.enemies[a].type <= -100
        gold = 0
        if a == -1 or by_ally:
            gold = self.grant_rewards(e)
        q.gold += gold
        witness = 0
        for o in w.enemies:
            if -100 < o.type < 0:
                witness += 1
            if o.type == 35:
                witness = 0
                break
        if witness > 1 and -100 < e.type < 0 and (a == -1 or by_ally):
            self.g.change_rep(-3)
        if e.type > 0 and e.type not in (4, 12) and witness > 0 and h.rep <= -4 and a == -1:
            self.g.change_rep(1)
        del w.enemies[i]
        if -100 < e.type < 0 and a == -1:
            for o in w.enemies:
                if -100 < o.type < 0 and o.att > -10:
                    o.att = 9
        self.g.status.mons = len(w.enemies)

    def grant_rewards(self, e: Enemy) -> int:
        """monsdeath2(): Honor calms down, experience, then loot from content/monsters.json. The roll
        random(100)+1 is always made; the first loot rule with lo < roll <= hi applies. Returns the gold."""
        h = self.p.hero
        if self.p.skill.hon == 2:
            self.p.skill.hon = 1
        reward = self.g.rewards.get(e.type, {})
        h.exper -= reward.get('exp', 0)
        roll = random(100) + 1
        gold = 0
        for lo, hi, kind, *args in reward.get('loot', []):
            if lo < roll <= hi:
                if kind == 'gold':
                    gold = random(args[0]) + args[1]
                elif kind == 'item':
                    self.g.put_item(e.x, e.y, args[0])
                break
        drop = reward.get('drop_on_level', {}).get(str(self.w.level))
        if drop:
            self.g.put_item(e.x, e.y, drop)
        return gold

    # ── the hero attacks ──────────────────────────────────────────────────────
    def wake_on_attack(self, e: Enemy):
        h, sk = self.p.hero, self.p.skill
        if h.invisible > -1:
            h.invisible = 0
        if sk.hon == 1:
            sk.hon = 2
        if e.att == -1:
            e.att = 1
        if e.att == -3 or e.att < -10:
            e.att = 9
        if e.is_npc:
            self.anger_npcs()

    def melee(self, e: Enemy):
        """Walking into an enemy: herohit(), Ambidexterity second swing, kind-1 double strikes."""
        p, items = self.p, self.g.items
        self.wake_on_attack(e)
        for swing in (0, 1):
            if swing == 1:
                p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = p.bag.get(SLOT_OFFHAND, 0), p.bag.get(SLOT_WEAPON, 0)
            rules.status_update(p, self.g.status, items)
            if items.tell(p.item(SLOT_WEAPON), IT_KIND) == KIND_RANGED:
                self.say("You can't fight hand to hand with that.")
            else:
                dmg = rules.hero_hit(p, e, items)
                if dmg > 0:
                    e.life -= dmg
                    self.say(f'You hit for {dmg}.')
                    q = self.w.sq(e.x, e.y)
                    if q.deco == 0 and e.life > 0 and bleeds(e):
                        q.deco = 4
                    if items.tell(p.item(SLOT_WEAPON), IT_KIND) == rules.KIND_DOUBLE and random(5) == 1:
                        e.life -= dmg
                        self.say(f'A second strike for {dmg}!')
                else:
                    self.say('You miss.')
            if swing == 1:
                p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = p.bag.get(SLOT_OFFHAND, 0), p.bag.get(SLOT_WEAPON, 0)
                rules.status_update(p, self.g.status, items)
            off = p.item(SLOT_OFFHAND)
            if not (swing == 0 and p.skill.amb == 1 and 200 < off < 300 and e.life > 0):
                break
        self.check_dead()

    def ranged_candidates(self) -> list[Enemy]:
        """Enemies that Space/Tab may shoot, nearest first (distance rings 2..14)."""
        px, py, st = self.p.X, self.p.Y, self.g.status
        out = []
        for e in self.w.enemies:
            d = distance(e.x - px, e.y - py)
            if not 2 <= d <= 14:
                continue
            if not (st.killer or e.type > 0 or e.att >= 0):
                continue
            if e.att == -1 and st.ems > 0:
                continue
            if e.type == 22:
                continue
            out.append((d, e))
        out.sort(key=lambda t: t[0])
        return [e for _, e in out]

    def can_shoot(self) -> str | None:
        """None if a shot is possible, else the reason."""
        p, items = self.p, self.g.items
        wep, ammo = p.item(SLOT_WEAPON), p.item(SLOT_OFFHAND)
        if items.tell(wep, IT_KIND) != KIND_RANGED:
            return 'You have no ranged weapon.'
        if not rules.ammo_ok(wep, ammo):
            return 'You have no ammunition for this weapon.' if ammo == 0 else "That ammunition doesn't fit."
        return None

    def shoot(self, e: Enemy):
        """Fire at e: to-hit (8-dist)*10 + atk + 5 - def, damage = power (ignores armour)."""
        p, h = self.p, self.p.hero
        rules.status_update(p, self.g.status, self.g.items)
        if e.att == -2:
            self.anger_npcs()
        self.wake_on_attack(e)
        if e.att not in (-4, 8):
            e.att = 9
        self.g.target = e
        d = distance(e.x - p.X, e.y - p.Y)
        if (8 - d) * 10 + h.atk + 5 - e.defense >= random(100) + 1:
            q = self.w.sq(e.x, e.y)
            if q.deco == 0 and e.life > 0 and bleeds(e):
                q.deco = 4
            dmg = self.hurt(h.power, e, 2, by_hero=True)
            self.say(f'Your shot hits for {dmg}.')
        else:
            self.say('Your shot misses.')
        ammo = p.item(SLOT_OFFHAND) - 1
        p.bag[SLOT_OFFHAND] = 0 if ammo % 20 == 0 else ammo
        rules.status_update(p, self.g.status, self.g.items)

    # ── the enemies attack (main2, after the hero's action) ───────────────────
    def enemy_attacks(self):
        p, h, st, items = self.p, self.p.hero, self.g.status, self.g.items
        for e in list(self.w.enemies):
            if e not in self.w.enemies or e.life <= 0:
                continue
            if not (e.att >= 0 or e.att <= -10 or e.att == -4):
                continue
            dx, dy = abs(p.X - e.x), abs(p.Y - e.y)
            adjacent = (dx == 1 and dy == 0) or (dy == 1 and dx == 0)
            if not adjacent and not (dx <= e.range and dy <= e.range and e.range > 1):
                continue
            if not (h.invisible == -1 or e.att in (-4, 8)):
                continue
            if e.moved and e.type == 45:
                continue
            if e.att != -4:
                e.moved = True
            name = self.g.monster_name(e.type)
            if e.range == 1 and e.atk != 0:
                self.enemy_melee(e, name)
            elif e.atk != 0 and e.type != 45:
                self.enemy_ranged(e, name)
            else:
                self.enemy_cast(e, name)

    def enemy_melee(self, e: Enemy, name: str):
        p, h, items = self.p, self.p.hero, self.g.items
        if e.type == 22:
            e.type = 23
            self.w.sq(e.x, e.y).mon = 23
            self.say('A wraith appears!')
        dmg = rules.mon_hit(e, p, self.g.status, self.g.spells)
        parry = items.tell(p.item(SLOT_WEAPON), IT_KIND) in (2, 6) or \
            (p.skill.amb == 1 and items.tell(p.item(SLOT_OFFHAND), IT_KIND) in (2, 6))
        if parry and random(5) == 1:
            dmg = 0
            self.say(f'You parry the {name}.')
        if dmg > 0:
            h.life -= dmg
            self.say(f'The {name} hits you for {dmg}.')
            self.bleed_hero()
            if e.type in (12, -102) and random(2) == 1 and not h.poisoned:
                h.poisoned = 1
                self.g.log('You have been poisoned!', 4)

    def enemy_ranged(self, e: Enemy, name: str):
        p, h = self.p, self.p.hero
        d = distance(e.x - p.X, e.y - p.Y)
        if d == 1:
            d = 99
            e.moved = False
        if e.atk + (8 - d) * 10 + 5 - h.defense >= random(100) + 1:
            dmg = self.hurt(e.power, None, 2, e)
            self.say(f'The {name} shoots you for {dmg}.')
            self.bleed_hero()
            if e.type == 27 and random(2) == 1 and not h.poisoned:
                h.poisoned = 1
                self.g.log('You have been poisoned!', 4)

    def enemy_cast(self, e: Enemy, name: str):
        w, p, h = self.w, self.p, self.p.hero
        if e.type == 38:                                   # cleric heals a wounded ally
            for o in w.enemies:
                if o is e or not (o.att > -1 or o.att in (-4, -5)) or o.life >= o.mlife:
                    continue
                t1 = e.power
                o.life = min(o.mlife, o.life + t1 - t1 // 3 + random(2 * (t1 // 3)))
                e.moved = True
                self.say(f'The {name} heals its ally.')
                break
        if e.type == 32:                                   # necromancer raises a skeleton from bones
            ox, oy = w.origin
            for x in range(ox, ox + 10):
                for y in range(oy, oy + 10):
                    q = w.sq(x, y)
                    if q.deco == 6 and q.mon == 0 and (x, y) != (p.X, p.Y):
                        e.moved = True
                        q.deco = 0
                        e.life -= 2
                        self.g.spawn(33, x, y)
                        self.say(f'The {name} raises the dead!')
                        self.check_dead(e)
                        break
                else:
                    continue
                break
        if e.type == 44:                                   # kamikaze demon: 6 blasts then dies
            for _ in range(6):
                self.hurt(e.power, None, 1, e)
            self.say(f'The {name} explodes!')
            self.hurt(e.power * 6, e, 1, e)
            return
        if e.att == -4:
            return
        dmg = self.hurt(e.power, None, 1, e)
        self.say(f'The {name} casts at you for {dmg}.')
        if e.type == 31 and dmg > 0:
            e.life += dmg
            e.mlife += dmg
        if e.type == 33 and dmg > 0 and random(20) == 1 and not h.poisoned:
            h.poisoned = 1
            self.g.log('You have been poisoned!', 4)
        if e.type == 45:                                   # the Deceiver turns summons into demons
            around = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                         if w.in_map(e.x + dx, e.y + dy) and w.sq(e.x + dx, e.y + dy).mon < -99)
            if random(2) == 0 and around > 1:
                for o in w.enemies:
                    if o.type < -99:
                        o.att, o.type, o.power, o.marm, o.atk, o.life = 9, 44, 25, 15, 0, 40
                        w.sq(o.x, o.y).mon = 44
                self.say('Your allies are twisted into demons!')

    def bleed_hero(self):
        h = self.p.hero
        q = self.w.sq(self.p.X, self.p.Y)
        if q.deco == 0 and h.mlife and h.life / h.mlife <= LOW_HEALTH:
            q.deco = 4

    def fire_shield(self):
        """Shield of Fire burns adjacent enemies every turn."""
        p = self.p
        power = self.g.spells.tell(13, rules.SP_POWER)
        for e in list(self.w.enemies):
            if e in self.w.enemies and abs(e.x - p.X) + abs(e.y - p.Y) == 1:
                self.hurt(power, e, 1, by_hero=True)
