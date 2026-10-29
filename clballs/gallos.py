import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "GALLOS",
    "filename": "11.png",     # put your picture in the assets folder with this name
    "max_hp": 1500,
    "speed_mult": 1.0,        # multiplies the starting speed (speed stays constant)
    "radius": 30,
    "contact_damage": 5,      # damage when the two balls bump

    "max_super": 100,         # size of the super bar
    "super_per_hit": 5,      # super gained each time a wave hits
    "super_per_contact": 5,   # super gained when the balls bump
}

# Main attack: swings a wooden stick in front of her. The stick itself barely hurts, but the swing
# sends out 3 small cold waves in an arc that deal the real damage (and chill the enemy).
ABILITY = {
    "swing_cooldown": 90,     # frames between swings (90 = 1.5 seconds)

    "stick_length": 40,       # how far the stick reaches from her edge
    "stick_thickness": 14,    # hitbox thickness of the stick
    "stick_damage": 50,       # the stick itself barely hurts
    "stick_arc": 130,         # (degrees) how wide the stick sweeps, visual only
    "swing_frames": 14,       # frames the stick swing takes

    "waves": 3,               # how many blizzard waves are sent per swing
    "wave_damage": 100,        # damage of each wave
    "wave_radius": 55,        # how big the wave arc is (small, not the whole arena)
    "wave_speed": 6.0,        # pixels per frame the wave slides forward
    "wave_range": 260,        # how far from GALLOS a wave travels before fading
    "wave_arc": 80,           # (degrees) angular size of each wave arc
    "wave_spread": 28,        # (degrees) how much the waves fan out from each other
    "wave_thickness": 16,     # hitbox thickness of the wave arc
    "wave_frames": 26,        # how long a wave lives if it does not hit (frames)
    "chill_frames": 60,       # how long the enemy is chilled (slowed a bit) after a hit
    "chill_slow": 0.85,       # 0.85 = moves at 85% speed
    "color": (190, 230, 255), # ice blue
}

# Super: GALLOS flies in a big infinity (∞) shape across the arena, hurting the enemy on contact,
# and leaving a slippery ice trail behind her.
ULTIMATE = {
    "duration": 120,          # frames the infinity flight lasts (240 = 4 seconds)
    "step_speed": 6.5,        # pixels per frame along the path (bigger = faster circle)
    "size": 0.42,             # how big the ∞ is relative to the arena (0.42 = 42% of half-arena)
    "contact_damage": 120,    # damage each time the enemy touches her while she is flying
    "contact_cooldown": 60,   # frames before the SAME enemy can be hit again by her body

    "trail_every": 3,         # drop a new ice patch every N frames of flight
    "patch_life": 60,        # frames an ice patch lasts (240 = 4 seconds)
    "patch_radius": 26,       # how big each patch is
    "patch_slow": 0.45,       # 0.45 = the enemy moves at 45% speed on the ice
    "patch_tick_damage": 10,   # damage per tick
    "patch_tick_every": 20,   # frames between damage ticks while on the ice
    "trail_color": (170, 220, 255),
}
# ===========================================================

ICE = (190, 230, 255)
ICE_LIGHT = (235, 250, 255)
WOOD = (150, 100, 60)
WOOD_LIGHT = (200, 150, 100)
TRAIL = (170, 220, 255)

_avatar_cache = {}


