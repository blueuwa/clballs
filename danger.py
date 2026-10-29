import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset, load_sprite

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "DANGER",
    "filename": "8.png",      # put your picture in the assets folder with this name
    "max_hp": 2200,
    "speed_mult": 1.0,        # multiplies the starting speed (speed stays constant)
    "radius": 30,
    "contact_damage": 5,      # damage when the two balls bump

    "max_super": 100,         # size of the super bar
    "super_per_hit": 25,      # super gained each time the lightsaber hits (4 hits = super)
    "super_per_contact": 5,   # super gained when the balls bump
}

# Main attack: a red lightsaber. When the enemy is in reach he swings it in a big arc.
ABILITY = {
    "swing_cooldown": 120,    # frames between two swings (60 = 1 second, 120 = 2 seconds)
    "damage": 80,            # damage of one swing (it can only hit once per swing)
    "blade_length": 60,       # length of the glowing blade
    "hilt_length": 16,        # length of the handle between the ball and the blade
    "blade_thickness": 16,    # hitbox thickness of the blade
    "swing_arc": 200,         # how wide the swing is (degrees)
    "swing_frames": 14,       # how long one swing takes (frames)
    "trigger_extra": 25,      # starts swinging when the enemy is this many pixels outside the blade's reach
    "swing_only_in_range": True,   # ON = swings only when the enemy is close, OFF = swings every cooldown no matter what
    "idle_turn": 0.08,        # how fast the saber turns toward the enemy while resting (radians per frame)
}

# Super: small rocks appear around him and are thrown at the enemy. A rock that hits makes the enemy
# fly from wall to wall (a random wall each time) and every wall it touches hurts.
ULTIMATE = {
    "rock_count": 3,          # how many rocks
    "rock_radius": 12,        # size of a rock
    "orbit_radius": 62,       # how far from him the rocks float before they are thrown
    "appear_frames": 30,      # rocks grow out of him over this many frames
    "throw_stagger": 14,      # frames between two throws
    "rock_speed": 11.0,       # pixels per frame
    "rock_turn": 0.06,        # how much a flying rock can steer toward the enemy (radians per frame, 0 = straight)
    "rock_damage": 0,         # damage of the rock itself (the real damage comes from the walls)

    "curse_duration": 120,    # frames the enemy keeps flying into walls (180 = 3 seconds)
    "curse_speed": 1000.0,    # speed of the enemy while it is flying into walls (pixels/second)
    "wall_damage": 50,       # damage every time the enemy touches a wall
    "wall_cooldown": 8,       # frames before the same hit can count again
}
# ===========================================================

BLADE = (255, 45, 55)
BLADE_LIGHT = (255, 170, 170)
ROCK_FILL = (122, 110, 100)
ROCK_EDGE = (58, 52, 48)
CURSE_COLOR = (255, 150, 60)

_avatar_cache = {}


