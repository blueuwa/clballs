import math
import random
import pygame
import pymunk
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "HYPER",
    "filename": "13.png",
    "max_hp": 2500,
    "speed_mult": 1.0,        
    "radius": 30,
    "contact_damage": 5,      

    "max_super": 100,         
    "super_per_hit": 10,      
    "super_per_contact": 5,   
}

# Main attack: HYPER activates a cyan frenzy. He lunges at the enemy and his contact damage spikes to 50.
ABILITY = {
    "cooldown": 120,          # frames between attacks (120 = 2 seconds)
    "trigger_range": 400,     # only activates if the enemy is within this distance
    "frenzy_duration": 90,    # how long the frenzy lasts (90 = 1.5 seconds)
    "frenzy_damage": 150,      # contact damage while frenzied
    "hit_cooldown": 30,       # frames between frenzy damage ticks
    "lunge_speed": 18.0,      # speed boost when he first activates it
    "aura_color": (50, 255, 255),
}

# Super: HYPER phases out of reality for 4 seconds, passing through the enemy to weaken them.
ULTIMATE = {
    "duration": 240,          # 4 seconds at 60fps
    "phase_speed": 14.0,      # constant speed while phasing
    "hit_damage": 100,        # damage when passing through
    "pass_cd": 60,            # 1 second cooldown between 100-dmg hits
    
    "weakness_frames": 120,   # 2 seconds of weakness
    "weakness_damage": 80,     # deals 1 dmg (out of 10) while cursed
    
    "trail_frames": 15,       # length of the ghost trail
}
# ===========================================================

CYAN = (50, 255, 255)
DARK_RED = (180, 20, 40)
PHASE_BLUE = (80, 150, 255)
PURPLE = (200, 80, 255)

_avatar_cache = {}

