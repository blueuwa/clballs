import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM

BLUE_GLOW = (80, 180, 255)
YELLOW_CHARGE = (255, 225, 70)

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "SAUCER",
    "filename": "12.png",
    "max_hp": 3000,
    "speed_mult": 1.0,        # multiplies the starting speed (speed stays constant)
    "radius": 30,
    "contact_damage": 0,      # SAUCER deals NO damage at all, except with the beam

    "max_super": 100,         # size of the super bar
    "super_per_hit": 0,       # nothing charges the super except time (see ULTIMATE)
    "super_per_contact": 0,
}

# The only thing SAUCER does: a gigantic beam of blue light.
ULTIMATE = {
    "charge_frames": 900,     # the super charges by itself: 900 frames = 15 seconds
    "seek_corner_at": 0.85,   # at 85% charge, he starts flying to a corner to set up the shot
    "corner_speed": 6.0,      # pixels per frame while flying to the corner
    "ray_duration": 300,      # 5 seconds
    "total_damage": 2500,     # damage if the enemy stays in the beam the WHOLE time (split into every frame)
    "ray_width": 100,         # thickness of the beam (big, but a moving enemy can still get out)
    "track_speed": 1,         # degrees per frame the beam turns to follow the enemy (0 = never turns)
    "stand_still": True,      # SAUCER can't move (or be knocked back) while firing
    "grow_frames": 40,        # beam widens / narrows over this many frames at the start / end
    "fade_frames": 15,        # the screen darkens / brightens over this many frames
    "dim_alpha": 200,         # how dark everything else gets (0-255)

    # If the beam stays on the enemy for MORE than this many frames in total,
    # SAUCER gets part of the super bar back when the beam ends.
    "refund_time": 180,       # 3 seconds
    "refund_fraction": 0.5,   # half of the bar
}
# ===========================================================