def make_avatar(radius):
    """Dark red ball with angry eyes (used when there is no 8.png)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(40):
        t = i / 39
        col = (int(40 + 170 * t), int(8 + 42 * t), int(12 + 43 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.9))))
    for sx in (-1, 1):
        eye = [(c + sx * c * 0.10, c + c * 0.02), (c + sx * c * 0.52, c - c * 0.22),
               (c + sx * c * 0.48, c + c * 0.08), (c + sx * c * 0.16, c + c * 0.14)]
        pygame.draw.polygon(big, (255, 255, 255), eye)
        pygame.draw.circle(big, (20, 10, 14), (int(c + sx * c * 0.30), int(c + c * 0.0)), int(c * 0.06))
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


def _glow_line(screen, p1, p2, color, core_w, glow_w):
    """A glowing lightsaber blade: soft halo, colored body, white core."""
    pad = glow_w + 4
    x0 = int(min(p1[0], p2[0]) - pad)
    y0 = int(min(p1[1], p2[1]) - pad)
    w = int(abs(p1[0] - p2[0]) + 2 * pad)
    h = int(abs(p1[1] - p2[1]) + 2 * pad)
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    a = (p1[0] - x0, p1[1] - y0)
    b = (p2[0] - x0, p2[1] - y0)
    pygame.draw.line(layer, (*color, 40), a, b, glow_w)
    pygame.draw.line(layer, (*color, 95), a, b, int(glow_w * 0.65))
    pygame.draw.line(layer, (*color, 255), a, b, core_w)
    for p in (a, b):
        pygame.draw.circle(layer, (*color, 255), (int(p[0]), int(p[1])), core_w // 2)
    pygame.draw.line(layer, (255, 255, 255, 255), a, b, max(2, core_w // 2 - 1))
    screen.blit(layer, (x0, y0))


def _debris(x, y, radius, frames, color):
    return {"x": x, "y": y, "radius": radius, "timer": frames, "max": frames, "color": color,
            "sparks": [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.5, 5.0)) for _ in range(10)]}


# ======================================================================
#  SUPER: the rocks
# ======================================================================
class Rock:
    """Grows out of DANGER, floats around him, then is thrown at the enemy (steering a little)."""

    def __init__(self, owner, target, orbit_angle, index):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        self.radius = U["rock_radius"]
        self.orbit = orbit_angle
        self.launch_at = U["appear_frames"] + index * U["throw_stagger"]
        self.state = "orbit"
        self.t = 0
        self.life = 240
        self.scale = 0.0
        self.angle = 0.0
        self.rot = random.uniform(0, TAU)
        self.spin = random.choice((-1, 1)) * random.uniform(0.12, 0.3)
        self.x, self.y = owner.body.position.x, owner.body.position.y
        self.active = True
        self.shape = [(i * TAU / 8 + random.uniform(-0.2, 0.2), random.uniform(0.72, 1.15)) for i in range(8)]
        self.sprite = load_sprite("rock", int(self.radius * 2.4), int(self.radius * 2.4))   # optional picture: assets/rock.png

    def _crumble(self, explosions):
        self.active = False
        explosions.append(_debris(self.x, self.y, 24, 14, (170, 140, 100)))
        sounds.play("bump")

    def update(self, explosions, storm):
        if not self.active:
            return
        U = ULTIMATE
        o, t = self.owner, self.target
        if o.hp <= 0 or t is None or t.hp <= 0:
            self.active = False
            return
        self.t += 1
        self.rot += self.spin

        if self.state == "orbit":
            self.orbit += 0.14
            grow = min(1.0, self.t / max(1, U["appear_frames"]))
            d = U["orbit_radius"] * grow
            self.x = o.body.position.x + math.cos(self.orbit) * d
            self.y = o.body.position.y + math.sin(self.orbit) * d
            self.scale = grow
            if self.t >= self.launch_at:
                self.state = "fly"
                self.angle = math.atan2(t.body.position.y - self.y, t.body.position.x - self.x)
                sounds.play("star")
            return

        tp = t.body.position
        self.angle = _turn(self.angle, math.atan2(tp.y - self.y, tp.x - self.x), U["rock_turn"])
        self.x += math.cos(self.angle) * U["rock_speed"]
        self.y += math.sin(self.angle) * U["rock_speed"]
        self.life -= 1
        r = self.radius
        wall = (self.x - r <= ARENA_LEFT or self.x + r >= ARENA_RIGHT or
                self.y - r <= ARENA_TOP or self.y + r >= ARENA_BOTTOM)
        if wall or self.life <= 0:
            self._crumble(explosions)
        elif math.hypot(self.x - tp.x, self.y - tp.y) <= r + t.radius:
            self.active = False
            storm.rock_hit(self, explosions)

    def draw(self, screen):
        if not self.active:
            return
        x, y, r = self.x, self.y, self.radius
        s = max(0.05, self.scale)
        if self.state == "fly":                       # dusty streak behind the rock
            bx, by = x - math.cos(self.angle) * 16, y - math.sin(self.angle) * 16
            pygame.draw.line(screen, (200, 170, 120), (int(bx), int(by)), (int(x), int(y)), 3)
        if self.sprite:
            img = pygame.transform.rotozoom(self.sprite, -math.degrees(self.rot), s)
            screen.blit(img, img.get_rect(center=(int(x), int(y))))
            return
        pts = [(x + math.cos(self.rot + a) * r * k * s, y + math.sin(self.rot + a) * r * k * s) for a, k in self.shape]
        pygame.draw.polygon(screen, ROCK_FILL, pts)
        pygame.draw.polygon(screen, ROCK_EDGE, pts, 2)
        pygame.draw.circle(screen, (170, 158, 145), (int(x - r * 0.3 * s), int(y - r * 0.3 * s)), max(1, int(r * 0.25 * s)))


class RockStorm:
    """One object that owns all the rocks of one super AND the wall-bouncing curse they cause.
    (It lives in the projectile list, so it keeps working even if DANGER gets stunned.)"""

    def __init__(self, owner, target):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        n = max(1, U["rock_count"])
        base = random.uniform(0, TAU)
        self.rocks = [Rock(owner, target, base + i * TAU / n, i) for i in range(n)]
        self.curse = 0             # frames left of the wall-bouncing
        self.wall_cd = 0
        self.t = 0
        self.active = True

    # ---------- the curse ----------
    def _touching(self):
        t = self.target
        p = t.body.position
        r, tol = t.radius, 7
        s = set()
        if p.x - r <= ARENA_LEFT + tol:
            s.add("L")
        if p.x + r >= ARENA_RIGHT - tol:
            s.add("R")
        if p.y - r <= ARENA_TOP + tol:
            s.add("T")
        if p.y + r >= ARENA_BOTTOM - tol:
            s.add("B")
        return s

    def _redirect(self, avoid):
        """Send the enemy flying toward a random point on a random wall (never the one it is at)."""
        t = self.target
        p = t.body.position
        options = [w for w in "LRTB" if w not in avoid] or list("LRTB")
        w = random.choice(options)
        W, H = ARENA_RIGHT - ARENA_LEFT, ARENA_BOTTOM - ARENA_TOP
        k = random.uniform(0.15, 0.85)
        if w == "L":
            px, py = ARENA_LEFT, ARENA_TOP + H * k
        elif w == "R":
            px, py = ARENA_RIGHT, ARENA_TOP + H * k
        elif w == "T":
            px, py = ARENA_LEFT + W * k, ARENA_TOP
        else:
            px, py = ARENA_LEFT + W * k, ARENA_BOTTOM
        dx, dy = px - p.x, py - p.y
        d = math.hypot(dx, dy) or 1.0
        dx, dy = dx / d, dy / d
        sp = ULTIMATE["curse_speed"]
        t.move_dir = (dx, dy)
        t.body.velocity = (dx * sp, dy * sp)

    def _start_curse(self):
        t = self.target
        self.curse = ULTIMATE["curse_duration"]
        self.wall_cd = 0
        t.popups.append(("PINBALL!", CURSE_COLOR))
        self._redirect(self._touching())

    def rock_hit(self, rock, explosions):
        U = ULTIMATE
        t = self.target
        explosions.append(_debris(rock.x, rock.y, 34, 16, CURSE_COLOR))
        sounds.play("hit")
        if U["rock_damage"] > 0:
            t.hp -= U["rock_damage"]
        if self.curse <= 0 and t.hp > 0:          # a rock only starts the curse; it can't be stacked or refreshed
            self._start_curse()

    def _update_curse(self, explosions):
        U = ULTIMATE
        t = self.target
        if t.hp <= 0:
            self.curse = 0
            return
        self.curse -= 1
        if self.curse <= 0:                       # over: the enemy slows back down to its normal speed
            t.knock_speed = U["curse_speed"]
            t.knock_total = t.knock_timer = 20
            return
        t.knock_speed = U["curse_speed"]          # keeps it at curse speed (the knockback timer is refreshed every frame)
        t.knock_total = 1
        t.knock_timer = 2
        if self.wall_cd > 0:
            self.wall_cd -= 1
            return
        touching = self._touching()
        if touching:
            p = t.body.position
            ex = ARENA_LEFT if "L" in touching else (ARENA_RIGHT if "R" in touching else p.x)
            ey = ARENA_TOP if "T" in touching else (ARENA_BOTTOM if "B" in touching else p.y)
            t.hp -= U["wall_damage"]
            explosions.append(_debris(ex, ey, 46, 16, CURSE_COLOR))
            sounds.play("boom")
            self.wall_cd = U["wall_cooldown"]
            self._redirect(touching)

    # ---------- per frame ----------
    def update(self, explosions):
        if not self.active:
            return
        self.t += 1
        for r in self.rocks:
            r.update(explosions, self)
        self.rocks = [r for r in self.rocks if r.active]
        if self.curse > 0:
            self._update_curse(explosions)
        self.active = bool(self.rocks) or self.curse > 0

    def draw(self, screen):
        t = self.target
        if self.curse > 0 and t.hp > 0:           # glowing ring with little rocks circling the enemy
            x, y = int(t.body.position.x), int(t.body.position.y)
            ring = t.radius + 10
            c = ring + 14
            fade = min(1.0, self.curse / 20)
            layer = pygame.Surface((c * 2, c * 2), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*CURSE_COLOR, int(60 * fade)), (c, c), ring + 6)
            pygame.draw.circle(layer, (255, 190, 90, int(200 * fade)), (c, c), ring, 2)
            screen.blit(layer, (x - c, y - c))
            for i in range(5):
                a = self.t * 0.2 + i * TAU / 5
                px, py = int(x + math.cos(a) * ring), int(y + math.sin(a) * ring)
                pygame.draw.circle(screen, ROCK_FILL, (px, py), 5)
                pygame.draw.circle(screen, ROCK_EDGE, (px, py), 5, 2)
        for r in self.rocks:
            r.draw(screen)


# ======================================================================
#  DANGER himself
# ======================================================================
class Danger(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):          # no 8.png -> built-in design
            self.surface = make_avatar(self.radius)
        self.saber_angle = math.atan2(velocity[1], velocity[0])
        self.swing_cd = 0
        self.swinging = False
        self.swing_t = 0
        self.swing_a0 = 0.0
        self.swing_sign = 1          # +1 / -1: the swing direction alternates every time
        self.swing_hit = False
        self.swoosh = None           # [start angle, end angle, alpha] of the fading arc trail

    # ---------- geometry ----------
    def _blade_points(self, a):
        A = ABILITY
        cx, cy = self.body.position.x, self.body.position.y
        ca, sa = math.cos(a), math.sin(a)
        d1 = self.radius + A["hilt_length"]
        d2 = d1 + A["blade_length"]
        return (cx + ca * d1, cy + sa * d1), (cx + ca * d2, cy + sa * d2)

    def _spark(self, x, y, effects):
        angles = [random.uniform(0, TAU) for _ in range(7)]

        def draw(screen):
            for a in angles:
                ln = random.uniform(20, 38)
                end = (x + math.cos(a) * ln, y + math.sin(a) * ln)
                pygame.draw.line(screen, BLADE, (x, y), end, 3)
                pygame.draw.line(screen, (255, 235, 235), (x, y), end, 1)
        effects.append({"x": x, "y": y, "sprite": None, "timer": 12, "draw": draw})

    # ---------- lightsaber ----------
    def _start_swing(self, base):
        A = ABILITY
        self.swinging = True
        self.swing_t = 0
        self.swing_hit = False
        self.swing_a0 = base - self.swing_sign * math.radians(A["swing_arc"]) / 2
        self.saber_angle = self.swing_a0
        self.swing_cd = A["swing_cooldown"]
        sounds.play("sword")

    def _check_hit(self, a, target, effects):
        A = ABILITY
        p1, p2 = self._blade_points(a)
        tx, ty = target.body.position.x, target.body.position.y
        qx, qy = _closest_on_segment(tx, ty, p1[0], p1[1], p2[0], p2[1])
        if math.hypot(tx - qx, ty - qy) <= target.radius + A["blade_thickness"] / 2:
            self.swing_hit = True
            target.hp -= A["damage"]
            self.add_super(self.super_per_hit)
            self._spark(qx, qy, effects)
            sounds.play("hit")

    def _update_swing(self, target, effects):
        A = ABILITY
        self.swing_t += 1
        p = min(1.0, self.swing_t / max(1, A["swing_frames"]))
        ease = p * p * (3 - 2 * p)
        arc = math.radians(A["swing_arc"])
        new_a = self.swing_a0 + self.swing_sign * arc * ease
        if target is not None and not self.swing_hit:     # check a few angles in between, so a fast blade can't skip the enemy
            for k in range(1, 5):
                self._check_hit(self.saber_angle + (new_a - self.saber_angle) * k / 4, target, effects)
                if self.swing_hit:
                    break
        self.saber_angle = new_a
        self.swoosh = [self.swing_a0, new_a, 120]
        if p >= 1.0:
            self.swinging = False
            self.swing_sign = -self.swing_sign

    # ---------- super ----------
    def _ultimate(self, target, projectiles):
        projectiles.append(RockStorm(self, target))
        sounds.play("super")
        sounds.play("boom")

    # ---------- update ----------
    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        A = ABILITY
        alive = target is not None and target.hp > 0

        if self.swing_cd > 0:
            self.swing_cd -= 1
        if self.swoosh and not self.swinging:
            self.swoosh[2] -= 14
            if self.swoosh[2] <= 0:
                self.swoosh = None

        if self.swinging:
            self._update_swing(target if alive else None, scratch_effects)
        else:
            cx, cy = self.body.position.x, self.body.position.y
            if alive:
                base = math.atan2(target.body.position.y - cy, target.body.position.x - cx)
            else:
                vx, vy = self.body.velocity
                base = math.atan2(vy, vx) if (vx or vy) else self.saber_angle
            want = base - self.swing_sign * math.radians(A["swing_arc"]) / 2     # ready position = where the next swing starts
            self.saber_angle = _turn(self.saber_angle, want, A["idle_turn"])
            if self.swing_cd <= 0 and alive:
                reach = self.radius + A["hilt_length"] + A["blade_length"] + target.radius + A["trigger_extra"]
                dist = math.hypot(target.body.position.x - cx, target.body.position.y - cy)
                if dist <= reach or not A["swing_only_in_range"]:
                    self._start_swing(base)

        if alive and self.super_charge >= self.max_super:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)

    # ---------- drawing ----------
    def draw(self, screen):
        if self.hp <= 0:
            return
        super().draw(screen)
        A = ABILITY
        x, y = self.body.position.x, self.body.position.y
        r = self.radius

        if self.swoosh and self.swoosh[2] > 0:           # the arc the blade just cut through the air
            a0, a1, alpha = self.swoosh
            span = a1 - a0
            if abs(span) > 0.01:
                r_out = r + A["hilt_length"] + A["blade_length"]
                r_in = r + A["hilt_length"] + A["blade_length"] * 0.35
                steps = max(4, int(abs(span) / 0.08))
                outer = [(r_out + math.cos(a0 + span * i / steps) * r_out,
                          r_out + math.sin(a0 + span * i / steps) * r_out) for i in range(steps + 1)]
                inner = [(r_out + math.cos(a0 + span * i / steps) * r_in,
                          r_out + math.sin(a0 + span * i / steps) * r_in) for i in range(steps, -1, -1)]
                size = int(r_out * 2) + 2
                layer = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.polygon(layer, (*BLADE, max(0, min(255, int(alpha)))), outer + inner)
                screen.blit(layer, (int(x - r_out), int(y - r_out)))

        ca, sa = math.cos(self.saber_angle), math.sin(self.saber_angle)
        h0 = (x + ca * (r - 2), y + sa * (r - 2))
        h1 = (x + ca * (r + A["hilt_length"]), y + sa * (r + A["hilt_length"]))
        pygame.draw.line(screen, (45, 45, 55), h0, h1, 9)
        pygame.draw.line(screen, (190, 190, 205), h0, h1, 5)
        p1, p2 = self._blade_points(self.saber_angle)
        _glow_line(screen, p1, p2, BLADE, 10, 28)
        pygame.draw.circle(screen, (225, 225, 235), (int(h1[0]), int(h1[1])), 5)