def make_avatar(radius):
    """Ice-blue ball with a wooden stick and a chilly aura (used when there is no 11.png)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)

    # body gradient: deep blue to icy white
    for i in range(40):
        t = i / 39
        col = (int(30 + 90 * t), int(90 + 120 * t), int(150 + 100 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.85))))

    # icy sparkles
    rng = random.Random(11)
    for _ in range(20):
        a, d = rng.uniform(0, TAU), rng.uniform(0, c * 0.85)
        r = rng.choice((1, 2, 2, 3))
        pygame.draw.circle(big, ICE_LIGHT, (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), r)

    # eyes (calm, slanted)
    for sx in (-1, 1):
        eye = [(c + sx * c * 0.14, c - c * 0.04), (c + sx * c * 0.46, c - c * 0.18),
               (c + sx * c * 0.44, c + c * 0.08), (c + sx * c * 0.16, c + c * 0.12)]
        pygame.draw.polygon(big, WHITE, eye)
        pygame.draw.circle(big, (20, 30, 60), (int(c + sx * c * 0.30), int(c - c * 0.02)), int(c * 0.06))

    # wooden stick across the top-right
    pygame.draw.line(big, WOOD, (c + c * 0.30, c - c * 0.55), (c + c * 0.75, c - c * 0.90), 12)
    pygame.draw.line(big, WOOD_LIGHT, (c + c * 0.32, c - c * 0.58), (c + c * 0.72, c - c * 0.88), 4)

    # mask to circle
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


def _turn(cur, want, step):
    d = (want - cur + math.pi) % TAU - math.pi
    return cur + max(-step, min(step, d))


def _closest_on_segment(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return ax + abx * t, ay + aby * t


class BlizzardWave:
    """A small arc-shaped cold wave that slides outward from GALLOS. One per wave, 3 per swing."""

    def __init__(self, owner, target, origin, angle, dist):
        A = ABILITY
        self.owner = owner
        self.target = target
        self.ox, self.oy = origin
        self.angle = angle
        self.dist = dist
        self.radius = A["wave_radius"]
        self.arc = math.radians(A["wave_arc"])
        self.thickness = A["wave_thickness"]
        self.damage = A["wave_damage"]
        self.speed = A["wave_speed"]
        self.max_range = A["wave_range"]
        self.life = A["wave_frames"]
        self.hit = False
        self.active = True
        self.t = 0

    def _center(self):
        return (self.ox + math.cos(self.angle) * self.dist,
                self.oy + math.sin(self.angle) * self.dist)

    def _hits(self, px, py):
        """Is the point (px,py) inside the arc band?"""
        cx, cy = self._center()
        dx, dy = px - cx, py - cy
        d = math.hypot(dx, dy)
        if d < self.radius - self.thickness or d > self.radius + self.thickness:
            return False
        a = math.atan2(dy, dx)
        rel = (a - self.angle + math.pi) % TAU - math.pi
        return abs(rel) <= self.arc / 2

    def update(self, explosions):
        if not self.active:
            return
        self.t += 1
        self.dist += self.speed
        self.life -= 1
        if self.dist > self.max_range or self.life <= 0:
            self.active = False
            return
        t = self.target
        if not self.hit and t and t.hp > 0:
            tp = t.body.position
            if self._hits(tp.x, tp.y):
                t.hp -= self.damage
                self.hit = True
                self.owner.add_super(self.owner.super_per_hit)
                sounds.play("hit")
                # chill the enemy a bit
                t.apply_slow(ABILITY["chill_frames"], ABILITY["chill_slow"], 0, ABILITY["color"])
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.0, 4.0))
                          for _ in range(8)]
                explosions.append({"x": tp.x, "y": tp.y, "radius": 32, "timer": 12, "max": 12,
                                   "color": ABILITY["color"], "sparks": sparks})

    def draw(self, screen):
        if not self.active:
            return
        A = ABILITY
        cx, cy = self._center()
        fade = min(1.0, self.life / 10.0)
        # build the arc as a layered band
        steps = 16
        for layer, (mult, alpha) in enumerate(((1.0, 90), (0.6, 150), (0.25, 210))):
            pts = []
            for i in range(steps + 1):
                a = self.angle - self.arc / 2 + self.arc * i / steps
                r = self.radius + self.thickness * mult * 0.4
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
            for i in range(steps, -1, -1):
                a = self.angle - self.arc / 2 + self.arc * i / steps
                r = self.radius - self.thickness * mult * 0.4
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
            if len(pts) >= 3:
                surf = pygame.Surface((self.radius * 4 + 40, self.radius * 4 + 40), pygame.SRCALPHA)
                cx_local = surf.get_width() // 2
                cy_local = surf.get_height() // 2
                local_pts = [(p[0] - cx + cx_local, p[1] - cy + cy_local) for p in pts]
                pygame.draw.polygon(surf, (*A["color"], int(alpha * fade)), local_pts)
                screen.blit(surf, (int(cx - cx_local), int(cy - cy_local)))
        # bright inner highlight
        for i in range(steps + 1):
            a = self.angle - self.arc / 2 + self.arc * i / steps
            r = self.radius
            px = cx + math.cos(a) * r
            py = cy + math.sin(a) * r
            pygame.draw.circle(screen, ICE_LIGHT, (int(px), int(py)), 3)


class IcePatch:
    """A slippery ice patch left behind by GALLOS's super."""

    def __init__(self, x, y):
        U = ULTIMATE
        self.x, self.y = x, y
        self.timer = U["patch_life"]
        self.max = U["patch_life"]
        self.radius = U["patch_radius"]
        self.tick_cd = 0

    def update(self, target, explosions):
        if self.timer <= 0:
            return
        self.timer -= 1
        if self.tick_cd > 0:
            self.tick_cd -= 1
        if target is None or target.hp <= 0:
            return
        tp = target.body.position
        if math.hypot(self.x - tp.x, self.y - tp.y) <= self.radius + target.radius * 0.4:
            # slip: slow the enemy down
            if target.slow_timer < 3:
                target.apply_slow(2, ULTIMATE["patch_slow"], 0, ULTIMATE["trail_color"])
            if self.tick_cd <= 0:
                self.tick_cd = ULTIMATE["patch_tick_every"]
                target.hp -= ULTIMATE["patch_tick_damage"]
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(1.5, 3.0))
                          for _ in range(4)]
                explosions.append({"x": tp.x, "y": tp.y, "radius": 20, "timer": 8, "max": 8,
                                   "color": ULTIMATE["trail_color"], "sparks": sparks})

    def draw(self, screen):
        if self.timer <= 0:
            return
        fade = min(1.0, self.timer / 30.0)
        r = self.radius
        surf = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        c = r + 4
        pygame.draw.circle(surf, (*ULTIMATE["trail_color"], int(80 * fade)), (c, c), r)
        pygame.draw.circle(surf, (*ULTIMATE["trail_color"], int(160 * fade)), (c, c), r, 2)
        # crystalline shine
        for i in range(3):
            a = i * TAU / 3 + self.timer * 0.05
            px = c + math.cos(a) * r * 0.5
            py = c + math.sin(a) * r * 0.5
            pygame.draw.circle(surf, (255, 255, 255, int(180 * fade)), (int(px), int(py)), 2)
        screen.blit(surf, (int(self.x - c), int(self.y - c)))


