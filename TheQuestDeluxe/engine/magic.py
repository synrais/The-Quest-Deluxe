"""Spells: port of cast() (RPG.CPP 0a45:832a).

Spells.dat columns: id, required INT, mana, range (0 = self), power, duration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .rules import random, SP_INT, SP_MANA, SP_RANGE, SP_POWER, SP_DURATION

if TYPE_CHECKING:
    from .game import Game

RING8 = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]


class Magic:
    """What a spell does comes from its effect in the pack's spells.json (heal, bolt, teleport,
    shield, fire_shield, freeze, ward, dark_hour, invisibility, summon, drain, earthquake)."""

    def __init__(self, game: 'Game'):
        self.g = game

    def effect(self, spell: int) -> str:
        return self.g.pack.spell(spell).get('effect', '')

    def anim(self, spell: int, x: int, y: int, **kw):
        a = self.g.pack.spell(spell).get('anim')
        if a:
            self.g.play_at(a[0], x, y, *a[1:], **kw)

    def tell(self, spell: int, col: int) -> int:
        return self.g.spells.tell(spell, col)

    def can_cast(self, spell: int) -> str | None:
        p = self.g.player
        if not spell or p.spells[spell] != 1:
            return "You don't know that spell."
        if self.tell(spell, SP_MANA) > p.hero.mana:
            return 'Not enough mana.'
        if self.tell(spell, SP_INT) > p.hero.intl:
            return 'You are not intelligent enough to cast that.'
        return None

    def fizzles(self, spell: int) -> bool:
        """Rashness (20% while enemies are near) and Invisibility's own 50% / shield conflicts."""
        p, st = self.g.player, self.g.status
        if p.hero.invisible > -1:
            p.hero.invisible = 0
        fail = False
        if p.skill.ras == 1 and st.ems > 0 and random(100) > 79:
            fail = True
        chance = self.g.pack.spell(spell).get('fizzle')
        if chance and (random(100) >= 100 - chance or (self.effect(spell) == 'invisibility' and
                                                        (st.Shield > 0 or st.fShield > 0))):
            fail = True
        if fail and p.skill.ras == 1:
            p.skill.ras = 3
        return fail

    # ── targeting rules (Enter in the cast cursor) ────────────────────────────
    def valid_target(self, spell: int, x: int, y: int) -> bool:
        w, p, st = self.g.world, self.g.player, self.g.status
        q, eff = w.sq(x, y), self.effect(spell)
        if (q.wall != 0 or self.g.pack.item_type(q.item) in ('teleporter', 'exit')) and eff != 'earthquake':
            return False
        if (x, y) == (p.X, p.Y) and eff != 'earthquake':
            return False
        if q.mon < 0 and not st.killer and eff not in ('summon', 'teleport'):
            return False
        if eff in ('teleport', 'summon') and q.mon != 0:
            return False
        if self.g.pack.spell(spell).get('needs_target') and q.mon == 0:
            return False
        return True

    def in_range(self, spell: int, x: int, y: int) -> bool:
        r = self.tell(spell, SP_RANGE)
        p = self.g.player
        return abs(x - p.X) <= r and abs(y - p.Y) <= r and self.g.world.in_room(x, y)

    # ── effects ───────────────────────────────────────────────────────────────
    def strike(self, spell: int, e, x: int, y: int):
        """cast()'s common blow: Honor is engaged, hurt(power, w, 1, -1), and bhit(5) (the spell is
        absorbed) when it did no damage. The original shows no text for any of this."""
        g, p = self.g, self.g.player
        if p.skill.hon == 1:
            p.skill.hon = 2
        if g.combat.hurt(self.tell(spell, SP_POWER), e, 1, by_hero=True, how=g.pack.spell_name(spell)) == 0:
            g.play_at('bhit', x, y, 5)

    def cast_self(self, spell: int) -> None:
        """The range-0 half of cast(): mana first, then each spell with its animation on the hero."""
        g, p, h, st = self.g, self.g.player, self.g.player.hero, self.g.status
        h.mana -= self.tell(spell, SP_MANA)
        power, dur = self.tell(spell, SP_POWER), self.tell(spell, SP_DURATION)
        eff, sp = self.effect(spell), g.pack.spell(spell)
        ring = [(p.X + dx, p.Y + dy) for dx, dy in RING8]
        if eff == 'heal':
            g.report(f'You heal {min(power, max(0, h.mlife - h.life))} life.', 10, (p.X, p.Y),
                     f'+{min(power, max(0, h.mlife - h.life))}')
            h.life = min(h.mlife, h.life + power)
            self.anim(spell, p.X, p.Y)
        elif eff == 'invisibility':
            h.invisible = dur + 1
            for e in g.world.enemies:
                if e.att > 0 and e.att != 8 and e.att > -10:
                    e.att = -5
            self.anim(spell, p.X, p.Y)
        elif eff == 'shield':
            st.Shield, st.fShield = dur, 0
            self.anim(spell, p.X, p.Y)
        elif eff == 'fire_shield':
            st.fShield, st.Shield = dur, 0
            self.anim(spell, p.X, p.Y)
        elif eff == 'ward':
            self.area(spell, ring)
        elif eff == 'dark_hour':
            h.mana = 0
            for _ in range(sp.get('repeat', 1)):
                self.area(spell, ring)

    def area(self, spell: int, tiles):
        """Black Ward / Dark Hour: each square around the hero in turn, animation then the blow."""
        g = self.g
        for x, y in tiles:
            if not g.world.in_room(x, y):
                continue
            self.anim(spell, x, y)
            e = g.world.enemy_at(x, y)
            if e:
                self.strike(spell, e, x, y)

    def cast_at(self, spell: int, x: int, y: int) -> None:
        """The targeted half of cast(), in the original order."""
        g, w, p, h = self.g, self.g.world, self.g.player, self.g.player.hero
        target = w.enemy_at(x, y)
        h.mana -= self.tell(spell, SP_MANA)
        power = self.tell(spell, SP_POWER)
        eff, sp = self.effect(spell), g.pack.spell(spell)
        if eff == 'bolt':
            for _ in range(sp.get('repeat', 1)):
                self.anim(spell, x, y)
            if sp.get('empties_mana'):
                h.mana = 0
        if eff == 'drain':                                  # life drain
            if p.skill.hon == 1:
                p.skill.hon = 2
            g.play_at('adrain', x, y, 1)
            dealt = g.combat.hurt(power, target, 1, by_hero=True, how=g.pack.spell_name(spell))
            if dealt < 1:
                g.play_at('bhit', x, y, 5)
            g.play_at('adrain', p.X, p.Y, 2)
            if dealt > 0:
                h.life = min(h.mlife, h.life + dealt)
            return
        if eff == 'summon':
            self.anim(spell, x, y)
            g.spawn(sp['creature'], x, y)
            return
        if eff == 'teleport':
            def move(sx, sy):
                ox, oy = w.origin
                p.X, p.Y = ox + sx - 1, oy + sy - 1
            g.play_at('ateleport', x, y, *g.on_screen(p.X, p.Y), on_move=move)
            return
        if eff == 'freeze':                                 # ring of ice: freeze if it beats magic armour
            self.anim(spell, x, y)
            g.combat.hurt(0, target, 1, by_hero=True, quiet=True)   # even with nobody there: hurt(0, -1, ...)
            if target:
                power_of = spell if g.pack.fixed('shield_ice') else sp.get('freeze_power_of', spell)
                if self.tell(power_of, SP_POWER) > target.marm:    # Quest I: spell 4's
                    target.att = -11 - self.tell(spell, SP_DURATION)
                    g.report(f'The {g.monster_name(target.type)} is frozen.', 11, (x, y), 'frozen')
                else:
                    g.play_at('bhit', x, y, 5)
                    g.report(f'The {g.monster_name(target.type)} resists the ice.', 7, (x, y), 'resists')
            return
        if eff == 'earthquake':                             # the cross; the centre may shake again
            ww = 0
            while ww < 5:
                dx, dy = ((0, 0), (-1, 0), (0, -1), (1, 0), (0, 1))[ww]
                tx, ty = x + dx, y + dy
                if w.in_room(tx, ty):
                    g.play_at('aearthq', tx, ty)
                    e = w.enemy_at(tx, ty)
                    if e:
                        self.strike(spell, e, tx, ty)
                    elif (tx, ty) == (p.X, p.Y):
                        g.combat.hurt(power, None, 1, how=g.pack.spell_name(spell))
                        if h.life < -5:
                            return
                if ww == 0 and random(3) == 0:
                    g.play('pause', 100)
                    ww -= 1
                ww += 1
            return
        if target:
            self.strike(spell, target, x, y)
