import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "TERMI",
    "filename": "10.png",     # put your picture in the assets folder with this name
    "max_hp": 2000,
    "speed_mult": 1.0,        # multiplies the starting speed (speed stays constant)
    "radius": 30,
    "contact_damage": 5,      # damage when the two balls bump

    "max_super": 100,         # size of the super bar
    "super_per_hit": 5,       # super gained each time a triangle hits
    "super_per_contact": 5,   # super gained when the balls bump
}

# Main attack: throws one glowing yellow triangle every second (60 frames).
# The triangle bounces off the arena walls and lives for 3 seconds, so it can hit more than once.
ABILITY = {
    "throw_interval": 30,     # frames between throws (60 = 1 second)
    "damage": 15,             # damage of one triangle hit
    "speed": 8.0,             # pixels per frame
    "radius": 10,             # hitbox radius of the triangle
    "spin": 0.15,             # how fast the triangle spins (radians per frame)
    "color": (255, 225, 70),  # yellow glow
    "trail_length": 8,
    "lifetime": 180,          # frames the triangle lives (180 = 3 seconds) before it fizzles out
    "hit_cooldown": 30,       # frames before the SAME triangle can hit the same enemy again
    "max_hits": 2,            # a triangle can hit at most this many times before it disappears
}

# Super: TERMI DASHES at the enemy (with a streak trail), stops the battle, does a HANDSHAKE
# (arms reaching out and gripping), steals 50 hp from the enemy, then explodes them for 250.
ULTIMATE = {
    "dash_speed": 1999999.0,       # pixels per frame during the dash (very fast)
    "dash_trail_frames": 12,  # length of the motion trail left behind the dash
    "stop_frames": 90,        # frames the handshake is held (90 = 1.5 seconds)
    "steal_hp": 150,           # hp taken from the enemy and given to TERMI
    "explosion_damage": 400,  # damage of the final explosion
    "explosion_radius": 90,   # radius of the explosion
    "explosion_frames": 30,   # how long the explosion animation lasts
    "handshake_reach": 70,    # how close the two balls must be for the hands to meet
    "after_frames": 20,       # frames after the explosion before TERMI can act again
}
# ===========================================================

YELLOW = (255, 225, 70)
YELLOW_LIGHT = (255, 250, 190)
ORANGE = (255, 160, 50)
RED = (255, 70, 70)
WHITE = (255, 255, 255)
SKIN = (255, 210, 160)
DASH_COLOR = (255, 225, 70)

_avatar_cache = {}