class GallosSuper:
    """GALLOS flies in an ∞ (figure-eight) path across the arena, damaging the enemy on contact
    and dropping slippery ice patches behind her. Lives in the projectile list, so it keeps
    working even if GALLOS gets stunned."""

    def __init__(self, owner, target):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        self.t = 0
        self.active = True
        self.timer = U["duration"]
        self.contact_cd = 0
        self.trail_timer = 0

        # parametrize the ∞ around the arena center
        self.cx = (ARENA_LEFT + ARENA_RIGHT) / 2
        self.cy = (ARENA_TOP + ARENA_BOTTOM) / 2
        self.rx = (ARENA_RIGHT - ARENA_LEFT) * U["size"] / 2
        self.ry = (ARENA_BOTTOM - ARENA_TOP) * U["size"] / 2

        # start at t=0 (rightmost point of the ∞)
        self.phase = 0.0
        self.speed = U["step_speed"] / max(1.0, (self.rx + self.ry) / 2)

        self._original_speed = owner.speed_override
        self._target_original_speed = target.speed_override

    def _pos_at(self, phase):
        # Gerono / figure-eight lemniscate
        x = self.cx + self.rx * math.cos(phase) * 1.0
        y = self.cy + self.ry * math.sin(phase) * math.cos(phase) * 2.0
        # normalise so it fits inside the arena
        x = max(ARENA_LEFT + self.owner.radius + 6, min(ARENA_RIGHT - self.owner.radius - 6, x))
        y = max(ARENA_TOP + self.owner.radius + 6, min(ARENA_BOTTOM - self.owner.radius - 6, y))
        return x, y

    def _release(self):
        o, t = self.owner, self.target
        o.speed_override = self._original_speed
        t.speed_override = self._target_original_speed
        self.active = False

    def update(self, explosions):
        if not self.active:
            return
        U = ULTIMATE
        o, t = self.owner, self.target
        self.t += 1
        self.timer -= 1
        if self.contact_cd > 0:
            self.contact_cd -= 1
        if self.trail_timer > 0:
            self.trail_timer -= 1

        if o.hp <= 0 or t.hp <= 0 or self.timer <= 0:
            self._release()
            return

        # advance the ∞ path
        self.phase += self.speed
        nx, ny = self._pos_at(self.phase)
        # teleport her along the path at high speed (she is "flying", not walking)
        o.body.position = (nx, ny)
        o.body.velocity = (0, 0)
        o.speed_override = 0.0
        # keep her facing the path tangent for a nicer read
        o.move_dir = (math.cos(self.phase), math.cos(2 * self.phase))

        # drop an ice patch behind her
        if self.trail_timer <= 0:
            self.trail_timer = U["trail_every"]
            self._drop_patch(explosions)

        # contact damage with a per-enemy cooldown
        if self.contact_cd <= 0 and t.hp > 0:
            tp = t.body.position
            if math.hypot(nx - tp.x, ny - tp.y) <= o.radius + t.radius:
                t.hp -= U["contact_damage"]
                self.contact_cd = U["contact_cooldown"]
                o.add_super(o.super_per_hit)
                sounds.play("hit")
                sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(3.0, 5.0))
                          for _ in range(10)]
                explosions.append({"x": tp.x, "y": tp.y, "radius": 40, "timer": 12, "max": 12,
                                   "color": ICE, "sparks": sparks})

    def _drop_patch(self, explosions):
        """Adds a slippery ice patch at her current position (stored as its own object)."""
        x, y = self.owner.body.position.x, self.owner.body.position.y
        # clamp patches inside the arena so they're visible
        r = ULTIMATE["patch_radius"]
        x = max(ARENA_LEFT + r, min(ARENA_RIGHT - r, x))
        y = max(ARENA_TOP + r, min(ARENA_BOTTOM - r, y))
        self.owner.patches.append(IcePatch(x, y))

    def draw(self, screen):
        if not self.active:
            return
        # icy aura around her body
        o = self.owner
        x, y = int(o.body.position.x), int(o.body.position.y)
        r = o.radius + 8
        glow = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        gc = r * 2
        for k, a in ((r + 14, 40), (r + 6, 90), (r, 160)):
            pygame.draw.circle(glow, (*TRAIL, a), (gc, gc), k)
        screen.blit(glow, (x - gc, y - gc))

        # ∞ guide-line (faint) so the shape is readable
        U = ULTIMATE
        pts = []
        for i in range(72):
            ph = i * TAU / 72 + self.phase
            pts.append(self._pos_at(ph))
        if len(pts) >= 2:
            line = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            pygame.draw.lines(line, (*TRAIL, 70), True, pts, 2)
            screen.blit(line, (0, 0))


