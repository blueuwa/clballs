import math
import pygame
import pymunk
import sounds

from brawler import BaseBrawler, Projectile
from config import load_sprite

STATS = {
    "name": "STARR NOVA",
    "filename": "1.png",
    "max_hp": 2500,
    "speed_mult": 1.0,        
    "radius": 30,
    "contact_damage": 10,     

    "max_super": 100,         
    "super_per_hit": 10,      
    "super_per_contact": 5,  
}

ABILITY = {
    "attack_cooldown": 100,   

    "star_damage": 100,
    "star_speed": 7.0,
    "star_radius": 11,
    "star_trail_length": 14,              
    "star_trail_color": (60, 220, 255),   

    "homing_damage": 80,
    "homing_speed": 6.0,
    "homing_radius": 6,
}

ULTIMATE = {
    "dash_speed": 1200.0,     
    "dash_duration": 20,      
    "sword_damage": 150,
    "sword_range": 105,       
    "sword_arc": 180,         
    "sword_visual_frames": 15,
    "sword_sprite": "novasword",   
    "swoosh_color": (150, 240, 255),  
}


class StarrNova(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        self.dash_timer = 0

    def _dash(self, target, scratch_effects):
        if target and target.hp > 0:
            dx = target.body.position.x - self.body.position.x
            dy = target.body.position.y - self.body.position.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                s = ULTIMATE["dash_speed"]
                self.body.velocity = (dx / dist * s, dy / dist * s)

        self.dash_timer -= 1
        if self.dash_timer <= 0:
            self.speed_override = None
            self._swing_sword(target, scratch_effects)

    def _swing_sword(self, target, scratch_effects):
        sounds.play("sword")
        x, y = self.body.position.x, self.body.position.y
        angle = 0.0
        if target and target.hp > 0:
            t = target.body.position
            angle = math.atan2(t.y - y, t.x - x)
            dist = math.hypot(t.x - x, t.y - y)
            if dist <= ULTIMATE["sword_range"] + target.radius:
                target.hp -= ULTIMATE["sword_damage"]

        frames = ULTIMATE["sword_visual_frames"]
        state = {"t": 0}
        reach = ULTIMATE["sword_range"]
        arc = math.radians(ULTIMATE["sword_arc"])

        sword = load_sprite(ULTIMATE["sword_sprite"], reach * 2, reach * 2)
        color = ULTIMATE["swoosh_color"]
        a_start = angle - arc / 2

        def draw_swoosh(screen, a_now):
            span = a_now - a_start
            if span <= 0.01:
                return
            steps = max(4, int(span / 0.08))
            outer = [(reach + math.cos(a_start + span * i / steps) * reach,
                      reach + math.sin(a_start + span * i / steps) * reach) for i in range(steps + 1)]
            inner = [(reach + math.cos(a_start + span * i / steps) * reach * 0.5,
                      reach + math.sin(a_start + span * i / steps) * reach * 0.5) for i in range(steps, -1, -1)]
            layer = pygame.Surface((reach * 2, reach * 2), pygame.SRCALPHA)
            pygame.draw.polygon(layer, (*color, 110), outer + inner)
            screen.blit(layer, (int(x - reach), int(y - reach)))

        def draw(screen):
            progress = min(1.0, state["t"] / max(1, frames - 1))
            state["t"] += 1
            a = a_start + arc * progress

            if sword:
                draw_swoosh(screen, a)
                rotated = pygame.transform.rotate(sword, -math.degrees(a))
                screen.blit(rotated, rotated.get_rect(center=(int(x), int(y))))
                return

            end = (x + math.cos(a) * reach, y + math.sin(a) * reach)
            pygame.draw.circle(screen, (255, 230, 80), (int(x), int(y)), reach, 2)
            pygame.draw.line(screen, (255, 255, 255), (x, y), end, 12)
            pygame.draw.line(screen, (255, 215, 0), (x, y), end, 6)

        scratch_effects.append({"x": x, "y": y, "sprite": None, "timer": frames, "draw": draw})

    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return

        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1

        if self.dash_timer > 0:
            self._dash(target, scratch_effects)
            return

        if self.super_charge >= self.max_super and target and target.hp > 0:
            self.super_charge = 0
            self.trigger_super()
            self.dash_timer = ULTIMATE["dash_duration"]
            self.speed_override = ULTIMATE["dash_speed"]
            sounds.play("super")
            sounds.play("dash")
            self._dash(target, scratch_effects)
            return

        pos = (self.body.position.x, self.body.position.y)

        if self.attack_cooldown <= 0:
            sounds.play("star")
            vel = self.body.velocity
            direction = vel.normalized() if vel.length > 0 else pymunk.Vec2d(1, 0)

            star1_vel = (direction.x * ABILITY["star_speed"], direction.y * ABILITY["star_speed"])
            projectiles.append(Projectile(
                self, target, "star", "novastar", pos, star1_vel,
                damage=ABILITY["star_damage"], radius=ABILITY["star_radius"],
                trail_length=ABILITY["star_trail_length"], trail_color=ABILITY["star_trail_color"]
            ))

            star2_vel = (-direction.x * ABILITY["homing_speed"], -direction.y * ABILITY["homing_speed"])
            projectiles.append(Projectile(
                self, target, "star", "novastar", pos, star2_vel,
                damage=ABILITY["homing_damage"], radius=ABILITY["homing_radius"],
                is_homing=True, homing_speed=ABILITY["homing_speed"],
                trail_length=ABILITY["star_trail_length"], trail_color=ABILITY["star_trail_color"]
            ))

            self.attack_cooldown = ABILITY["attack_cooldown"]