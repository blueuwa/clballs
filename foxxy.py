import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "FOXXY",
    "filename": "2.png",
    "max_hp": 2500,
    "speed_mult": 1.2,
    "radius": 30,
    "contact_damage": 5,

    "max_super": 100,
    "super_per_hit": 1.0,
    "super_per_contact": 5,
}

ABILITY = {
    "scratch_cooldown": 1,       
    "scratch_damage": 5,
    "scratch_range": 140,
    "scratch_arc": 160,
    "claw_color": (255, 150, 40),
}

ULTIMATE = {
    "duration": 120,          
    "ambush_damage": 200,     
    "ambush_radius": 150,     
    "strike_color": (255, 220, 100),
    
    "turret_duration": 300,   
    "turret_fire_rate": 12,   
    "turret_bullet_damage": 30,
    "turret_bullet_speed": 9.0,
    "turret_explosion_radius": 100,
    "turret_explosion_damage": 150,
}
# ===========================================================

_avatar_cache = {}

def make_avatar(radius):
    """Built-in orange fox design (used if 2.png is missing)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)

    for i in range(40):
        t = i / 39
        col = (int(200 + 55 * t), int(100 + 60 * t), int(20 + 20 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.85))))

    pygame.draw.ellipse(big, (240, 240, 240), pygame.Rect(c - c * 0.5, c + c * 0.1, c * 1.0, c * 0.6))
    pygame.draw.polygon(big, (200, 100, 20), [(c - c*0.6, c - c*0.3), (c - c*0.3, c - c*0.9), (c, c - c*0.4)])
    pygame.draw.polygon(big, (200, 100, 20), [(c + c*0.6, c - c*0.3), (c + c*0.3, c - c*0.9), (c, c - c*0.4)])
    pygame.draw.circle(big, (20, 20, 20), (int(c - c*0.2), int(c - c*0.05)), int(c*0.06))
    pygame.draw.circle(big, (20, 20, 20), (int(c + c*0.2), int(c - c*0.05)), int(c*0.06))
    pygame.draw.circle(big, (20, 20, 20), (c, int(c + c*0.2)), int(c*0.05))

    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


class FoxBullet:
    def __init__(self, owner, target, pos, angle):
        self.owner = owner
        self.target = target
        self.x, self.y = pos
        self.vx = math.cos(angle) * ULTIMATE["turret_bullet_speed"]
        self.vy = math.sin(angle) * ULTIMATE["turret_bullet_speed"]
        self.radius = 8
        self.active = True
        self.t = 0

    def update(self, explosions):
        if not self.active: return
        self.t += 1
        
        if self.target and self.target.hp > 0:
            dx = self.target.body.position.x - self.x
            dy = self.target.body.position.y - self.y
            d = math.hypot(dx, dy) or 1.0
            sp = ULTIMATE["turret_bullet_speed"]
            self.vx += (dx / d * sp - self.vx) * 0.15
            self.vy += (dy / d * sp - self.vy) * 0.15
            
            v_len = math.hypot(self.vx, self.vy) or 1.0
            self.vx = (self.vx / v_len) * sp
            self.vy = (self.vy / v_len) * sp

        self.x += self.vx
        self.y += self.vy

        if (self.x - self.radius <= ARENA_LEFT or self.x + self.radius >= ARENA_RIGHT or
                self.y - self.radius <= ARENA_TOP or self.y + self.radius >= ARENA_BOTTOM):
            self.active = False
            return

        t = self.target
        if t and t.hp > 0:
            if math.hypot(self.x - t.body.position.x, self.y - t.body.position.y) <= self.radius + t.radius:
                t.hp -= ULTIMATE["turret_bullet_damage"]
                self.active = False
                sounds.play("hit")
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.0, 4.0)) for _ in range(6)]
                explosions.append({"x": self.x, "y": self.y, "radius": 20, "timer": 10, "max": 10, "color": (255, 150, 40), "sparks": sparks})

    def draw(self, screen):
        if not self.active: return
        pygame.draw.circle(screen, (255, 100, 0), (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, (255, 220, 100), (int(self.x), int(self.y)), self.radius - 2)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), 2)


class FoxTurret:
    def __init__(self, owner, target, pos):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        self.x, self.y = pos
        self.timer = U["turret_duration"]
        self.fire_cd = 0
        self.active = True
        self.rot = 0
        self.t = 0

    def update(self, explosions):
        if not self.active: return
        U = ULTIMATE
        self.t += 1
        self.timer -= 1
        if self.timer <= 0:
            self._explode(explosions)
            return

        if self.fire_cd > 0:
            self.fire_cd -= 1
            
        t = self.target
        if t and t.hp > 0:
            self.rot = math.atan2(t.body.position.y - self.y, t.body.position.x - self.x)
            if self.fire_cd <= 0:
                self.fire_cd = U["turret_fire_rate"]
                sounds.play("star")
                self.owner._proj.append(FoxBullet(self.owner, t, (self.x, self.y), self.rot))
                
    def _explode(self, explosions):
        U = ULTIMATE
        self.active = False
        sounds.play("boom")
        sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.5, 5.0)) for _ in range(15)]
        explosions.append({"x": self.x, "y": self.y, "radius": U["turret_explosion_radius"],
                           "timer": 20, "max": 20, "color": (255, 150, 40), "sparks": sparks})
        t = self.target
        if t and t.hp > 0:
            if math.hypot(self.x - t.body.position.x, self.y - t.body.position.y) <= U["turret_explosion_radius"] + t.radius:
                t.hp -= U["turret_explosion_damage"]

    def draw(self, screen):
        if not self.active: return
        x, y = int(self.x), int(self.y)
        pygame.draw.circle(screen, (40, 30, 20), (x, y), 20)
        pygame.draw.circle(screen, (150, 80, 20), (x, y), 16)
        
        ca, sa = math.cos(self.rot), math.sin(self.rot)
        bx, by = x + ca * 25, y + sa * 25
        pygame.draw.line(screen, (255, 120, 30), (x, y), (bx, by), 8)
        pygame.draw.circle(screen, (255, 200, 50), (x, y), 10)
        
        if (self.t // 10) % 2 == 0:
            pygame.draw.circle(screen, (255, 50, 50), (x, y), 5)


class Foxxy(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):
            self.surface = make_avatar(self.radius)
            
        self.scratch_cooldown = 0
        self.invisible_timer = 0
        self.original_dmg = self.contact_damage
        self._proj = None

    def _ultimate(self, target, projectiles):
        self.invisible_timer = ULTIMATE["duration"]
        self.speed_override = self.base_speed * 1.5 # Move faster while invisible
        self.original_dmg = self.contact_damage
        self.contact_damage = 0
        
        projectiles.append(FoxTurret(self, target, (self.body.position.x, self.body.position.y)))
        
        sounds.play("dash")
        sounds.play("super")
        self.popups.append(("VANISHED!", (150, 150, 150)))

    def _ambush_strike(self, target):
        U = ULTIMATE
        self.speed_override = None
        self.contact_damage = self.original_dmg
        
        if target and target.hp > 0:
            tx, ty = target.body.position.x, target.body.position.y
            if math.hypot(self.body.position.x - tx, self.body.position.y - ty) <= U["ambush_radius"]:
                target.hp -= U["ambush_damage"]
                target.flash(U["strike_color"], 30)
                target.popups.append(("AMBUSH!", U["strike_color"]))
                target.apply_stun(30, 0, U["strike_color"])
                sounds.play("boom")

    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
            
        self._proj = projectiles

        if self.invisible_timer > 0:
            self.invisible_timer -= 1
            if self.invisible_timer <= 0:
                self._ambush_strike(target)
        else:
            if self.scratch_cooldown > 0:
                self.scratch_cooldown -= 1

            pos = (self.body.position.x, self.body.position.y)

            if target and target.hp > 0 and self.scratch_cooldown <= 0:
                t_pos = target.body.position
                dx, dy = t_pos.x - pos[0], t_pos.y - pos[1]
                dist = math.hypot(dx, dy)

                vx, vy = self.body.velocity
                facing = math.atan2(vy, vx) if (vx or vy) else 0
                diff = (math.atan2(dy, dx) - facing + math.pi) % TAU - math.pi
                in_arc = abs(diff) <= math.radians(ABILITY["scratch_arc"]) / 2

                if dist <= ABILITY["scratch_range"] and in_arc:
                    target.hp -= ABILITY["scratch_damage"]
                    self.add_super(self.super_per_hit)
                    self.scratch_cooldown = ABILITY["scratch_cooldown"]
                    sounds.play("scratch")

                    # Curved Claw Aura (Centered on Foxxy, swiping toward enemy)
                    angle = math.atan2(dy, dx)
                    def draw_aura_claw(screen, cx=int(self.body.position.x), cy=int(self.body.position.y), a=angle):
                        for i in range(3):
                            r = self.radius + 15 + i * 8
                            spread = 0.5
                            pts = []
                            for step in range(10):
                                theta = a - spread + (spread * 2) * (step / 9.0)
                                px = cx + math.cos(theta) * (r + random.uniform(-2, 2))
                                py = cy + math.sin(theta) * (r + random.uniform(-2, 2))
                                pts.append((px, py))
                            if len(pts) > 1:
                                pygame.draw.lines(screen, ABILITY["claw_color"], False, pts, 5)
                                pygame.draw.lines(screen, (255, 255, 255), False, pts, 2)

                    scratch_effects.append({
                        "x": self.body.position.x, "y": self.body.position.y, "sprite": None, "timer": 15, "draw": draw_aura_claw
                    })

        if self.super_charge >= self.max_super and self.invisible_timer <= 0:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)

    def draw(self, screen):
        if self.hp <= 0:
            return
            
        if self.invisible_timer > 0:
            x, y = int(self.body.position.x), int(self.body.position.y)
            r = self.radius
            alpha = 30 + int(20 * math.sin(self.invisible_timer * 0.5))
            surf = pygame.Surface((r*3, r*3), pygame.SRCALPHA)
            pygame.draw.circle(surf, (100, 150, 255, alpha), (int(r*1.5), int(r*1.5)), r + 15)
            pygame.draw.circle(surf, (255, 255, 255, alpha * 2), (int(r*1.5), int(r*1.5)), r + 5, 2)
            screen.blit(surf, (x - r*1.5, y - r*1.5))
            
            ghost = self.surface.copy()
            ghost.set_alpha(80)
            screen.blit(ghost, (x - r, y - r))
            return

        super().draw(screen)