def _closest_on_segment(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return ax + abx * t, ay + aby * t


def _turn(cur, want, step):
    d = (want - cur + math.pi) % (2 * math.pi) - math.pi
    return cur + max(-step, min(step, d))


def _scale(col, k):
    return tuple(max(0, min(255, int(v * k))) for v in col)


class Saucer(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        self.charge_frames = 0
        self.ray_timer = 0
        self.ray_frame = 0
        self.ray_angle = 0.0
        self.ray_geom = None          # ((ox, oy), (ex, ey), half_width)
        self.ray_target = None
        self.ray_hit_now = False
        self.hit_frames = 0           # frames the beam has been on the enemy
        self.dmg_accum = 0.0

        self.spin = 0.0               # used for the charging aura

    # ---------- the beam ----------
    def _fire(self, target):
        U = ULTIMATE
        self.charge_frames = 0
        self.super_charge = 0
        self.trigger_super()
        self.ray_timer = U["ray_duration"]
        self.ray_frame = 0
        self.hit_frames = 0
        self.dmg_accum = 0.0
        self.ray_target = target
        self.ray_angle = math.atan2(target.body.position.y - self.body.position.y,
                                    target.body.position.x - self.body.position.x)
        if U["stand_still"]:
            self.speed_override = 0.0
        sounds.play("super")
        sounds.play("boom")
        self._update_ray(target)

    def _end_ray(self, refund):
        U = ULTIMATE
        self.ray_timer = 0
        self.ray_geom = None
        self.ray_hit_now = False
        self.speed_override = None
        if refund and self.hit_frames > U["refund_time"]:
            self.charge_frames = int(U["charge_frames"] * U["refund_fraction"])
            self.super_charge = int(self.max_super * U["refund_fraction"])
            self.popups.append(("SUPER BACK!", BLUE_GLOW))

    def _update_ray(self, target):
        U = ULTIMATE
        self.ray_frame += 1
        cx, cy = self.body.position.x, self.body.position.y
        tx, ty = target.body.position.x, target.body.position.y

        # the beam slowly turns toward the enemy (slowly enough that a moving enemy can slip out)
        want = math.atan2(ty - cy, tx - cx)
        self.ray_angle = _turn(self.ray_angle, want, math.radians(U["track_speed"]))
        ux, uy = math.cos(self.ray_angle), math.sin(self.ray_angle)

        tmax = 10 ** 6                    # the beam goes on until the arena wall
        if ux > 1e-6:
            tmax = min(tmax, (ARENA_RIGHT - cx) / ux)
        elif ux < -1e-6:
            tmax = min(tmax, (ARENA_LEFT - cx) / ux)
        if uy > 1e-6:
            tmax = min(tmax, (ARENA_BOTTOM - cy) / uy)
        elif uy < -1e-6:
            tmax = min(tmax, (ARENA_TOP - cy) / uy)
        ex, ey = cx + ux * tmax, cy + uy * tmax

        grow = min(1.0, self.ray_frame / U["grow_frames"], self.ray_timer / U["grow_frames"])
        half = U["ray_width"] * max(0.0, grow) / 2
        self.ray_geom = ((cx, cy), (ex, ey), half)

        qx, qy = _closest_on_segment(tx, ty, cx, cy, ex, ey)
        self.ray_hit_now = math.hypot(tx - qx, ty - qy) <= half + target.radius
        if self.ray_hit_now:
            # the total damage is split evenly over every frame of the beam
            self.hit_frames += 1
            self.dmg_accum += U["total_damage"] / U["ray_duration"]
            whole = int(self.dmg_accum)
            self.dmg_accum -= whole
            target.hp -= whole

        self.ray_timer -= 1
        if self.ray_timer <= 0:
            self._end_ray(refund=True)

    # ---------- update ----------
    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        U = ULTIMATE
        alive = target is not None and target.hp > 0

        if self.ray_timer > 0:
            if alive:
                self._update_ray(target)
            else:
                self._end_ray(refund=False)
            return

        # the super bar fills by itself
        self.charge_frames = min(U["charge_frames"], self.charge_frames + self.charge_rate())
        self.super_charge = int(self.max_super * self.charge_frames / U["charge_frames"])

        # Seek a corner to shoot from when almost fully charged
        k = self.charge_frames / U["charge_frames"]
        if k >= U["seek_corner_at"] and alive:
            # Pick the corner furthest from the target
            cx, cy = self.body.position.x, self.body.position.y
            tx, ty = target.body.position.x, target.body.position.y
            corners = [
                (ARENA_LEFT + 40, ARENA_TOP + 40),
                (ARENA_RIGHT - 40, ARENA_TOP + 40),
                (ARENA_LEFT + 40, ARENA_BOTTOM - 40),
                (ARENA_RIGHT - 40, ARENA_BOTTOM - 40)
            ]
            # Find the corner that gives the most distance from the enemy
            best_corner = max(corners, key=lambda c: math.hypot(c[0] - tx, c[1] - ty))
            
            # Fly toward the corner
            dx = best_corner[0] - cx
            dy = best_corner[1] - cy
            d = math.hypot(dx, dy)
            
            if d > 10:  # Don't jitter when basically there
                self.move_dir = (dx / d, dy / d)
                self.speed_override = U["corner_speed"]
                self.body.velocity = (dx / d * U["corner_speed"], dy / d * U["corner_speed"])
            else:
                # settle in the corner
                self.speed_override = 0.0
                self.body.velocity = (0, 0)

        if self.charge_frames >= U["charge_frames"] and alive:
            self._fire(target)

    # ---------- drawing ----------
    def draw(self, screen):
        if self.hp <= 0:
            return
        
        U = ULTIMATE
        k = 1.0 if self.ray_timer > 0 else self.charge_frames / U["charge_frames"]
        x, y = int(self.body.position.x), int(self.body.position.y)
        r = self.radius

        if k > 0:
            # --- Charging Aura ---
            self.spin += 0.05 + 0.2 * k  # spin faster as it charges
            pulse = 0.5 + 0.5 * math.sin(self.charge_frames * 0.15 * (1 + 2 * k) + self.ray_frame * 0.4)
            
            aura_size = (r + 80) * 2
            c = aura_size // 2
            aura = pygame.Surface((aura_size, aura_size), pygame.SRCALPHA)
            
            # 1. Soft glowing background
            glow_radius = r + 12 + int(12 * k * pulse)
            pygame.draw.circle(aura, (*BLUE_GLOW, int(40 * k)), (c, c), glow_radius)
            pygame.draw.circle(aura, (*BLUE_GLOW, int(90 * k)), (c, c), glow_radius, 2)

            # 2. Swirling energy vortex lines spiraling inward
            for arm in range(5):
                arm_angle = self.spin + arm * (math.pi * 2 / 5)
                pts = []
                for i in range(15):
                    f = i / 14
                    dist = (r + 50) - f * 45
                    a = arm_angle + f * 3.0  # spiral twist
                    px = c + math.cos(a) * dist
                    py = c + math.sin(a) * dist
                    pts.append((px, py))
                
                # Draw the trail fading out at the edges
                for i in range(len(pts) - 1):
                    frac = i / len(pts)
                    alpha = int(200 * frac * k)
                    width = max(1, int(4 * frac))
                    pygame.draw.line(aura, (*YELLOW_CHARGE, alpha), pts[i], pts[i+1], width)

            # 3. Bright swirling dots on the arms
            for arm in range(5):
                arm_angle = self.spin + arm * (math.pi * 2 / 5)
                for dot in range(2):
                    f = 0.3 + dot * 0.4
                    dist = (r + 50) - f * 45
                    a = arm_angle + f * 3.0
                    px = c + math.cos(a) * dist
                    py = c + math.sin(a) * dist
                    pygame.draw.circle(aura, YELLOW_CHARGE, (int(px), int(py)), max(2, int(6 * k)))
                    pygame.draw.circle(aura, (255, 255, 255), (int(px), int(py)), max(1, int(2 * k)))

            screen.blit(aura, (x - c, y - c))

        super().draw(screen)

        # 4. Super intense bright core when almost ready
        if k > 0.8 and self.ray_timer <= 0:
            flash = (k - 0.8) / 0.2
            if int(self.charge_frames) % 10 < 3:
                core = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
                pygame.draw.circle(core, (255, 255, 255, int(150 * flash)), (r*2, r*2), r + 4)
                screen.blit(core, (x - r*2, y - r*2))

    def draw_overlay(self, screen):
        """Called by main.py after everything else is drawn: darkens the whole screen except the beam."""
        if self.ray_timer <= 0 or not self.ray_geom or self.hp <= 0:
            return
        tgt = self.ray_target
        if tgt is None or tgt.hp <= 0:
            return

        U = ULTIMATE
        (ox, oy), (ex, ey), half = self.ray_geom
        k = max(0.0, min(1.0, self.ray_frame / U["fade_frames"], self.ray_timer / U["fade_frames"]))
        L = math.hypot(ex - ox, ey - oy) or 1.0
        ux, uy = (ex - ox) / L, (ey - oy) / L
        nx, ny = -uy, ux

        def quad(width, dx=0, dy=0):
            h = width / 2
            return [(ox + nx * h - dx, oy + ny * h - dy), (ex + nx * h - dx, ey + ny * h - dy),
                    (ex - nx * h - dx, ey - ny * h - dy), (ox - nx * h - dx, oy - ny * h - dy)]

        # 1) darkness everywhere, with a soft-edged hole around the beam and around SAUCER
        a = int(U["dim_alpha"] * k)
        dark = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        dark.fill((3, 4, 14, a))
        if half > 1:
            for mult, frac in ((1.9, 0.6), (1.5, 0.3), (1.15, 0.1), (1.0, 0.0)):
                col = (3, 4, 14, int(a * frac))
                pygame.draw.polygon(dark, col, quad(half * 2 * mult))
                pygame.draw.circle(dark, col, (int(ox), int(oy)), max(1, int(half * mult)))
        for rr, frac in ((self.radius + 44, 0.55), (self.radius + 26, 0.2), (self.radius + 12, 0.0)):
            pygame.draw.circle(dark, (3, 4, 14, int(a * frac)), (int(ox), int(oy)), rr)
        screen.blit(dark, (0, 0))

        # 2) the beam itself: light added on top (only needs to cover the arena)
        pad = 100
        ax, ay = ARENA_LEFT - pad, ARENA_TOP - pad
        light = pygame.Surface((ARENA_RIGHT - ARENA_LEFT + 2 * pad, ARENA_BOTTOM - ARENA_TOP + 2 * pad))
        kk = k * (0.92 + 0.08 * random.random())     # tiny shimmer
        
        # Layer the beam: deep blue edges to a blinding white center
        layers = (
            (2.2, (10, 30, 80)),       # wide outer haze
            (1.6, (30, 90, 180)),      # deep blue body
            (1.1, (80, 180, 255)),     # bright blue core
            (0.7, (180, 230, 255)),    # icy white-blue
            (0.3, (255, 255, 255))     # blinding white center
        )
        
        for mult, col in layers:
            c = _scale(col, kk)
            pygame.draw.polygon(light, c, quad(half * 2 * mult, ax, ay))
            pygame.draw.circle(light, c, (int(ox - ax), int(oy - ay)), max(1, int(half * mult)))
            
        # Add energy pulses rippling down the beam
        if half > 4:
            for i in range(6):
                # Move the bright bands along the beam
                s = (self.ray_frame * 25 + i * L / 6) % L
                px, py = ox + ux * s - ax, oy + uy * s - ay
                hw = half * 0.9
                # Draw a bright horizontal line across the beam width
                pygame.draw.line(light, _scale((255, 255, 255), kk), 
                                 (px + nx * hw, py + ny * hw),
                                 (px - nx * hw, py - ny * hw), 4)
                
            # Add floating energy specks
            for _ in range(30):
                s, o = random.uniform(0, L), random.uniform(-half, half)
                pygame.draw.circle(light, _scale((255, 255, 255), kk),
                                   (int(ox + ux * s + nx * o - ax), int(oy + uy * s + ny * o - ay)),
                                   random.randint(1, 3))
                                   
        # Add a massive bright glow at the origin (the firing point)
        pygame.draw.circle(light, _scale((255, 255, 255), kk), (int(ox - ax), int(oy - ay)), int(half * 1.5))

        screen.blit(light, (ax, ay), special_flags=pygame.BLEND_RGB_ADD)

        # 3) SAUCER stays crisp and bright; the enemy is redrawn on top of the glare while it is inside the beam
        self.draw(screen)
        if self.ray_hit_now:
            tgt.draw(screen)