class Gallos(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):          # no 11.png -> built-in design
            self.surface = make_avatar(self.radius)
        self.swing_cd = 0
        self.swing_dir = random.choice((-1, 1))        # alternate direction each swing
        self.swing_t = 0
        self.swing_angle = 0.0
        self.swinging = False
        self.swing_swoosh = None
        self.patches = []                              # ice patches left by the super

    # ---------- the stick + blizzard waves ----------
    def _stick_points(self, angle):
        A = ABILITY
        cx, cy = self.body.position.x, self.body.position.y
        ca, sa = math.cos(angle), math.sin(angle)
        d1 = self.radius + 4
        d2 = d1 + A["stick_length"]
        return (cx + ca * d1, cy + sa * d1), (cx + ca * d2, cy + sa * d2)

    def _check_stick(self, angle, target, effects):
        A = ABILITY
        if target is None or target.hp <= 0:
            return
        p1, p2 = self._stick_points(angle)
        tx, ty = target.body.position.x, target.body.position.y
        qx, qy = _closest_on_segment(tx, ty, p1[0], p1[1], p2[0], p2[1])
        if math.hypot(tx - qx, ty - qy) <= target.radius + A["stick_thickness"] / 2:
            target.hp -= A["stick_damage"]
            self.add_super(self.super_per_hit)
            sounds.play("bump")

    def _swing(self, target, projectiles):
        A = ABILITY
        self.swinging = True
        self.swing_t = 0
        cx, cy = self.body.position.x, self.body.position.y
        base = math.atan2(target.body.position.y - cy, target.body.position.x - cx)
        self.swing_base = base
        self.swing_angle = base - self.swing_dir * math.radians(A["stick_arc"]) / 2
        self.swing_cd = A["swing_cooldown"]
        sounds.play("sword")

    def _update_swing(self, target, projectiles, effects):
        A = ABILITY
        self.swing_t += 1
        p = min(1.0, self.swing_t / max(1, A["swing_frames"]))
        ease = p * p * (3 - 2 * p)
        arc = math.radians(A["stick_arc"])
        new_a = self.swing_base - self.swing_dir * arc / 2 + self.swing_dir * arc * ease
        self._check_stick(new_a, target, effects)
        self.swing_angle = new_a
        self.swing_swoosh = [self.swing_base - self.swing_dir * arc / 2, new_a, 120]
        if p >= 1.0:
            self.swinging = False
            self.swing_dir = -self.swing_dir
            # fire the 3 blizzard waves at the end of the swing
            self._fire_waves(target, projectiles)

    def _fire_waves(self, target, projectiles):
        A = ABILITY
        cx, cy = self.body.position.x, self.body.position.y
        base = math.atan2(target.body.position.y - cy, target.body.position.x - cx)
        n = max(1, A["waves"])
        for i in range(n):
            off = math.radians((i - (n - 1) / 2) * A["wave_spread"])
            projectiles.append(BlizzardWave(self, target, (cx, cy), base + off, self.radius + 10))

    # ---------- super ----------
    def _ultimate(self, target, projectiles):
        projectiles.append(GallosSuper(self, target))
        sounds.play("super")

    # ---------- update ----------
    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        A = ABILITY
        alive = target is not None and target.hp > 0

        # ice patches only tick while GALLOS is alive
        for p in self.patches:
            p.update(target, scratch_effects)
        self.patches = [p for p in self.patches if p.timer > 0]

        if self.swing_cd > 0:
            self.swing_cd -= 1
        if self.swing_swoosh and not self.swinging:
            self.swing_swoosh[2] -= 12
            if self.swing_swoosh[2] <= 0:
                self.swing_swoosh = None

        super_running = any(isinstance(p, GallosSuper) and p.active for p in projectiles)

        if self.swinging:
            self._update_swing(target if alive else None, projectiles, scratch_effects)
        elif alive and self.swing_cd <= 0 and not super_running:
            self._swing(target, projectiles)

        if alive and self.super_charge >= self.max_super and not super_running:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)

    # ---------- drawing ----------
    def _draw_stick(self, screen):
        A = ABILITY
        angle = self.swing_angle if self.swinging else self.swing_angle
        p1, p2 = self._stick_points(angle)

        # swoosh trail
        if self.swing_swoosh and self.swing_swoosh[2] > 0:
            a0, a1, alpha = self.swing_swoosh
            span = a1 - a0
            if abs(span) > 0.02:
                cx, cy = self.body.position.x, self.body.position.y
                reach = self.radius + A["stick_length"]
                inner = reach * 0.4
                steps = max(4, int(abs(span) / 0.1))
                outer_pts = [(cx + math.cos(a0 + span * i / steps) * reach,
                              cy + math.sin(a0 + span * i / steps) * reach) for i in range(steps + 1)]
                inner_pts = [(cx + math.cos(a0 + span * i / steps) * inner,
                              cy + math.sin(a0 + span * i / steps) * inner) for i in range(steps, -1, -1)]
                size = int(reach * 2) + 4
                layer = pygame.Surface((size, size), pygame.SRCALPHA)
                local = [(p[0] - cx + size // 2, p[1] - cy + size // 2) for p in outer_pts + inner_pts]
                pygame.draw.polygon(layer, (*ICE, max(0, min(255, int(alpha)))), local)
                screen.blit(layer, (int(cx - size // 2), int(cy - size // 2)))

        # wooden stick (with icy crystals on the tip)
        pygame.draw.line(screen, (60, 40, 20), p1, p2, A["stick_thickness"] + 4)
        pygame.draw.line(screen, WOOD, p1, p2, A["stick_thickness"])
        pygame.draw.line(screen, WOOD_LIGHT, p1, p2, 3)
        # icy tip
        tip_r = 10
        pygame.draw.circle(screen, ICE, (int(p2[0]), int(p2[1])), tip_r)
        pygame.draw.circle(screen, ICE_LIGHT, (int(p2[0]), int(p2[1])), tip_r - 2)
        for k in range(4):
            a = k * TAU / 4 + self.swing_t * 0.2
            px = p2[0] + math.cos(a) * (tip_r + 4)
            py = p2[1] + math.sin(a) * (tip_r + 4)
            pygame.draw.circle(screen, ICE_LIGHT, (int(px), int(py)), 2)

    def draw(self, screen):
        if self.hp <= 0:
            return
        super().draw(screen)
        self._draw_stick(screen)