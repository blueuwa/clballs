import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "SHADE",
    "filename": "6.png",
    "max_hp": 1800,
    "speed_mult": 1.0,
    "radius": 30,
    "contact_damage": 5,

    "max_super": 100,
    "super_per_hit": 2,
    "super_per_contact": 5,
}

# Main attack: throws 3 hooked blades in a cone. They bounce off walls for 1 second.
ABILITY = {
    "blades": 3,
    "cone_angle": 0.35,
    "damage": 25,
    "speed": 12.0,
    "lifetime": 60,
    "throw_cooldown": 40,
    "hit_cooldown": 20,
    "radius": 14,
    "spin": 0.25,
}

# Super: Summons a blizzard. Snow falls, enemy projectiles are slowed, Shade's are faster & stronger.
ULTIMATE = {
    "duration": 300,
    "enemy_slow": 0.65,
    "enemy_proj_mult": 0.4,
    "shade_proj_mult": 1.4,
    "shade_damage_mult": 1.5,
    "snow_color": (220, 240, 255),
}
# ===========================================================

STEEL = (214, 220, 232)
HANDLE = (230, 60, 70)

_avatar_cache = {}


def make_avatar(radius):
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(40):
        t = i / 39
        col = (int(18 + 55 * t), int(18 + 55 * t), int(26 + 62 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.9))))
    for k in range(12):
        a = k * TAU / 12
        pts = [(c + math.cos(a - 0.17) * c * 0.55, c + math.sin(a - 0.17) * c * 0.55),
               (c + math.cos(a) * c * 0.97, c + math.sin(a) * c * 0.97),
               (c + math.cos(a + 0.17) * c * 0.55, c + math.sin(a + 0.17) * c * 0.55)]
        pygame.draw.polygon(big, (120, 122, 135), pts)
        pygame.draw.polygon(big, (200, 202, 215), pts, 2)
    for sx in (-1, 1):
        ex, ey = c + sx * c * 0.26, c - c * 0.06
        pygame.draw.ellipse(big, (255, 255, 255), pygame.Rect(ex - c * 0.14, ey - c * 0.09, c * 0.28, c * 0.18))
        pygame.draw.circle(big, (20, 20, 30), (int(ex + sx * c * 0.02), int(ey)), int(c * 0.05))
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


