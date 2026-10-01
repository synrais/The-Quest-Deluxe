"""Combat: ports of hurt(), deadenemycheck(), the hero's melee/ranged attacks (main2)
and the enemies' attack phase (main2, after the hero acts)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import rules
from .rules import random, distance, LOW_HEALTH
from .state import (Enemy, SLOT_WEAPON, SLOT_OFFHAND, IT_KIND, KIND_RANGED)

if TYPE_CHECKING:
    from .game import Game

def bleeds(pack, e: Enemy) -> bool:
    return pack.trait(e.type, 'bleeds', True)


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
             by_hero: bool = False, how: str = '', quiet: bool = False) -> int:
        """Deal `dmg` (± a third) to target (None = the hero). kind 0 weapon armour, 1 magic armour,
        2/3 ignore armour. Returns damage done. how: what dealt it, for the combat log (a spell's name)."""
        self.absorbed = False
        self._log = None if quiet else (kind, attacker, by_hero, how)
        return self._hurt(dmg, target, kind, attacker, by_hero)

    def _logged(self, dam, target):
        if self._log is not None:
            kind, attacker, by_hero, how = self._log
            self.log_hurt(None if self.absorbed else dam, target, kind, attacker, by_hero, how)

    def log_hurt(self, dam, target, kind, attacker, by_hero, how):
        """The combat log's line for a hurt() (Deluxe; the original shows only the animation)."""
        g = self.g
        if not g.combat_log:
            return
        if target is None:
            p = self.p
            if dam is None:
                g.report('Your Shield absorbs the blow.', 11)
            elif attacker is not None:
                verb = 'shoots' if kind == 2 else 'hits' if kind == 0 else 'blasts'
                name = g.monster_name(attacker.type)
                g.report(f'The {name} {verb} you for {dam}.' if dam else f'The {name} {verb} you, but does no harm.',
                         12 if dam else 7, (p.X, p.Y), dam)
            elif how:
                g.report(f'Your {how} hits you for {dam}.', 12, (p.X, p.Y), dam)
            return
        name = g.monster_name(target.type)
        if by_hero:
            who = f'Your {how}' if how else 'You'
            verb = 'hits' if how else 'hit'
            g.report(f'{who} {verb} the {name} for {dam}.' if dam else f'The {name} shrugs off {"your " + how if how else "the blow"}.',
                     14 if dam else 7, (target.x, target.y), dam)
        elif attacker is not None and attacker is not target:
            g.report(f'The {g.monster_name(attacker.type)} hits the {name} for {dam}.', 11, (target.x, target.y), dam)

    def _hurt(self, dmg, target, kind, attacker, by_hero):
        h, st = self.p.hero, self.g.status
        if target is not None and target.att < -10 and h.invisible == -1:
            target.att = 9
        dam = rules.spread(dmg)
        warm, marm = (h.warm, h.marm) if target is None else (target.warm, target.marm)
        if target is None and st.Shield > 0 and self.g.pack.shield_absorbs() >= dam:
            self.g.tones((400, 70), (350, 70))            # the Shield spell absorbs the blow
            self.absorbed = True
            self._logged(0, None)
            return 0
        if kind == 0:
            dam -= warm
        elif kind == 1:
            dam -= marm
        dam = max(0, dam)
        if target is None:
            if dam > 0:
                h.life -= dam
            self._logged(dam, None)
            return dam
        target.life -= dam
        self._logged(dam, target)                           # before the death check, so hits come before deaths
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
        fixed = self.g.pack.fixed('dead_scan')
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
                        if fixed and not ev.restart_scan:
                            continue                   # the fix: look at the one that slid into place
            if ev.restart_scan:
                ev.restart_scan = False
                i = -1 if fixed else 0                 # the original starts over at index 1
            i += 1
        self.g.status.mons = len(w.enemies)

    def fall(self, i: int, e: Enemy):
        """The generic half of a death in deadenemycheck()."""
        w, h, ev = self.w, self.p.hero, self.g.events
        self.g.tones((200, 50), (500, 50))                 # every death beeps
        if self.g.target is e:
            self.g.target = None
        q = w.sq(e.x, e.y)
        for cx, cy in w.cells(e):
            if w.in_map(cx, cy):
                w.sq(cx, cy).mon = 0
        r, pk = random(2), self.g.pack
        if q.deco in (0, pk.deco('blood')):
            q.deco = pk.deco('remains') if r == 0 else pk.deco('remains2')
            corpse = pk.trait(e.type, 'corpse', 'body')
            if corpse == 'bones':
                q.deco = pk.deco('bones')
            elif corpse == 'none':
                q.deco = 0
        a = ev.attacker
        by_ally = 0 <= a < len(w.enemies) and w.enemies[a].ally
        gold = 0
        before = h.exper
        if a == -1 or by_ally:
            gold = self.grant_rewards(e)
        if self.g.combat_log:
            gained = before - h.exper
            self.g.report(f'The {self.g.monster_name(e.type)} dies.' + (f' +{gained} experience.' if gained > 0 else ''),
                          15)
        q.gold += gold
        witness = 0
        for o in w.enemies:
            if -100 < o.type < 0:
                witness += 1
            if self.g.pack.trait(o.type, 'silences_witnesses'):
                witness = 0
                break
        if witness > 1 and -100 < e.type < 0 and (a == -1 or by_ally):
            self.g.change_rep(-3)
        if e.type > 0 and not self.g.pack.trait(e.type, 'animal') and witness > 0 and h.rep <= -4 and a == -1:
            self.g.change_rep(1)
        if (e.type > 0 or -100 < e.type < 0 and e.type != -5) and q.deco in (
                pk.deco('remains'), pk.deco('remains2'), pk.deco('bones')) and q.deco:
            corpses = self.p.more.setdefault('corpses', {})   # who lies where, for the Resurrect spell
            corpses.pop(f'{w.level},{e.x},{e.y}', None)
            corpses[f'{w.level},{e.x},{e.y}'] = e.type
            while len(corpses) > 60:
                corpses.pop(next(iter(corpses)))
        if pk.trait(e.type, 'regenerates_from_blood'):
            self.p.more.setdefault('reviving', []).append([w.level, e.x, e.y, e.type, -1, -1, 0])
        del w.enemies[i]
        if -100 < e.type < 0 and a == -1:
            for o in w.enemies:
                if -100 < o.type < 0 and o.att > -10:
                    o.att = 9
        self.g.status.mons = len(w.enemies)

    def grant_rewards(self, e: Enemy) -> int:
        """monsdeath2(): Honor calms down, experience, then loot from the pack's creatures.json. The roll
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

    # ── a creature that rises again from a pile of blood (creatures.json `regenerates_from_blood`) ──
    def blood_squares(self) -> set:
        pk = self.g.pack
        return {pk.deco(role) for role in ('blood', 'remains', 'remains2')} - {0}

    def revive_step(self):
        """The end of a turn: for each fallen creature that feeds on blood, the nearest pile of blood on the
        screen slides a square towards its body, and one that lands on the body makes the creature whole
        again (when nobody stands there). Fire that burns the pile away sends the next-nearest. With no
        blood left on the screen it stays dead. The entries are [level, x, y, creature, pile x, pile y,
        turns stuck] in the hero's more['reviving']."""
        g, w, p = self.g, self.w, self.p
        entries = p.more.get('reviving')
        if not entries:
            return
        blood, keep = self.blood_squares(), []
        for entry in entries:
            level, x, y, kind, px, py, stuck = entry
            if level != w.level:
                continue                                  # another level was reloaded
            if not w.in_room(x, y):
                keep.append(entry)                        # waits for the hero to come back to this screen
                continue
            reach = g.pack.trait(kind, 'blood_range') or 99          # how far from the body blood still feeds it
            if (px, py) != (x, y):
                if not (px >= 0 and w.in_room(px, py) and w.sq(px, py).deco in blood):
                    near = [(max(abs(sx - x), abs(sy - y)), abs(sx - x) + abs(sy - y), sx, sy)
                            for sx, sy in w.room_tiles() if w.sq(sx, sy).deco in blood and (sx, sy) != (x, y)
                            and max(abs(sx - x), abs(sy - y)) <= reach]
                    if not near:
                        continue                          # no blood left: the creature stays dead
                    px, py = min(near)[2:]
            moved = (px, py) == (x, y)                    # a pile already on the body only waits
            if not moved:
                dx, dy = (x > px) - (x < px), (y > py) - (y < py)
                steps = [(dx, 0), (0, dy)] if abs(x - px) >= abs(y - py) else [(0, dy), (dx, 0)]
                if dx and dy and abs(x - px) == abs(y - py):
                    steps.insert(0, (dx, dy))
                for sx, sy in steps:
                    nx, ny = px + sx, py + sy
                    if (sx, sy) == (0, 0) or not w.in_room(nx, ny):
                        continue
                    q, wall = w.sq(nx, ny), g.pack.wall(w.sq(nx, ny).wall)
                    if wall.get('solid') or wall.get('door') or not (q.deco == 0 or q.deco in blood):
                        continue
                    pile = w.sq(px, py).deco
                    w.sq(px, py).deco = 0
                    q.deco, px, py, moved = pile, nx, ny, True
                    break
            entry[4:] = [px, py, 0 if moved else stuck + 1]
            if (px, py) == (x, y):
                if w.sq(x, y).mon == 0 and (x, y) != (p.X, p.Y):
                    w.sq(x, y).deco = 0
                    g.spawn(kind, x, y)
                    g.report(f'The {g.monster_name(kind)} rises again, made whole by the blood!', 12, (x, y), 'reborn')
                    g.count_hostiles()
                    continue
            elif entry[6] > 12:
                continue                                  # blocked for good
            keep.append(entry)
        if keep:
            p.more['reviving'] = keep
        else:
            p.more.pop('reviving', None)

    # ── elements: a weapon or ammunition that burns, freezes, poisons or drains (Deluxe) ──
    def apply_element(self, source: dict, e: Enemy, dealt: int):
        """A blow that hit e, struck with `source` (an item's row): its `element` (fire, ice, poison, drain)
        takes hold with a chance of `element_chance` percent (100 if left out). Fire and poison go on
        hurting for `element_turns` turns (3), `element_power` (3) a turn; ice freezes it that many turns;
        drain heals the hero by half the damage. A creature whose `resists` holds the element shrugs it off.
        Items without an element draw no random numbers, so the original's games are untouched."""
        kind = source.get('element')
        if not kind or e.life <= 0:
            return
        g = self.g
        chance = source.get('element_chance', 100)
        if chance < 100 and random(100) >= chance:
            return
        name = g.monster_name(e.type)
        if kind in (g.pack.trait(e.type, 'resists') or []):
            g.report(f'The {name} resists the {kind}.', 7, (e.x, e.y), 'resists')
            return
        power, turns = source.get('element_power', 3), source.get('element_turns', 3)
        if kind in ('fire', 'poison'):
            e.effects[kind] = [turns, power]
            g.report(f'The {name} {"catches fire" if kind == "fire" else "is poisoned"}!', 12 if kind == 'fire' else 10,
                     (e.x, e.y), 'burning' if kind == 'fire' else 'poisoned')
        elif kind == 'ice':
            e.att = -11 - turns
            g.report(f'The {name} is frozen.', 11, (e.x, e.y), 'frozen')
        elif kind == 'drain' and dealt > 0:
            h = self.p.hero
            h.life = min(h.mlife, h.life + max(1, dealt // 2))

    def tick_effects(self):
        """The end of a turn: what burns or is poisoned takes its damage and the turns run down; summoned
        clones whose time is up fade."""
        for e in list(self.w.enemies):
            ttl = e.__dict__.get('_ttl')
            if ttl is not None:
                if ttl <= 1:
                    self.w.sq(e.x, e.y).mon = 0
                    self.w.enemies.remove(e)
                    self.g.status.mons = len(self.w.enemies)
                    self.g.report(f'The {self.g.monster_name(e.type)} fades away.', 8, (e.x, e.y), 'fades')
                    continue
                e.__dict__['_ttl'] = ttl - 1
            for kind in list(e.effects):
                if e not in self.w.enemies or e.life <= 0:
                    break
                turns, power = e.effects[kind]
                if kind == 'fire':
                    self.g.play_at('afireball', e.x, e.y, 1)
                self.hurt(power, e, 3, by_hero=True, how='burning' if kind == 'fire' else 'poison')
                if turns <= 1:
                    e.effects.pop(kind, None)
                else:
                    e.effects[kind] = [turns - 1, power]

    # ── the hero attacks ──────────────────────────────────────────────────────
    def wake_on_attack(self, e: Enemy):
        h, sk = self.p.hero, self.p.skill
        if h.invisible > -1 and not self.g.disguised():
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
        """Walking into an enemy: herohit(), Ambidexterity second swing, kind-1 double strikes.
        Only animations and tones show the result, as in the original: ahit() on a hit, bhit() on a
        miss, a low beep for a ranged weapon."""
        p, g, items = self.p, self.g, self.g.items
        self.wake_on_attack(e)
        # movewhere: which side the blow comes from (1 right, 2 below, 3 left, 4 above)
        where = 1 if e.x < p.X else 3 if e.x > p.X else 2 if e.y < p.Y else 4
        for swing in (0, 1):
            if swing == 1:
                p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = p.bag.get(SLOT_OFFHAND, 0), p.bag.get(SLOT_WEAPON, 0)
                g.play('pause', 100)
            rules.status_update(p, self.g.status, items)
            g.start_swing()                           # FPS mode: the weapon in view swings (Deluxe)
            dmg = rules.hero_hit(p, e, items)
            if dmg > 0 and g.grown():
                dmg = dmg * 3 // 2                                # a giant hits half as hard again
            kind = items.tell(p.item(SLOT_WEAPON), IT_KIND)
            if dmg > 0 and kind == 3:
                g.tones((450, 20))                    # herohit(): a magic weapon rings
            name = g.monster_name(e.type)
            if kind == KIND_RANGED:
                g.tones((150, 150))
                g.report(f'Your {g.item_name(p.item(SLOT_WEAPON)).lower() or "bow"} is no use up close.', 7)
            elif dmg > 0:
                g.play_at('ahit', e.x, e.y, where, 1, in_view=False)     # FPS mode: the weapon shows it
                e.life -= dmg
                g.report(f'You hit the {name} for {dmg}.', 14, (e.x, e.y), dmg)
                steal = g.worn_sum('lifesteal')
                if steal:
                    p.hero.life = min(p.hero.mlife, p.hero.life + max(1, dmg * steal // 100))
                self.apply_element(g.pack.item(p.item(SLOT_WEAPON)), e, dmg)
                q = self.w.sq(e.x, e.y)
                if q.deco == 0 and e.life > 0 and bleeds(self.g.pack, e):
                    q.deco = self.g.pack.deco('blood')
                if kind == rules.KIND_DOUBLE and random(5) == 1:
                    g.play('pause', 100)
                    e.life -= dmg
                    g.play_at('ahit', e.x, e.y, where, 1, in_view=False)
                    g.report(f'You strike again for {dmg}!', 14, (e.x, e.y), dmg)
            else:
                g.swing_missed()                          # FPS mode: swing and a miss
                g.play_at('bhit', e.x, e.y, where, in_view=False)
                g.report(f'You miss the {name}.', 7, (e.x, e.y), 'miss')
            if swing == 1:
                p.bag[SLOT_WEAPON], p.bag[SLOT_OFFHAND] = p.bag.get(SLOT_OFFHAND, 0), p.bag.get(SLOT_WEAPON, 0)
                g.play('pause', 100)
                rules.status_update(p, self.g.status, items)
            off = p.item(SLOT_OFFHAND)
            if not (swing == 0 and p.skill.amb == 1 and g.pack.item_type(off) in ('weapon', 'launcher')
                    and e.life > 0):
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
            if e.ally or not (st.killer or e.type > 0 or e.att >= 0):
                continue
            if e.att == -1 and st.ems > 0:
                continue
            if self.g.pack.trait(e.type, 'invisible') and not self.g.foresight():
                continue
            out.append((d, e))
        out.sort(key=lambda t: t[0])
        return [e for _, e in out]

    def can_shoot(self) -> str | None:
        """None if a shot is possible, else the reason."""
        p, items = self.p, self.g.items
        wep, ammo = p.item(SLOT_WEAPON), p.item(SLOT_OFFHAND)
        if items.tell(wep, IT_KIND) != KIND_RANGED:
            return 'noweapon'
        if not self.g.pack.fires(wep, ammo):
            return 'noarrows' if ammo == 0 else 'badammo'
        return None

    def shoot(self, e: Enemy):
        """Fire at e: to-hit (8-dist)*10 + atk + 5 - def, damage = power (ignores armour)."""
        p, h = self.p, self.p.hero
        rules.status_update(p, self.g.status, self.g.items)
        self.g.start_swing()                          # FPS mode: the bow is drawn and let go (Deluxe)
        if e.att == -2:
            self.anger_npcs()
        self.wake_on_attack(e)
        if e.att not in (-4, 8):
            e.att = 9
        self.g.target = e
        d = distance(e.x - p.X, e.y - p.Y)
        if (8 - d) * 10 + h.atk + 5 - e.defense >= random(100) + 1:
            wep = p.item(SLOT_WEAPON)
            hit = self.g.pack.item(wep).get('missile_anim')
            self.g.fly(hit, (p.X, p.Y), (e.x, e.y), True)          # FPS mode: the flight (Deluxe)
            if hit:
                self.g.play_at(hit, e.x, e.y, 0)
            q = self.w.sq(e.x, e.y)
            if q.deco == 0 and e.life > 0 and bleeds(self.g.pack, e):
                q.deco = self.g.pack.deco('blood')
            dealt = self.hurt(h.power, e, 2, by_hero=True, how='shot')
            for src in (self.g.pack.item(wep), self.g.pack.item(p.item(SLOT_OFFHAND))):
                self.apply_element(src, e, dealt)          # a fire bow, fire arrows
        else:
            self.g.fly(self.g.pack.item(p.item(SLOT_WEAPON)).get('missile_anim'), (p.X, p.Y), (e.x, e.y), False)
            self.g.play_at('bhit', e.x, e.y, 6)
            self.g.tones((150, 50))
            self.g.report(f'Your shot misses the {self.g.monster_name(e.type)}.', 7, (e.x, e.y), 'miss')
        ammo = self.g.pack.item(p.item(SLOT_OFFHAND))
        p.bag[SLOT_OFFHAND] = self.g.pack.ammo_id(ammo.get('ammo'), ammo.get('count', 0) - 1)
        rules.status_update(p, self.g.status, self.g.items)

    # ── the enemies attack (main2, after the hero's action) ───────────────────
    def enemy_attacks(self):
        p, h, st, items = self.p, self.p.hero, self.g.status, self.g.items
        self.g.play('pause', 100 if st.ems > 0 else 50)      # main2() pauses before the enemies act
        for e in list(self.w.enemies):
            if e not in self.w.enemies or e.life <= 0:
                continue
            if not (e.att >= 0 or e.att <= -10 or e.att == -4):
                continue
            dx, dy = self.w.gap(e, p.X, p.Y)               # a big creature: from its nearest square
            adjacent = (dx == 1 and dy == 0) or (dy == 1 and dx == 0)
            if not adjacent and not (dx <= e.range and dy <= e.range and e.range > 1):
                continue
            if not (h.invisible == -1 or e.att in (-4, 8)):
                continue
            if e.moved and self.g.pack.trait(e.type, 'rests_after_moving'):
                continue
            if e.att != -4:
                e.moved = True
            name = self.g.monster_name(e.type)
            if e.range == 1 and e.atk != 0:
                self.enemy_melee(e, name)
            elif e.atk != 0 and not self.g.pack.trait(e.type, 'deceiver'):
                self.enemy_ranged(e, name)
            else:
                self.enemy_cast(e, name)

    def side_seen(self, e: Enemy) -> int:
        """side(), or in FPS mode the side as the hero sees it (Game.fps_side): only the stroke's
        picture differs."""
        return self.g.fps_side(e) if self.g.renderer.in_3d(self.g) else self.side(e)

    def side(self, e: Enemy) -> int:
        """Which side of the hero e attacks from, as ahit()/bhit2() draw it."""
        p = self.p
        return 3 if e.x < p.X else 1 if e.x > p.X else 2 if e.y > p.Y else 4

    def poison_hero(self):
        if self.g.worn_any('poison_immune'):
            self.g.report('Your armour keeps the poison out.', 11)
            return
        self.g.report('You are poisoned!', 10)
        self.p.hero.poisoned = 1
        self.g.play('ampoisoned2', 1)

    def enemy_melee(self, e: Enemy, name: str):
        p, h, g, items = self.p, self.p.hero, self.g, self.g.items
        self.reveal(e)
        dmg = rules.mon_hit(e, p, self.g.status, self.g.spells, g.pack)
        shielded = dmg == rules.SHIELDED
        if shielded:
            g.tones((400, 70), (350, 70))                 # monhit(): the Shield spell absorbs it
            dmg = 0
            g.report(f"Your Shield absorbs the {name}'s blow.", 11)
        parry = items.tell(p.item(SLOT_WEAPON), IT_KIND) in (2, 6) or \
            (p.skill.amb == 1 and items.tell(p.item(SLOT_OFFHAND), IT_KIND) in (2, 6))
        if parry and random(5) == 1:
            dmg = 0
            g.play_at('bhit2', p.X, p.Y, self.side_seen(e))
            g.report(f"You parry the {name}'s blow.", 11)
        elif dmg <= 0 and not shielded:
            g.report(f'The {name} misses you.', 7, (p.X, p.Y), 'miss')
        if dmg > 0:
            h.life -= dmg
            g.report(f'The {name} hits you for {dmg}.', 12, (p.X, p.Y), dmg)
            g.play_at('ahit', p.X, p.Y, self.side_seen(e), 2)
            thorns = g.worn_sum('thorns')
            if thorns and e.life > 0:
                self.hurt(thorns, e, 3, by_hero=True, how='thorns')   # what he wears hurts whoever strikes him
            self.bleed_hero()
            n = g.pack.trait(e.type, 'poison_melee')
            if n and random(n) == 1 and not h.poisoned:
                self.poison_hero()

    def enemy_ranged(self, e: Enemy, name: str):
        p, h = self.p, self.p.hero
        d = distance(e.x - p.X, e.y - p.Y)
        if d == 1:
            d = 99
            e.moved = False
        if e.atk + (8 - d) * 10 + 5 - h.defense >= random(100) + 1:
            hit = self.g.pack.trait(e.type, 'missile_anim')
            self.g.fly(hit, (e.x, e.y), (p.X, p.Y), True, towards_hero=True)
            if hit:
                self.g.play_at(hit, p.X, p.Y, 1)
            self.hurt(e.power, None, 2, e)
            self.bleed_hero()
            n = self.g.pack.trait(e.type, 'poison_ranged')
            if n and random(n) == 1 and not h.poisoned:
                self.poison_hero()
        else:
            self.g.fly(self.g.pack.trait(e.type, 'missile_anim'), (e.x, e.y), (p.X, p.Y), False, towards_hero=True)
            self.g.report(f"The {name}'s shot misses you.", 7, (p.X, p.Y), 'miss')

    def enemy_cast(self, e: Enemy, name: str):
        """main2(), a creature without a melee or missile attack: heal, raise, explode, or cast at the
        hero. The damage comes first and the animation after, as in the original."""
        g, w, p, h = self.g, self.w, self.p, self.p.hero
        trait = lambda name, default=None: g.pack.trait(e.type, name, default)
        if trait('heals_allies'):                          # the cleric heals a wounded ally
            for o in w.enemies:
                if o is e or not (o.att > -1 or o.att in (-4, -5)) or o.life >= o.mlife:
                    continue
                t1 = e.power
                o.life = min(o.mlife, o.life + t1 - t1 // 3 + random(2 * (t1 // 3)))
                g.play_at('dcast2', e.x, e.y)
                g.play_at('aheal2', o.x, o.y)
                e.moved = True
                break
        raised = trait('raises_dead')
        if raised:                                         # the necromancer raises a skeleton from bones
            ox, oy = w.origin
            for x in range(ox, ox + 10):
                for y in range(oy, oy + 10):
                    q = w.sq(x, y)
                    if q.deco == g.pack.deco('bones') and q.mon == 0 and (x, y) != (p.X, p.Y):
                        e.moved = True
                        g.play_at('dcast2', e.x, e.y)
                        q.deco = 0
                        e.life -= 2
                        g.play_at('asskeleton', x, y, 2)
                        g.spawn(raised, x, y)
                        break
                else:
                    continue
                break
            self.check_dead()                              # deadenemycheck(-1), raised or not
        blasts = trait('explodes')
        if blasts:                                         # the kamikaze demon: blasts, then it dies
            for _ in range(blasts):
                g.play_at('adarkhour', p.X, p.Y)
                self.hurt(e.power, None, 1, e)
                g.play_at('adarkhour', e.x, e.y)
            self.hurt(e.power * blasts, e, 1, e)
            return
        dmg = e.power
        if e.att != -4:
            dmg = self.hurt(e.power, None, 1, e)
        cast, deceiver = trait('cast_anim'), trait('deceiver')
        if cast:
            g.play_at(cast[0], p.X, p.Y, *cast[1:])
            n = trait('poison_cast')
            if n and dmg > 0 and random(n) == 1 and not h.poisoned:
                self.poison_hero()
        elif deceiver:                                     # the Deceiver turns summons into demons
            around = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                         if w.in_map(e.x + dx, e.y + dy) and w.sq(e.x + dx, e.y + dy).mon < -99)
            if random(2) == 0 and around > 1:
                g.play('screen_flash', 5)
                for o in w.enemies:
                    if o.type < -99:
                        o.type = deceiver['becomes']
                        for f in ('att', 'power', 'marm', 'atk', 'life'):
                            setattr(o, f, deceiver[f])
                        w.sq(o.x, o.y).mon = o.type
            else:
                g.play_at('aearthq', p.X, p.Y)
        if dmg > 0 and trait('drains_life'):
            g.play_at('adrain', e.x, e.y, 4)
            e.life += dmg
            e.mlife += dmg

    def reveal(self, e: Enemy):
        """An invisible creature shows itself when it attacks."""
        shown = self.g.pack.trait(e.type, 'reveals_as')
        if shown:
            e.type = shown
            self.w.sq(e.x, e.y).mon = shown

    def bleed_hero(self):
        h = self.p.hero
        q = self.w.sq(self.p.X, self.p.Y)
        if q.deco == 0 and h.mlife and h.life / h.mlife <= LOW_HEALTH:
            q.deco = self.g.pack.deco('blood')

    def fire_shield(self):
        """Shield of Fire burns adjacent enemies every turn."""
        p = self.p
        power = self.g.pack.fire_shield_power()
        for e in list(self.w.enemies):
            if e in self.w.enemies and abs(e.x - p.X) + abs(e.y - p.Y) == 1:
                self.g.play_at('afireball', e.x, e.y, 1)
                if self.hurt(power, e, 1, by_hero=True, how='Shield of Fire') == 0:
                    self.g.play_at('bhit', e.x, e.y, 5)