def make_avatar(radius):
    """Built-in design for HYPER (used if 13.png is missing)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)

    # body gradient: deep cyan to bright cyan
    for i in range(40):
        t = i / 39
        col = (int(10 + 40 * t), int(60 + 160 * t), int(80 + 120 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.85))))

    # visor/eyes
    pygame.draw.ellipse(big, (15, 20, 30), pygame.Rect(c - c * 0.5, c - c * 0.15, c, c * 0.3))
    pygame.draw.ellipse(big, CYAN, pygame.Rect(c - c * 0.4, c - c * 0.08, c * 0.8, c * 0.16))
    pygame.draw.circle(big, (255, 255, 255), (c, c), int(c * 0.05))

    # mask to circle
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


class HyperPhase:
    """The super: HYPER flies around incredibly fast, phasing through the enemy and cursing them."""
    def __init__(self, owner, target):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        self.timer = U["duration"]
        self.pass_cd = 0
        self.active = True
        
        # GHOST MODE: remove from physics engine so he passes through walls and enemies
        self.space = owner.body.space
        self.space.remove(owner.body, owner.shape)
        
        self.trail = []
        
        # Start flying towards the enemy
        o, t = owner, target
        self.angle = math.atan2(t.body.position.y - o.body.position.y, t.body.position.x - o.body.position.x)

    def _bounce(self):
        o = self.owner
        x, y = o.body.position.x, o.body.position.y
        r = o.radius
        bounced = False
        
        # Manual wall bounces
        if x - r <= ARENA_LEFT:
            self.angle = math.pi - self.angle
            o.body.position = (ARENA_LEFT + r + 2, y)
            bounced = True
        elif x + r >= ARENA_RIGHT:
            self.angle = math.pi - self.angle
            o.body.position = (ARENA_RIGHT - r - 2, y)
            bounced = True
            
        if y - r <= ARENA_TOP:
            self.angle = -self.angle
            o.body.position = (x, ARENA_TOP + r + 2)
            bounced = True
        elif y + r >= ARENA_BOTTOM:
            self.angle = -self.angle
            o.body.position = (x, ARENA_BOTTOM - r - 2)
            bounced = True
            
        if bounced:
            sounds.play("bump")

    def update(self, explosions):
        if not self.active:
            return
        U = ULTIMATE
        o, t = self.owner, self.target
        self.timer -= 1
        if self.pass_cd > 0:
            self.pass_cd -= 1

        if self.timer <= 0 or o.hp <= 0:
            # Re-insert into physics engine
            self.space.add(o.body, o.shape)
            # Push away slightly so we don't get stuck inside the enemy
            dx = o.body.position.x - t.body.position.x
            dy = o.body.position.y - t.body.position.y
            d = math.hypot(dx, dy) or 1.0
            o.apply_knockback(dx/d, dy/d, 600, 15)
            self.active = False
            return

        # Manually move (bypassing physics)
        o.body.position = (o.body.position.x + math.cos(self.angle) * U["phase_speed"],
                           o.body.position.y + math.sin(self.angle) * U["phase_speed"])
        self._bounce()

        # Store trail for the visual effect
        self.trail.append((o.body.position.x, o.body.position.y))
        if len(self.trail) > U["trail_frames"]:
            self.trail.pop(0)

        # Hit the enemy
        if t.hp > 0 and self.pass_cd <= 0:
            tp = t.body.position
            if math.hypot(o.body.position.x - tp.x, o.body.position.y - tp.y) <= o.radius + t.radius:
                self.pass_cd = U["pass_cd"]
                t.hp -= U["hit_damage"]
                
                # Apply the weakness curse TO THE ENEMY
                t.weakness_timer = U["weakness_frames"]
                t.weakness_dmg = U["weakness_damage"]
                t.popups.append(("WEAKENED!", PURPLE))
                
                sounds.play("hit")
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.0, 5.0))
                          for _ in range(15)]
                explosions.append({"x": tp.x, "y": tp.y, "radius": 50, "timer": 15, "max": 15,
                                   "color": PURPLE, "sparks": sparks})

    def draw(self, screen):
        if not self.active:
            return
        # Draw the ghost trail
        o = self.owner
        U = ULTIMATE
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            f = (i + 1) / (n + 1)
            r = max(1, int(o.radius * f))
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*PHASE_BLUE, int(180 * f)), (r, r), r)
            screen.blit(surf, (int(tx - r), int(ty - r)))


class Hyper(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):
            self.surface = make_avatar(self.radius)
        self.attack_cd = 0
        self.phasing = False
        
        # Frenzy (main attack) variables
        self.frenzy_timer = 0
        self.frenzy_hit_cd = 0

    def _start_frenzy(self, target):
        self.frenzy_timer = ABILITY["frenzy_duration"]
        self.frenzy_hit_cd = 0
        self.attack_cd = ABILITY["cooldown"]
        
        # Lunge towards the enemy
        dx = target.body.position.x - self.body.position.x
        dy = target.body.position.y - self.body.position.y
        d = math.hypot(dx, dy) or 1.0
        self.apply_knockback(dx / d, dy / d, ABILITY["lunge_speed"] * 60, 15)
        
        self.popups.append(("FRENZY!", CYAN))
        sounds.play("dash")

    def _ultimate(self, target, projectiles):
        projectiles.append(HyperPhase(self, target))
        self.phasing = True
        sounds.play("super")

    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        alive = target is not None and target.hp > 0
        
        if self.attack_cd > 0:
            self.attack_cd -= 1
        if self.frenzy_timer > 0:
            self.frenzy_timer -= 1
        if self.frenzy_hit_cd > 0:
            self.frenzy_hit_cd -= 1
            
        # check if our active objects are still running
        self.phasing = any(isinstance(p, HyperPhase) and p.active for p in projectiles)

        # Main attack activation
        if alive and self.attack_cd <= 0 and not self.phasing and self.frenzy_timer <= 0:
            dx = target.body.position.x - self.body.position.x
            dy = target.body.position.y - self.body.position.y
            if math.hypot(dx, dy) <= ABILITY["trigger_range"]:
                self._start_frenzy(target)

        # Frenzy contact damage
        if alive and self.frenzy_timer > 0 and self.frenzy_hit_cd <= 0 and not self.phasing:
            tp = target.body.position
            if math.hypot(self.body.position.x - tp.x, self.body.position.y - tp.y) <= self.radius + target.radius + 5:
                target.hp -= ABILITY["frenzy_damage"]
                self.add_super(self.super_per_hit)
                self.frenzy_hit_cd = ABILITY["hit_cooldown"]
                
                sounds.play("hit")
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(3.0, 6.0))
                          for _ in range(10)]
                scratch_effects.append({"x": tp.x, "y": tp.y, "sprite": None, "timer": 12,
                                        "draw": lambda s, x=int(tp.x), y=int(tp.y): self._draw_frenzy_burst(s, x, y)})

        # Super
        if alive and self.super_charge >= self.max_super and not self.phasing:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)

    def _draw_frenzy_burst(self, screen, x, y):
        for _ in range(8):
            a = random.uniform(0, TAU)
            ln = random.uniform(20, 40)
            end = (x + math.cos(a) * ln, y + math.sin(a) * ln)
            pygame.draw.line(screen, CYAN, (x, y), end, 3)
            pygame.draw.line(screen, (255, 255, 255), (x, y), end, 1)

    def draw(self, screen):
        if self.hp <= 0:
            return
            
        # Cyan glowing aura while frenzied
        if self.frenzy_timer > 0:
            x, y = int(self.body.position.x), int(self.body.position.y)
            r = self.radius
            pulse = 0.5 + 0.5 * math.sin(self.frenzy_timer * 0.5)
            glow = pygame.Surface((r*5, r*5), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ABILITY["aura_color"], int(100 * pulse)), (r*2.5, r*2.5), r + 20)
            pygame.draw.circle(glow, (*ABILITY["aura_color"], 200), (r*2.5, r*2.5), r + 10, 3)
            screen.blit(glow, (x - r*2.5, y - r*2.5))
            
        # Intense glowing outline while phasing
        if self.phasing:
            x, y = int(self.body.position.x), int(self.body.position.y)
            r = self.radius
            glow = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*PHASE_BLUE, 100), (r*2, r*2), r + 10)
            pygame.draw.circle(glow, (255, 255, 255, 200), (r*2, r*2), r + 4, 2)
            screen.blit(glow, (x - r*2, y - r*2))
            
        super().draw(screen)