class DarkBlade:
    """A hooked blade that bounces off walls for 1 second."""

    def __init__(self, owner, target, pos, angle):
        A = ABILITY
        self.owner = owner
        self.target = target
        self.x, self.y = pos
        self.base_speed = A["speed"]
        self.vx = math.cos(angle) * self.base_speed
        self.vy = math.sin(angle) * self.base_speed
        self.radius = A["radius"]
        self.rot = random.uniform(0, TAU)
        self.timer = A["lifetime"]
        self.hit_cd = 0
        self.active = True
        self.t = 0

    def update(self, explosions):
        if not self.active:
            return
        A = ABILITY
        self.t += 1
        self.timer -= 1
        if self.hit_cd > 0:
            self.hit_cd -= 1
        if self.timer <= 0:
            self.active = False
            return

        self.rot += A["spin"]

        # Speed multiplier if the blizzard is active
        mult = ULTIMATE["shade_proj_mult"] if getattr(self.owner, "blizzard_timer", 0) > 0 else 1.0
        
        self.x += self.vx * mult
        self.y += self.vy * mult

        # Wall bounce
        bounced = False
        if self.x - self.radius <= ARENA_LEFT:
            self.x = ARENA_LEFT + self.radius
            self.vx = abs(self.vx)
            bounced = True
        elif self.x + self.radius >= ARENA_RIGHT:
            self.x = ARENA_RIGHT - self.radius
            self.vx = -abs(self.vx)
            bounced = True
        if self.y - self.radius <= ARENA_TOP:
            self.y = ARENA_TOP + self.radius
            self.vy = abs(self.vy)
            bounced = True
        elif self.y + self.radius >= ARENA_BOTTOM:
            self.y = ARENA_BOTTOM - self.radius
            self.vy = -abs(self.vy)
            bounced = True

        if bounced:
            sounds.play("bump")

        # Hit enemy
        t = self.target
        if t and t.hp > 0 and self.hit_cd <= 0:
            tp = t.body.position
            if math.hypot(self.x - tp.x, self.y - tp.y) <= self.radius + t.radius:
                self.hit_cd = A["hit_cooldown"]
                dmg = A["damage"]
                if getattr(self.owner, "blizzard_timer", 0) > 0:
                    dmg *= ULTIMATE["shade_damage_mult"]
                t.hp -= int(dmg)
                self.owner.add_super(self.owner.super_per_hit)
                sounds.play("hit")
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.0, 4.0)) for _ in range(6)]
                explosions.append({"x": tp.x, "y": tp.y, "radius": 24, "timer": 10, "max": 10, "color": (200, 200, 220), "sparks": sparks})

    def draw(self, screen):
        if not self.active:
            return
        x, y, r = int(self.x), int(self.y), self.radius
        if self.timer < 15 and (self.timer // 2) % 2 == 0:
            return

        ca, sa = math.cos(self.rot), math.sin(self.rot)

        def P(f, s):
            return (x + ca * r * f - sa * r * s, y + sa * r * f + ca * r * s)

        blade_pts = [P(1.6, 0.0), P(0.5, -0.4), P(-0.6, -0.9), P(-0.9, -0.6), P(0.1, 0.0), P(-0.9, 0.6), P(-0.6, 0.9), P(0.5, 0.4)]
        pygame.draw.polygon(screen, (30, 32, 40), blade_pts)
        pygame.draw.polygon(screen, STEEL, blade_pts, 2)
        
        gem_pts = [P(0.2, 0.0), P(-0.2, -0.25), P(-0.5, 0.0), P(-0.2, 0.25)]
        pygame.draw.polygon(screen, (200, 220, 255), gem_pts)
        pygame.draw.circle(screen, (255, 255, 255), (int(P(0, 0)[0]), int(P(0, 0)[1])), 3)


class Snowflake:
    def __init__(self):
        self.x = random.uniform(ARENA_LEFT, ARENA_RIGHT)
        self.y = random.uniform(ARENA_TOP, ARENA_BOTTOM)
        self.speed = random.uniform(1.5, 4.0)
        self.size = random.randint(2, 4)
        self.sway = random.uniform(0, TAU)
        self.sway_speed = random.uniform(0.02, 0.05)

    def update(self):
        self.y += self.speed
        self.sway += self.sway_speed
        self.x += math.sin(self.sway) * 0.5
        if self.y > ARENA_BOTTOM:
            self.y = ARENA_TOP
            self.x = random.uniform(ARENA_LEFT, ARENA_RIGHT)

    def draw(self, screen):
        pygame.draw.circle(screen, ULTIMATE["snow_color"], (int(self.x), int(self.y)), self.size)


class Shade(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):
            self.surface = make_avatar(self.radius)
        self.throw_cd = 0
        self.blizzard_timer = 0
        self.snowflakes = []

    def _throw(self, target, projectiles):
        A = ABILITY
        x, y = self.body.position.x, self.body.position.y
        base = math.atan2(target.body.position.y - y, target.body.position.x - x)
        sounds.play("star")
        for i in range(A["blades"]):
            off = (i - (A["blades"] - 1) / 2) * A["cone_angle"]
            projectiles.append(DarkBlade(self, target, (x, y), base + off))
        self.throw_cd = A["throw_cooldown"]

    def _ultimate(self):
        self.blizzard_timer = ULTIMATE["duration"]
        self.snowflakes = [Snowflake() for _ in range(80)]
        sounds.play("super")
        sounds.play("boom")

    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        alive = target is not None and target.hp > 0

        if self.throw_cd > 0:
            self.throw_cd -= 1

        if alive and self.throw_cd <= 0:
            self._throw(target, projectiles)

        if alive and self.super_charge >= self.max_super and self.blizzard_timer <= 0:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate()

        # Blizzard active effects
        if self.blizzard_timer > 0:
            self.blizzard_timer -= 1
            if alive:
                # FORCE the slow to stay permanently active on the enemy
                target.slow_timer = max(target.slow_timer, 10)
                target.slow_factor = min(target.slow_factor, ULTIMATE["enemy_slow"])
                target.slow_color = ULTIMATE["snow_color"]
            
            for f in self.snowflakes:
                f.update()

    def draw(self, screen):
        if self.hp <= 0:
            return
            
        if self.blizzard_timer > 0:
            tint = pygame.Surface((ARENA_RIGHT - ARENA_LEFT, ARENA_BOTTOM - ARENA_TOP), pygame.SRCALPHA)
            tint.fill((30, 60, 100, 60))
            screen.blit(tint, (ARENA_LEFT, ARENA_TOP))
            
            for f in self.snowflakes:
                f.draw(screen)

        super().draw(screen)
        
        if self.blizzard_timer > 0:
            x, y, r = int(self.body.position.x), int(self.body.position.y), self.radius
            glow = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ULTIMATE["snow_color"], 80), (r*2, r*2), r + 15)
            screen.blit(glow, (x - r*2, y - r*2))