import math
import random
import pygame
import pymunk
from config import (
    ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM,
    load_avatar, load_sprite
)

STATUS_TICK_FRAMES = 12

def draw_lightning(screen, p1, p2, color, width=3, jitter=8, segments=6):
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    pts = [(x1, y1)]
    for i in range(1, segments):
        t = i / segments
        off = random.uniform(-jitter, jitter)
        pts.append((x1 + dx * t + nx * off, y1 + dy * t + ny * off))
    pts.append((x2, y2))
    pygame.draw.lines(screen, color, False, pts, width)


class Projectile:
    def __init__(self, owner, target, p_type, sprite_filename, pos, vel, damage, radius,
                 is_homing=False, timer=None, homing_speed=6.0, explosion_radius=60,
                 charges_super=True, trail_length=0, trail_color=(255, 255, 255),
                 explosion_color=(255, 140, 40), explosion_frames=22):
        self.owner = owner
        self.target = target
        self.p_type = p_type
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.damage = damage
        self.radius = radius
        self.is_homing = is_homing
        self.timer = timer
        self.homing_speed = homing_speed
        self.explosion_radius = explosion_radius
        self.charges_super = charges_super
        self.trail_length = trail_length
        self.trail_color = trail_color
        self.trail = []
        self.explosion_color = explosion_color
        self.explosion_frames = explosion_frames
        self.active = True
        self.sprite = load_sprite(sprite_filename, radius * 2, radius * 2)

    def update(self, explosions):
        if not self.active:
            return

        if self.timer is not None:
            self.timer -= 1
            if self.timer <= 0:
                self.explode(explosions)
                return

        if self.is_homing and self.target and self.target.hp > 0:
            target_pos = self.target.body.position
            dx = target_pos.x - self.x
            dy = target_pos.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.vx = (dx / dist) * self.homing_speed
                self.vy = (dy / dist) * self.homing_speed

        if self.trail_length > 0:
            self.trail.append((self.x, self.y))
            if len(self.trail) > self.trail_length:
                self.trail.pop(0)

        self.x += self.vx
        self.y += self.vy

        hit_wall = (
            self.x - self.radius <= ARENA_LEFT or self.x + self.radius >= ARENA_RIGHT or
            self.y - self.radius <= ARENA_TOP or self.y + self.radius >= ARENA_BOTTOM
        )
        if hit_wall:
            if self.timer is not None:
                self.explode(explosions)
            else:
                self.active = False
            return

        if self.target and self.target.hp > 0 and self.p_type != "yarn":
            t_pos = self.target.body.position
            dist = math.hypot(self.x - t_pos.x, self.y - t_pos.y)
            if dist <= self.radius + self.target.radius:
                self.target.hp -= self.damage
                if self.charges_super:
                    self.owner.add_super(self.owner.super_per_hit)
                self.active = False

    def explode(self, explosions):
        self.active = False
        sparks = [(random.uniform(0, math.pi * 2), random.uniform(0.5, 1.0), random.uniform(2.5, 5.0))
                  for _ in range(14)]
        explosions.append({
            "x": self.x, "y": self.y, "radius": self.explosion_radius,
            "timer": self.explosion_frames, "max": self.explosion_frames,
            "color": self.explosion_color, "sparks": sparks,
        })

        if self.target and self.target.hp > 0:
            t_pos = self.target.body.position
            dist = math.hypot(self.x - t_pos.x, self.y - t_pos.y)
            if dist <= self.explosion_radius + self.target.radius:
                self.target.hp -= self.damage
                if self.charges_super:
                    self.owner.add_super(self.owner.super_per_hit)

    def draw(self, screen):
        if not self.active:
            return
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            f = (i + 1) / (n + 1)
            r = max(1, int(self.radius * f * 0.9))
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*self.trail_color, int(150 * f)), (r, r), r)
            screen.blit(surf, (int(tx - r), int(ty - r)))

        if self.sprite:
            screen.blit(self.sprite, (int(self.x - self.radius), int(self.y - self.radius)))
        else:
            color = (60, 220, 255) if self.p_type == "star" else (220, 60, 180)
            pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)