def make_avatar(radius):
    """Cyan robot ball with antenna and glowing eyes (used when there is no 10.png)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)

    # body gradient: dark cyan to bright cyan
    for i in range(40):
        t = i / 39
        col = (int(20 + 60 * t), int(80 + 140 * t), int(100 + 130 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.85))))

    # antenna
    pygame.draw.line(big, (100, 120, 140), (c, c - c * 0.7), (c, c - c * 0.98), 6)
    pygame.draw.circle(big, (80, 220, 255), (c, c - int(c * 0.98)), 8)
    pygame.draw.circle(big, WHITE, (c, c - int(c * 0.98)), 4)

    # eyes: two glowing cyan ovals
    for sx in (-1, 1):
        ex = c + sx * c * 0.28
        ey = c - c * 0.05
        pygame.draw.ellipse(big, (15, 25, 40), pygame.Rect(ex - c * 0.18, ey - c * 0.12, c * 0.36, c * 0.24))
        pygame.draw.ellipse(big, (80, 220, 255), pygame.Rect(ex - c * 0.14, ey - c * 0.08, c * 0.28, c * 0.16))
        pygame.draw.ellipse(big, WHITE, pygame.Rect(ex - c * 0.06, ey - c * 0.04, c * 0.12, c * 0.08))

    # mouth: a small line
    pygame.draw.line(big, (15, 30, 45), (c - c * 0.2, c + c * 0.3), (c + c * 0.2, c + c * 0.3), 4)

    # mask to circle
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


def _draw_hand(screen, x, y, angle, scale=1.0, color=SKIN):
    """A simple cartoon hand: a palm and fingers pointing along `angle`."""
    ca, sa = math.cos(angle), math.sin(angle)
    nx, ny = -sa, ca

    def P(f, s):
        return (x + (ca * f + nx * s) * scale, y + (sa * f + ny * s) * scale)

    # palm
    palm = [P(-6, -9), P(6, -9), P(8, 0), P(6, 9), P(-6, 9), P(-8, 0)]
    pygame.draw.polygon(screen, color, palm)
    pygame.draw.polygon(screen, (80, 50, 30), palm, 2)
    # fingers
    for off in (-6, -2, 2, 6):
        f0 = P(6, off)
        f1 = P(20, off * 1.1)
        pygame.draw.line(screen, color, f0, f1, max(2, int(4 * scale)))
        pygame.draw.circle(screen, color, (int(f1[0]), int(f1[1])), max(1, int(2.5 * scale)))
    # thumb
    pygame.draw.line(screen, color, P(-2, -8), P(2, -18), max(2, int(4 * scale)))
    pygame.draw.circle(screen, color, (int(P(2, -18)[0]), int(P(2, -18)[1])), max(1, int(2.5 * scale)))


class GlowTriangle:
    """A glowing spinning yellow triangle projectile that bounces off the walls for a few seconds."""

    def __init__(self, owner, target, pos, angle):
        A = ABILITY
        self.owner = owner
        self.target = target
        self.x, self.y = pos
        self.vx = math.cos(angle) * A["speed"]
        self.vy = math.sin(angle) * A["speed"]
        self.radius = A["radius"]
        self.rot = random.uniform(0, TAU)
        self.trail = []
        self.active = True
        self.t = 0
        self.life = A["lifetime"]
        self.hit_cd = 0          # frames until this triangle can hit the enemy again
        self.hits = 0            # how many times this triangle has already hit
        self.bounce_flash = 0    # frames of the small spark after a wall bounce

    def _wall_bounce(self, explosions):
        A = ABILITY
        hit = False
        if self.x - self.radius <= ARENA_LEFT:
            self.x = ARENA_LEFT + self.radius
            self.vx = abs(self.vx)
            hit = True
        elif self.x + self.radius >= ARENA_RIGHT:
            self.x = ARENA_RIGHT - self.radius
            self.vx = -abs(self.vx)
            hit = True
        if self.y - self.radius <= ARENA_TOP:
            self.y = ARENA_TOP + self.radius
            self.vy = abs(self.vy)
            hit = True
        elif self.y + self.radius >= ARENA_BOTTOM:
            self.y = ARENA_BOTTOM - self.radius
            self.vy = -abs(self.vy)
            hit = True
        if hit:
            self.bounce_flash = 8
            sounds.play("bump")

    def _hit_enemy(self, explosions):
        A = ABILITY
        t = self.target
        t.hp -= A["damage"]
        self.owner.add_super(self.owner.super_per_hit)
        self.hits += 1
        self.hit_cd = A["hit_cooldown"]
        sounds.play("hit")
        sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.0, 4.0))
                  for _ in range(8)]
        explosions.append({"x": self.x, "y": self.y, "radius": 30, "timer": 12, "max": 12,
                           "color": A["color"], "sparks": sparks})
        if self.hits >= A["max_hits"]:
            self.active = False

    def update(self, explosions):
        if not self.active:
            return
        A = ABILITY
        self.t += 1
        self.rot += A["spin"]
        self.life -= 1
        if self.hit_cd > 0:
            self.hit_cd -= 1
        if self.bounce_flash > 0:
            self.bounce_flash -= 1

        if self.life <= 0:
            self.active = False
            return

        self.trail.append((self.x, self.y))
        if len(self.trail) > A["trail_length"]:
            self.trail.pop(0)

        self.x += self.vx
        self.y += self.vy

        # bounce off the walls instead of dying
        self._wall_bounce(explosions)

        # hit the enemy (with a per-triangle cooldown so it can hit several times)
        t = self.target
        if t and t.hp > 0 and self.hit_cd <= 0:
            tp = t.body.position
            if math.hypot(self.x - tp.x, self.y - tp.y) <= self.radius + t.radius:
                self._hit_enemy(explosions)

    def draw(self, screen):
        if not self.active:
            return
        A = ABILITY
        # trail
        for i, (tx, ty) in enumerate(self.trail):
            f = (i + 1) / (len(self.trail) + 1)
            r = max(1, int(self.radius * f * 0.6))
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*A["color"], int(100 * f)), (r, r), r)
            screen.blit(surf, (int(tx - r), int(ty - r)))

        # glow (a touch brighter right after a wall bounce)
        glow = pygame.Surface((self.radius * 6, self.radius * 6), pygame.SRCALPHA)
        gc = self.radius * 3
        boost = 1.5 if self.bounce_flash > 0 else 1.0
        for r, a in ((self.radius * 2.5, 30), (self.radius * 1.8, 60), (self.radius * 1.2, 100)):
            pygame.draw.circle(glow, (*A["color"], int(min(255, a * boost))), (gc, gc), int(r))
        screen.blit(glow, (int(self.x - gc), int(self.y - gc)))

        # spinning triangle
        pts = []
        for i in range(3):
            a = self.rot + i * TAU / 3 - math.pi / 2
            pts.append((self.x + math.cos(a) * self.radius * 1.4,
                        self.y + math.sin(a) * self.radius * 1.4))
        pygame.draw.polygon(screen, A["color"], pts)
        pygame.draw.polygon(screen, WHITE, pts, 2)

        # inner bright core
        pts2 = [(self.x + (px - self.x) * 0.5, self.y + (py - self.y) * 0.5) for px, py in pts]
        pygame.draw.polygon(screen, YELLOW_LIGHT, pts2)

        # little warning blink near the end of its life
        if self.life < 30 and (self.life // 4) % 2 == 0:
            pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), self.radius + 3, 1)


class TermiSuper:
    """The super: TERMI DASHES at the enemy (with a streak trail), freezes the battle,
    does a HANDSHAKE, steals HP, explodes. Lives in the projectile list, so it keeps
    updating even if TERMI gets stunned."""

    def __init__(self, owner, target):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        self.phase = "dash"      # dash -> handshake -> steal -> explode
        self.t = 0
        self.pt = 0               # frames in the current phase
        self.active = True
        self._original_speed = owner.speed_override
        self._original_target_speed = target.speed_override
        self.trail = []           # list of past (x, y, radius) for the dash streak

    def _enter(self, phase):
        self.phase = phase
        self.pt = 0

    def _release(self):
        o, t = self.owner, self.target
        o.speed_override = self._original_speed
        t.speed_override = self._original_target_speed
        if t.stun_timer > 0:
            t.stun_timer = 1          # base class restores the mass when it hits 0
        self.active = False

    def update(self, explosions):
        if not self.active:
            return
        U = ULTIMATE
        o, t = self.owner, self.target
        self.t += 1
        self.pt += 1

        if o.hp <= 0 or t.hp <= 0:
            self._release()
            return

        if self.phase == "dash":
            # very fast, straight dash toward the enemy - not a walk
            o.speed_override = U["dash_speed"]
            dx = t.body.position.x - o.body.position.x
            dy = t.body.position.y - o.body.position.y
            d = math.hypot(dx, dy) or 1.0
            o.move_dir = (dx / d, dy / d)
            o.body.velocity = (dx / d * U["dash_speed"], dy / d * U["dash_speed"])

            # record the trail (oldest point drops off after a few frames)
            self.trail.append((o.body.position.x, o.body.position.y, self.t))
            if len(self.trail) > U["dash_trail_frames"]:
                self.trail.pop(0)

            if d <= U["handshake_reach"]:
                self._enter("handshake")
                o.speed_override = 0.0
                o.body.velocity = (0, 0)
                t.speed_override = 0.0
                t.body.velocity = (0, 0)
                t.apply_stun(U["stop_frames"], 0, YELLOW)
                sounds.play("star")
                o.popups.append(("HANDSHAKE!", YELLOW))

        elif self.phase == "handshake":
            o.body.velocity = (0, 0)
            t.body.velocity = (0, 0)
            if self.pt >= U["stop_frames"]:
                self._enter("steal")

        elif self.phase == "steal":
            stolen = min(U["steal_hp"], t.hp)
            t.hp -= stolen
            o.hp = min(o.max_hp, o.hp + stolen)
            o.popups.append((f"+{int(stolen)}", (90, 255, 140)))
            t.popups.append((f"-{int(stolen)}", RED))
            sounds.play("hit")
            self._enter("explode")

        elif self.phase == "explode":
            if self.pt == 1:
                t.hp -= U["explosion_damage"]
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(3.0, 6.0))
                          for _ in range(18)]
                explosions.append({"x": t.body.position.x, "y": t.body.position.y,
                                   "radius": U["explosion_radius"], "timer": U["explosion_frames"],
                                   "max": U["explosion_frames"], "color": ORANGE, "sparks": sparks})
                sounds.play("boom")
                t.flash(ORANGE, 30)
            if self.pt >= U["after_frames"]:
                self._release()

    def draw(self, screen):
        if not self.active:
            return
        o, t = self.owner, self.target

        if self.phase == "dash" and self.trail:
            # motion streak: shrinking, fading ghosts along the path TERMI just flew
            n = len(self.trail)
            for i, (tx, ty, _) in enumerate(self.trail):
                f = (i + 1) / (n + 1)
                r = max(2, int(o.radius * f))
                ghost = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(ghost, (*DASH_COLOR, int(180 * f)), (r, r), r)
                pygame.draw.circle(ghost, (255, 255, 255, int(120 * f)), (r, r), r, 2)
                screen.blit(ghost, (int(tx - r), int(ty - r)))
            # extra speed lines around TERMI
            if n >= 2:
                x0, y0, _ = self.trail[0]
                x1, y1 = o.body.position.x, o.body.position.y
                dx, dy = x1 - x0, y1 - y0
                d = math.hypot(dx, dy) or 1.0
                ux, uy = dx / d, dy / d
                nx, ny = -uy, ux
                for off in (-12, 0, 12):
                    ln = 26 + random.uniform(-6, 6)
                    px = x1 + nx * off + ux * 8
                    py = y1 + ny * off + uy * 8
                    pygame.draw.line(screen, DASH_COLOR,
                                     (px - ux * ln, py - uy * ln),
                                     (px + ux * 4, py + uy * 4), 3)

        elif self.phase == "handshake":
            ox, oy = o.body.position.x, o.body.position.y
            tx, ty = t.body.position.x, t.body.position.y
            mx, my = (ox + tx) / 2, (oy + ty) / 2
            base = math.atan2(ty - oy, tx - ox)

            # TERMI's arm reaches from his ball toward the midpoint
            arm_len = o.radius + 22
            hand_x = ox + math.cos(base) * arm_len
            hand_y = oy + math.sin(base) * arm_len

            # enemy's arm reaches from its ball toward the midpoint
            back = base + math.pi
            other_len = t.radius + 22
            other_x = tx + math.cos(back) * other_len
            other_y = ty + math.sin(back) * other_len

            # arms
            pygame.draw.line(screen, (90, 160, 190), (ox, oy), (hand_x, hand_y), 10)
            pygame.draw.line(screen, (190, 90, 110), (tx, ty), (other_x, other_y), 10)

            # the two hands gripping each other at the midpoint
            _draw_hand(screen, hand_x, hand_y, base, scale=1.2, color=SKIN)
            _draw_hand(screen, other_x, other_y, back, scale=1.2, color=SKIN)

            # spark burst at the meeting point
            pulse = 0.5 + 0.5 * math.sin(self.t * 0.35)
            for i in range(6):
                a = self.t * 0.25 + i * TAU / 6
                ln = 18 + 10 * pulse
                pygame.draw.line(screen, YELLOW, (mx, my),
                                 (mx + math.cos(a) * ln, my + math.sin(a) * ln), 2)
            pygame.draw.circle(screen, WHITE, (int(mx), int(my)), int(7 + 4 * pulse))
            pygame.draw.circle(screen, YELLOW, (int(mx), int(my)), int(12 + 6 * pulse), 3)

            # "HANDSHAKE!" label
            font = pygame.font.SysFont("Impact", 30)
            txt = font.render("HANDSHAKE!", True, YELLOW)
            sh = font.render("HANDSHAKE!", True, (0, 0, 0))
            r = txt.get_rect(center=(int(mx), int(my) - 50))
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                screen.blit(sh, r.move(dx, dy))
            screen.blit(txt, r)

        elif self.phase == "steal":
            tx, ty = t.body.position.x, t.body.position.y
            for i in range(5):
                a = self.t * 0.5 + i * TAU / 5
                px = tx + math.cos(a) * 30
                py = ty + math.sin(a) * 30
                pygame.draw.line(screen, ORANGE, (tx, ty), (px, py), 3)
                pygame.draw.circle(screen, WHITE, (int(px), int(py)), 4)


class Termi(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):          # no 10.png -> built-in design
            self.surface = make_avatar(self.radius)
        self.throw_timer = 0
        self.super_active = False

    def _throw_triangle(self, target, projectiles):
        A = ABILITY
        if target is None or target.hp <= 0:
            return
        x, y = self.body.position.x, self.body.position.y
        angle = math.atan2(target.body.position.y - y, target.body.position.x - x)
        projectiles.append(GlowTriangle(self, target, (x, y), angle))
        sounds.play("star")

    def _ultimate(self, target, projectiles):
        if target is None or target.hp <= 0:
            return
        self.super_active = True
        projectiles.append(TermiSuper(self, target))
        sounds.play("super")
        sounds.play("dash")

    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        A = ABILITY
        alive = target is not None and target.hp > 0

        super_running = any(isinstance(p, TermiSuper) and p.active for p in projectiles)
        self.super_active = super_running

        if self.throw_timer > 0:
            self.throw_timer -= 1

        # throw triangles (but not while the super is active)
        if alive and self.throw_timer <= 0 and not super_running:
            self._throw_triangle(target, projectiles)
            self.throw_timer = A["throw_interval"]

        # super
        if alive and self.super_charge >= self.max_super and not super_running:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)