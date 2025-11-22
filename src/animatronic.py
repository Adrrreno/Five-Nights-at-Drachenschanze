import pygame
import random
from dataclasses import dataclass

class GameContext:
    """Contains all external data the Animatronic logic needs."""
    def __init__(self,
                 rooms,
                 room_connections,
                 camera_order,
                 anim_img,
                 player_room,
                 door_checker,
                 get_power):

        self.rooms = rooms
        self.room_connections = room_connections
        self.camera_order = camera_order
        self.anim_img = anim_img                 # ✔ REQUIRED
        self.player_room = player_room
        self.is_door_closed_between = door_checker
        self.get_power = get_power


class Animatronic:
    def __init__(self, name, start_room, game: GameContext, route=None):
        self.name = name
        self.game = game
        self.current_room = start_room
        self.pos = list(random.choice(game.rooms[start_room].waypoints))
        self.waypoint_index = 0

        self.speed = 60
        self.state = "patrol"
        self.move_timer = random.uniform(5, 10)
        self.aggression = 1.0
        self.attack_timer = 0.0
        self.transitioning = False
        self.transition_target = None
        self.transition_progress = 0.0
        self.transition_duration = 0.0

        self.route = route if route else []
        self.visible = True
        self.images = {}

    # ----------------------------------------------------

    def update(self, dt):
        power = self.game.get_power()

        self.aggression = min(self.aggression + dt * 0.02, 3.0)

        # handle transition movement
        if self.transitioning:
            self.transition_progress += dt / max(self.transition_duration, 0.01)
            if self.transition_progress >= 1.0:
                self._finish_transition(power)
            return

        self.move_timer -= dt

        if self.state == "patrol":
            self.patrol(dt)
            if self.move_timer <= 0:
                self.try_move(power)
                self.move_timer = random.uniform(5 / self.aggression, 10 / self.aggression)

        elif self.state == "attack":
            self.attack_timer += dt
            if self.attack_timer > 3.0:
                self.state = "jumpscare"

    # ----------------------------------------------------

    def patrol(self, dt):
        room = self.game.rooms[self.current_room]
        target = room.waypoints[self.waypoint_index]

        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        dist = (dx*dx + dy*dy)**0.5

        if dist < 4:
            self.waypoint_index = (self.waypoint_index + 1) % len(room.waypoints)
            return

        vx = (dx / dist) * self.speed
        vy = (dy / dist) * self.speed

        self.pos[0] += vx * dt
        self.pos[1] += vy * dt

    # ----------------------------------------------------

    def try_move(self, power):
        """Follow the route with transitions."""
        if not self.route:
            return

        if not hasattr(self, "route_index"):
            self.route_index = 0

        # sync with route
        if self.current_room != self.route[self.route_index]:
            if self.current_room in self.route:
                self.route_index = self.route.index(self.current_room)
            else:
                self.route_index = 0
                self.current_room = self.route[0]

        # next target
        next_room = (
            self.route[self.route_index + 1]
            if self.route_index < len(self.route) - 1
            else self.route[0]
        )

        if self.transitioning:
            return

        # office special case
        if self.current_room == "Hall" and next_room == "Office":
            if not self.game.is_door_closed_between("Hall", "Office"):
                self._start_transition("Office")
                self.state = "attack"
            return

        # door block
        if self.game.is_door_closed_between(self.current_room, next_room):
            return

        # start transition
        self._start_transition(next_room)

        self.route_index = (self.route_index + 1) % len(self.route)

    # ----------------------------------------------------

    def _start_transition(self, target):
        self.transitioning = True
        self.transition_target = target
        self.transition_progress = 0
        self.transition_duration = random.uniform(2.0, 6.0) / max(self.aggression, 0.1)

    def _finish_transition(self, power):
        self.transitioning = False
        self.current_room = self.transition_target

        room = self.game.rooms[self.current_room]
        self.pos = list(random.choice(room.waypoints))

        if (
            self.current_room == self.game.player_room
            and (not self.game.is_door_closed_between("Hall", "Office") or power <= 0)
        ):
            self.state = "attack"
            self.attack_timer = 0.0
        else:
            self.state = "patrol"

    # ----------------------------------------------------

    def get_room_image(self):
        if self.current_room in self.images:
            return self.images[self.current_room]

        # load on demand
        path = f"../assets/animatronics/{self.name}/{self.current_room}.png"

        try:
            img = pygame.image.load(path).convert_alpha()
        except:
            img = self.game.anim_img

        img = pygame.transform.scale(img, (320, 240))
        self.images[self.current_room] = img
        return img

    # ----------------------------------------------------

    def draw_on_surface(self, surface):
        img = self.get_room_image()
        x = int(self.pos[0]) - img.get_width() // 2
        y = int(self.pos[1]) - img.get_height() // 2
        surface.blit(img, (x, y))


# ----------------------------------------------------
# Export default movement paths (optional)
# ----------------------------------------------------

ANIMATRONIC_PATHS = {
    "Rainer": ["Stage", "Hall", "Backroom", "Hall", "HallCorner", "Office"],
    "Fliege": ["Kitchen", "Backroom", "Hall", "HallCorner", "Office"]
}