class BaseBrawler:
    def __init__(self, space, pos, velocity, stats):
        self._hp = stats["max_hp"]
        self.name = stats["name"]
        self.filename = stats["filename"]
        self.max_hp = stats["max_hp"]
        self.radius = stats["radius"]
        self.contact_damage = stats["contact_damage"]
        self.cooldown = 0

        self.super_charge = 0
        self.max_super = stats.get("max_super", 100)
        self.super_per_hit = stats.get("super_per_hit", 15)
        self.super_per_contact = stats.get("super_per_contact", 20)
        self.attack_cooldown = 0

        self.flash_color = (255, 255, 255)
        self.flash_timer = 0
        self.flash_total = 1
        self.super_flash = 0
        self.popups = []

        self.slow_timer = 0
        self.slow_factor = 1.0
        self.slow_dps = 0
        self.slow_color = (130, 230, 255)
        self.stun_color = (255, 240, 110)
        self.knock_timer = 0
        self.knock_total = 1
        self.knock_speed = 0.0
        self.stun_timer = 0
        self.stun_dps = 0
        self.dot_accum = 0
        self.cosmic_timer = 0
        self.cosmic_slow = 0.3
        self._super_frac = 0.0
        
        # Weakness Curse (Hyper's super)
        self.weakness_timer = 0
        self.weakness_dmg = 1

        speed_mult = stats["speed_mult"]
        self.base_speed = math.hypot(velocity[0], velocity[1]) * speed_mult
        start_len = math.hypot(velocity[0], velocity[1]) or 1.0
        self.move_dir = (velocity[0] / start_len, velocity[1] / start_len)
        self.speed_override = None

        mass = 1.0
        self.base_mass = mass
        inertia = pymunk.moment_for_circle(mass, 0, self.radius)
        self.body = pymunk.Body(mass, inertia)
        self.body.position = pos
        self.body.velocity = (velocity[0] * speed_mult, velocity[1] * speed_mult)

        self.shape = pymunk.Circle(self.body, self.radius)
        self.shape.elasticity = 1.0
        self.shape.friction = 0.0

        space.add(self.body, self.shape)
        self.surface = load_avatar(self.filename, self.radius)

    @property
    def hp(self):
        return self._hp

    @hp.setter
    def hp(self, value):
        # If cursed, EVERYTHING only deals 1 damage.
        if getattr(self, "weakness_timer", 0) > 0 and value < self._hp:
            self._hp -= self.weakness_dmg
        else:
            self._hp = value

    def charge_rate(self):
        return (1.0 - self.cosmic_slow) if self.cosmic_timer > 0 else 1.0

    def add_super(self, amount):
        total = amount * self.charge_rate() + self._super_frac
        whole = int(total)
        self._super_frac = total - whole
        self.super_charge = min(self.max_super, self.super_charge + whole)

    def apply_cosmic(self, frames, slow=0.3):
        self.cosmic_timer = max(self.cosmic_timer, frames)
        self.cosmic_slow = slow

    def maintain_speed(self):
        if self.stun_timer > 0:
            self.body.velocity = (0, 0)
            return
        vx, vy = self.body.velocity
        length = math.hypot(vx, vy)
        if length > 1e-6:
            self.move_dir = (vx / length, vy / length)
        speed = self.speed_override if self.speed_override is not None else self.base_speed
        if self.slow_timer > 0:
            speed *= self.slow_factor
        if self.knock_timer > 0 and self.speed_override is None:
            f = self.knock_timer / self.knock_total
            speed += (self.knock_speed - speed) * f
        dx, dy = self.move_dir
        self.body.velocity = (dx * speed, dy * speed)

    def flash(self, color, frames):
        self.flash_color = color
        self.flash_timer = frames
        self.flash_total = max(1, frames)

    def trigger_super(self):
        self.super_flash = 60
        self.popups.append(("SUPER!", (255, 215, 0)))

    def can_act(self):
        return self.stun_timer <= 0

    def apply_slow(self, frames, factor, dps, color=None):
        self.slow_color = color or (130, 230, 255)
        self.slow_timer = max(self.slow_timer, frames)
        self.slow_factor = factor
        self.slow_dps = dps

    def apply_knockback(self, dx, dy, speed, frames):
        self.knock_speed = speed
        self.knock_timer = self.knock_total = max(1, frames)
        self.move_dir = (dx, dy)
        self.body.velocity = (dx * speed, dy * speed)

    def apply_stun(self, frames, dps, color=None):
        self.stun_color = color or (255, 240, 110)
        self.stun_timer = max(self.stun_timer, frames)
        self.stun_dps = dps
        self.body.mass = 1e6
        self.body.velocity = (0, 0)

    def tick_effects(self):
        if self.flash_timer > 0:
            self.flash_timer -= 1
        if self.super_flash > 0:
            self.super_flash -= 1
        if self.knock_timer > 0:
            self.knock_timer -= 1
        if self.cosmic_timer > 0:
            self.cosmic_timer -= 1
        if self.weakness_timer > 0:
            self.weakness_timer -= 1

        dps = 0
        if self.slow_timer > 0:
            self.slow_timer -= 1
            dps = max(dps, self.slow_dps)
        if self.stun_timer > 0:
            self.stun_timer -= 1
            dps = max(dps, self.stun_dps)
            if self.stun_timer == 0:
                self.body.mass = self.base_mass
        if dps > 0 and self.hp > 0:
            self.dot_accum += 1
            if self.dot_accum >= STATUS_TICK_FRAMES:
                self.dot_accum = 0
                self.hp -= round(dps * STATUS_TICK_FRAMES / 60)
        else:
            self.dot_accum = 0

    def update_abilities(self, target, projectiles, scratch_effects):
        pass

    def draw(self, screen):
        if self.hp <= 0:
            return
        x, y = int(self.body.position.x), int(self.body.position.y)
        if self.stun_timer > 0:
            x += random.randint(-3, 3)
            y += random.randint(-3, 3)
        r = self.radius
        surf = self.surface
        outline = (255, 255, 255)

        if self.flash_timer > 0:
            fade = self.flash_timer / self.flash_total
            blink_on = (self.flash_timer // 4) % 2 == 0
            k = (0.9 if blink_on else 0.3) * (0.4 + 0.6 * fade)
            glow = pygame.Surface((r * 2 + 40, r * 2 + 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*self.flash_color, int(120 * k)), (r + 20, r + 20), r + 16)
            screen.blit(glow, (x - r - 20, y - r - 20))
            surf = self.surface.copy()
            tint = tuple(int(v * k) for v in self.flash_color)
            surf.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
            outline = self.flash_color

        screen.blit(surf, (x - r, y - r))
        pygame.draw.circle(screen, outline, (x, y), r, 3)

        if self.flash_timer > 0:
            ring_r = r + 4 + int(14 * (1 - self.flash_timer / self.flash_total))
            pygame.draw.circle(screen, self.flash_color, (x, y), ring_r, 2)

        if self.slow_timer > 0:
            rng = random.Random(self.slow_timer // 9)
            pygame.draw.circle(screen, self.slow_color, (x, y), r + 3, 1)
            for _ in range(3):
                ang = rng.uniform(0, math.pi * 2)
                a0, b0 = r + 2, r + rng.uniform(7, 14)
                draw_lightning(screen, (x + math.cos(ang) * a0, y + math.sin(ang) * a0),
                               (x + math.cos(ang) * b0, y + math.sin(ang) * b0), self.slow_color, 2, 2, 2)

        if self.stun_timer > 0:
            color = self.stun_color
            pygame.draw.circle(screen, color, (x, y), r + 3, 2)
            for _ in range(6):
                ang = random.uniform(0, math.pi * 2)
                a, b0 = r + 2, r + random.uniform(10, 20)
                draw_lightning(screen, (x + math.cos(ang) * a, y + math.sin(ang) * a),
                               (x + math.cos(ang) * b0, y + math.sin(ang) * b0), color, 2, 3, 3)

        if self.cosmic_timer > 0:
            tt = pygame.time.get_ticks() / 1000.0
            pygame.draw.circle(screen, (170, 100, 255), (x, y), r + 5, 2)
            for i in range(4):
                a = tt * 2.2 + i * math.pi / 2
                pygame.draw.circle(screen, (255, 255, 255), (int(x + math.cos(a) * (r + 5)), int(y + math.sin(a) * (r + 5))), 2)

        # Weakness Curse (Hyper's super)
        if self.weakness_timer > 0:
            tt = pygame.time.get_ticks() / 1000.0
            pulse = 0.5 + 0.5 * math.sin(tt * 15)
            r_glow = r + 4 + int(4 * pulse)
            pygame.draw.circle(screen, (180, 40, 255), (x, y), r_glow, 3)
            
            for _ in range(4):
                ang = random.uniform(0, math.pi * 2)
                a0, b0 = r + 2, r + random.uniform(10, 20)
                draw_lightning(screen, (x + math.cos(ang) * a0, y + math.sin(ang) * a0),
                               (x + math.cos(ang) * b0, y + math.sin(ang) * b0), (200, 80, 255), 2, 3, 3)