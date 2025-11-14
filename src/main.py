import pygame
import sys
import random
from dataclasses import dataclass
from typing import List, Tuple
import os
from moviepy.editor import VideoFileClip
from PIL import Image

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- Compatibility patch for Pillow >= 10 ---
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

click_once = False

pygame.init()
pygame.mixer.init()
WIDTH, HEIGHT = 1920, 1080
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Fünf Nächte beim Drachen")

last_mouse_pressed = False

CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont("Arial", 20)

# ----- Configuration -----
ROOM_SIZE = (320, 240)  # size of each camera viewport for display thumbnails
PLAYER_ROOM = "Office"  # the room that is the player's location

# Load placeholder assets (replace these with your sprites)
def load_placeholder_surface(text, size=(320, 240)):
    surf = pygame.Surface(size)
    surf.fill((30, 30, 30))
    txt = FONT.render(text, True, (230,230,230))
    surf.blit(txt, (10,10))
    return surf

jumpscare_active = False
CAMERA_IMG = load_placeholder_surface("Camera View")
ANIM_IMG = pygame.Surface((48, 48))
ANIM_IMG.fill((200, 50, 50))
JUMPSCARE_IMG = pygame.Surface((WIDTH, HEIGHT))
JUMPSCARE_IMG.fill((255,0,0))
JUMP_TEXT = FONT.render("JUMPSCARE!", True, (255,255,255))
JUMPSCARE_IMG.blit(JUMP_TEXT, (WIDTH//2 - 60, HEIGHT//2 - 10))
# --- Static animation state ---
STATIC_FRAMES = []
STATIC_FRAME_INDEX = 0
STATIC_FRAME_TIMER = 0.0
office_locked = False  # prevents others from entering after jumpscare starts
REC_FONT = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
rec_flash_timer = 0.0
rec_visible = True


# --- Flicker effect control ---
static_alpha = 0         # current opacity
static_target_alpha = 0  # desired opacity (e.g. 100 when active)
static_fade_speed = 300  # how fast the fade occurs (alpha per second)

def create_scanline_surface(width, height):
    surf = pygame.Surface((width, height)).convert()
    surf.fill((0, 0, 0))
    for y in range(0, height, 4):
        pygame.draw.line(surf, (10, 10, 10), (0, y), (width, y), 2)
    surf.set_alpha(40)
    return surf

SCANLINE_OVERLAY = create_scanline_surface(WIDTH, HEIGHT)


# --- Office sprites ---
OFFICE_BASE = pygame.image.load("../assets/rooms/Office/office_base.png").convert()
OFFICE_BASE = pygame.transform.smoothscale(OFFICE_BASE, (1920, 1080))

DOOR_CLOSED_IMG = pygame.image.load("../assets/rooms/Office/door_left_closed.png").convert_alpha()
DOOR_CLOSED_IMG = pygame.transform.smoothscale(DOOR_CLOSED_IMG, (1920, 1080))


# --- Load pre-rendered static animation ---
def load_gif_frames(path):
    """Load all frames from a GIF and return a list of Pygame surfaces with alpha."""
    frames = []
    try:
        gif = Image.open(path)
    except Exception as e:
        print(f"[ERROR] Cannot load GIF {path}: {e}")
        return frames

    for frame_index in range(getattr(gif, "n_frames", 1)):
        gif.seek(frame_index)
        # Convert to RGBA so we can add transparency
        frame = gif.convert("RGBA")
        mode = frame.mode
        size = frame.size
        data = frame.tobytes()
        surface = pygame.image.fromstring(data, size, mode).convert_alpha()
        frames.append(surface)
    print(f"[INFO] Loaded {len(frames)} static frames with alpha.")
    return frames


# Optional: load sounds (place in assets/sounds)
def safe_load_sound(path):
    if not os.path.exists(path):
        print(f"[WARNING] Sound file not found: {path}")
        return None
    try:
        sound = pygame.mixer.Sound(path)
        print(f"[OK] Loaded sound: {path}")
        return sound
    except Exception as e:
        print(f"[ERROR] Could not load sound: {path} ({e})")
        return None

# Load sounds
JUMPSCARE_SOUND = safe_load_sound("../assets/sounds/jumpscare.wav")
BACKGROUND_LOOP = safe_load_sound("../assets/sounds/background_loop.wav")
CAMERA_SWITCH_SOUND = safe_load_sound("../assets/sounds/cam_select.wav")
DOOR_CLOSE_SOUND = safe_load_sound("../assets/sounds/door_close.wav")
DOOR_OPEN_SOUND = safe_load_sound("../assets/sounds/door_open.wav")

# Jumpscare video
RAINER_JUMPSCARE_VIDEO_PATH = "../assets/jumpscares/rainer_jumpscare.mp4"


# --- Ambient sounds ---
AMBIENT_SOUNDS = []
for i in range(1, 10):  # assuming ambient1.wav ... ambient9.wav
    path = f"../assets/sounds/schnaufer_winkler{i}.wav"
    sound = safe_load_sound(path)
    if sound:
        AMBIENT_SOUNDS.append(sound)

if AMBIENT_SOUNDS:
    print(f"[INFO] Loaded {len(AMBIENT_SOUNDS)} ambient sound(s).")


STATIC_FRAMES = load_gif_frames("../assets/effects/static.gif")
STATIC_FRAME_INDEX = 0
STATIC_FRAME_TIMER = 0.0


# ----- Map / Rooms / Waypoints -----
@dataclass
class Room:
    name: str
    view_surface: pygame.Surface
    waypoints: List[Tuple[int, int]]  # coordinates local to room


def safe_load_image(path, size=(320, 240)):
    """Safely load a PNG or return a placeholder if missing."""
    if not os.path.exists(path):
        print(f"[WARN] Missing room image: {path}")
        return load_placeholder_surface(os.path.basename(path), size)
    try:
        img = pygame.image.load(path).convert()
        return pygame.transform.smoothscale(img, size)
    except Exception as e:
        print(f"[ERROR] Could not load {path}: {e}")
        return load_placeholder_surface("Error", size)


# ----- Room Definitions -----
ROOMS = {
    "Stage": Room(
        "Stage",
        safe_load_image("../assets/rooms/stage.png", (320, 240)),
        waypoints=[(160, 30), (160, 210)]
    ),
    "Hall": Room(
        "Hall",
        safe_load_image("../assets/rooms/hall.png", (320, 240)),
        waypoints=[(50, 50), (250, 180)]
    ),
    "Kitchen": Room(
        "Kitchen",
        safe_load_image("../assets/rooms/kitchen.png", (320, 240)),
        waypoints=[(30, 30), (280, 200)]
    ),
    "HallCorner": Room(
        "HallCorner",
        safe_load_image("../assets/rooms/hallcorner.png", (320, 240)),
        waypoints=[(60, 60), (260, 180)]
    ),
    "Backroom": Room(
        "Backroom",
        safe_load_image("../assets/rooms/backroom.png", (320, 240)),
        waypoints=[(100, 100), (220, 160)]
    ),
    "Office": Room(
        "Office",
        safe_load_image("../assets/rooms/office.png", (320, 240)),
        waypoints=[(0, 0)]
    ),
}



# ----- Room Connections -----
ROOM_CONNECTIONS = {
    "Stage": ["Hall"],
    "Hall": ["Stage", "Backroom", "HallCorner"],
    "Kitchen": ["Backroom"],
    "HallCorner": ["Hall", "Office"],
    "Backroom": ["Hall", "HallCorner"],
    "Office": ["Hall", "HallCorner"]
} 



# --- Fixed Animatronic Routes (like FNaF paths) ---
ANIMATRONIC_PATHS = {
    "Rainer": ["Stage", "Hall", "Backroom", "Hall", "HallCorner", "Office"],
    "Fliege": ["Kitchen", "Backroom", "Hall", "HallCorner", "Office"]
}


# ----- Door & Power System -----
DOORS = {
    ("Hall", "Office"): {"closed": False}
}

# ----- Camera Order -----
CAMERA_ORDER = ["Stage", "Kitchen", "Hall", "Backroom", "HallCorner", "Office"]

# FNaF-style short labels for each camera
CAM_LABELS = {
    "Stage": "1A",
    "Hall": "2",
    "Kitchen": "1B",
    "Backroom": "3",
    "HallCorner": "4",
    "Office": "—"  # optional (usually not a numbered cam)
}



# Optional: if you don’t want to access the Office via camera view:
VIEWABLE_CAMERAS = [r for r in CAMERA_ORDER if r != "Office"]




MAX_POWER = 100.0
power = MAX_POWER
POWER_DRAIN_IDLE = 0.005      # per frame when doing nothing
POWER_DRAIN_CAMERA = 0.015    # per frame when viewing cameras
POWER_DRAIN_DOOR = 0.03       # per frame per closed door

for name, route in ANIMATRONIC_PATHS.items():
    base_dir = f"../assets/animatronics/{name}/"
    missing = [room for room in route if not os.path.exists(f"{base_dir}{room}.png")]
    if missing:
        print(f"[DEBUG] Missing PNGs for {name}: {missing}")



class Animatronic:
    def __init__(self, name, start_room, route=None):
        self.name = name
        self.current_room = start_room
        self.pos = list(random.choice(ROOMS[start_room].waypoints))
        self.waypoint_index = 0

        # movement / timing
        self.speed = 60  # not used for teleport movement but kept for future
        self.state = "patrol"
        self.move_timer = random.uniform(5.0, 10.0)
        self.aggression = 1.0
        self.attack_timer = 0.0
        self.target_room = None
        self.visible = True
        self.images = self.load_room_images(name)

        # smooth transition state (prevents instant double-moves)
        self.transitioning = False
        self.transition_target = None
        self.transition_progress = 0.0
        self.transition_duration = 0.0

        # Path/route for this anim; prefer explicit route arg, fallback to global dict
        if route:
            self.route = route
        else:
            self.route = ANIMATRONIC_PATHS.get(self.name, [])

        # ensure start room is valid for the route (if route exists)
        if self.route and self.current_room not in self.route:
            # place them at the route start to avoid desyncs
            self.current_room = self.route[0]
            self.pos = list(random.choice(ROOMS[self.current_room].waypoints))


    def load_room_images(self, name):
        """Load per-room images for this animatronic."""
        images = {}
        base_path = f"../assets/animatronics/{name}/"
        for room in CAMERA_ORDER:
            path = os.path.join(base_path, f"{room.lower()}.png")
            if os.path.exists(path):
                images[room] = pygame.image.load(path).convert_alpha()
                print(f"[OK] Loaded {name} image for {room}")
            else:
                print(f"[WARN] Missing {name} image for {room}")
        return images

    def get_room_image(self):
        """Return the current room’s image, or a fallback."""
        return self.images.get(self.current_room, ANIM_IMG)


    def update(self, dt):
        """Update AI behavior: timed movement, state logic, aggression scaling."""
        # Increase aggression slowly as the night goes on
        self.aggression = min(self.aggression + dt * 0.02, 3.0)

        # If currently transitioning between rooms, progress the transition
        if self.transitioning:
            # advance normalized progress (0..1)
            if self.transition_duration <= 0:
                self.transition_duration = 1.0
            self.transition_progress += dt / self.transition_duration

            if self.transition_progress >= 1.0:
                # finish transition
                self.transitioning = False
                arrived = self.transition_target
                self.transition_target = None
                self.transition_progress = 0.0
                self.transition_duration = 0.0

                # set new room & randomize waypoint inside that room
                self.current_room = arrived
                if ROOMS.get(self.current_room) and ROOMS[self.current_room].waypoints:
                    self.pos = list(random.choice(ROOMS[self.current_room].waypoints))
                else:
                    # fallback safe pos
                    self.pos = [0, 0]

                # if arrived at office, check attack conditions
                if self.current_room == PLAYER_ROOM:
                    if not is_door_closed_between("Hall", "Office") or power <= 0:
                        self.state = "attack"
                        self.attack_timer = 0.0
                    else:
                        self.state = "patrol"
                else:
                    self.state = "patrol"

            # while transitioning, skip the rest of update
            return

        # Not transitioning: normal timers and decisions
        self.move_timer -= dt

        if self.state == "patrol":
            # optional local patrol inside the room (waypoints) - keep sprite moving
            self.patrol(dt)
            if self.move_timer <= 0:
                self.try_move()
                # reset timer (shorter as aggression increases)
                self.move_timer = random.uniform(5.0 / max(self.aggression, 0.1),
                                                 10.0 / max(self.aggression, 0.1))

        elif self.state == "attack":
            self.attack_timer += dt
            if self.attack_timer > 3.0:
                self.state = "jumpscare"

    def patrol(self, dt):
        """Move between waypoints smoothly; reset safely if index out of range."""
        room = ROOMS.get(self.current_room)
        if not room or not room.waypoints:
            # Fallback: stay still if no valid waypoints
            self.pos = [0, 0]
            self.waypoint_index = 0
            return

        # Ensure waypoint index is always valid
        if self.waypoint_index >= len(room.waypoints):
            self.waypoint_index = 0

        target = room.waypoints[self.waypoint_index]
        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        dist = (dx*dx + dy*dy) ** 0.5

        if dist < 4:
            # move to next waypoint safely
            self.waypoint_index = (self.waypoint_index + 1) % len(room.waypoints)
            return

        # move toward current target
        vx = (dx / dist) * self.speed
        vy = (dy / dist) * self.speed
        self.pos[0] += vx * dt
        self.pos[1] += vy * dt


    def try_move(self):
        """Follow a defined route with smooth transitions and random timing."""
        if not self.route:
            return

        # Initialize current route index if not set
        if not hasattr(self, "route_index"):
            self.route_index = 0

        # Safety: if the current room mismatches route position, resync
        if self.current_room != self.route[self.route_index]:
            if self.current_room in self.route:
                self.route_index = self.route.index(self.current_room)
            else:
                self.route_index = 0
                self.current_room = self.route[0]

        # Determine next room
        if self.route_index < len(self.route) - 1:
            next_room = self.route[self.route_index + 1]
        else:
            # route finished — loop back to start
            next_room = self.route[0]

        # Don’t start a new transition if one is active
        if getattr(self, "transitioning", False):
            return

        # Random movement chance (depends on aggression)
        move_chance = 0.25 * self.aggression
        if random.random() < move_chance:
            # If moving from Hall to Office — special case
            if self.current_room == "Hall" and next_room == "Office":
                if not is_door_closed_between("Hall", "Office"):
                    print(f"[AI] {self.name} entering Office — attack imminent!")
                    self.move_to_room("Office")
                    self.state = "attack"
                else:
                    print(f"[AI] {self.name} is blocked by closed door at Hall → Office.")
                return

            # Prevent blocked transitions
            if is_door_closed_between(self.current_room, next_room):
                print(f"[AI] {self.name} blocked between {self.current_room} and {next_room}")
                return

            # Start transition
            self.transitioning = True
            self.transition_target = next_room
            self.transition_progress = 0.0
            self.transition_duration = random.uniform(2.0, 6.0) / max(self.aggression, 0.1)

            # Advance the route index for next time
            self.route_index = (self.route_index + 1) % len(self.route)

            print(f"[AI] {self.name} starts moving {self.current_room} → {next_room} (dur {self.transition_duration:.2f}s)")



    def move_to_room(self, room_name):
        """Legacy teleport helper (keeps compatibility); prefer transitions above."""
        global office_locked

        # Check valid connection
        if room_name not in ROOM_CONNECTIONS.get(self.current_room, []):
            return

        # Prevent entering the office if a jumpscare already started
        if office_locked and room_name == "Office":
            return

        # Normal door blocking
        if is_door_closed_between(self.current_room, room_name):
            return

        # Move to the new room
        self.current_room = room_name
        if ROOMS.get(room_name) and ROOMS[room_name].waypoints:
            self.pos = list(random.choice(ROOMS[room_name].waypoints))
        self.waypoint_index = 0

        # Attack logic
        if room_name == PLAYER_ROOM:
            if not is_door_closed_between("Hall", "Office") or power <= 0:
                self.state = "attack"
                self.attack_timer = 0.0
        else:
            self.state = "patrol"


    def get_room_image(self):
        """Return the animatronic's image for the current room (if available)."""
        import os

        # Initialize cache once
        if not hasattr(self, "_room_images"):
            self._room_images = {}

        # Return from cache if available
        if self.current_room in self._room_images:
            return self._room_images[self.current_room]

        # Build normalized path: FNBD/assets/animatronics/Rainer/Backroom.png
        folder = os.path.join("..", "assets", "animatronics", self.name)
        filename = f"{self.current_room}.png"
        path = os.path.join(folder, filename)
        path = path.replace("\\", "/")  # normalize for pygame compatibility

        try:
            # Load and cache image
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (320, 240))  # match camera viewport
            self._room_images[self.current_room] = img
            print(f"[OK] Loaded {self.name} image for {self.current_room}")
            return img

        except Exception as e:
            # Fallback placeholder (so missing images won't crash)
            print(f"[WARN] Missing or failed to load {path}: {e}")
            placeholder = pygame.Surface((320, 240), pygame.SRCALPHA)
            placeholder.fill((255, 0, 0, 80))
            pygame.draw.rect(placeholder, (255, 50, 50), placeholder.get_rect(), 3)
            self._room_images[self.current_room] = placeholder
            return placeholder




    def draw_on_surface(self, surf):
        surf.blit(ANIM_IMG, (int(self.pos[0]) - 24, int(self.pos[1]) - 24))

# create animatronics
animatronics = [
    Animatronic("Rainer", "Stage"),
    Animatronic("Fliege", "Hall")
]


# ----- Game state -----
camera_index = 0   # which camera the player is viewing
game_over = False
jumpscare_time = 0.0
NIGHT_LENGTH = 90  # seconds for the "night"
night_timer = NIGHT_LENGTH
start_ticks = pygame.time.get_ticks()

# ----- Helper UI -----
def draw_ui():
    """Draw FNaF-style status UI (night timer, door status, power)."""
    try:
        ui_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 26)
    except:
        ui_font = FONT  # fallback if pixel font missing

    # --- Background translucent panel ---
    panel = pygame.Surface((280, 100), pygame.SRCALPHA)
    panel.fill((10, 10, 10, 120))
    SCREEN.blit(panel, (WIDTH - 300, 15))

    info_x = WIDTH - 280
    info_y = 25

    # --- Night timer ---
    timer_text = ui_font.render(f"TIME LEFT: {int(night_timer)}s", True, (220, 220, 220))
    SCREEN.blit(timer_text, (info_x, info_y))
    info_y += 28

    # --- Door status ---
    door_text = "CLOSED" if is_door_closed_between("Hall", "Office") else "OPEN"
    door_color = (255, 60, 60) if door_text == "CLOSED" else (100, 255, 100)
    door_label = ui_font.render(f"DOOR: {door_text}", True, door_color)
    SCREEN.blit(door_label, (info_x, info_y))
    info_y += 28

    # --- Power ---
    if power > 20:
        power_color = (220, 220, 220)
    else:
        power_color = (255, 50, 50)
    power_label = ui_font.render(f"POWER: {power:.0f}%", True, power_color)
    SCREEN.blit(power_label, (info_x, info_y))

    # --- Subtle glow/flicker effect (optional aesthetic) ---
    if random.random() < 0.02:
        flicker_overlay = pygame.Surface((280, 100), pygame.SRCALPHA)
        flicker_overlay.fill((255, 255, 255, random.randint(10, 20)))
        SCREEN.blit(flicker_overlay, (WIDTH - 300, 15))




def draw_camera_hover_bar(screen, mouse_y, dt):
    global camera_active, camera_bar_y, camera_bar_target_y
    global last_hover_state, cam_toggle_cooldown, static_target_alpha

    bar_height = 80
    hover_zone = HEIGHT - 120        # The hover area
    toggle_cooldown_time = 0.4       # Prevent double triggers

    # initialize missing globals
    if "last_hover_state" not in globals():
        last_hover_state = False
    if "cam_toggle_cooldown" not in globals():
        cam_toggle_cooldown = 0.0

    # update cooldown
    if cam_toggle_cooldown > 0:
        cam_toggle_cooldown -= dt

    # detect hover
    hovering = mouse_y >= hover_zone

    # --- FNaF toggle logic ---
    if hovering and not last_hover_state and cam_toggle_cooldown <= 0:
        # mouse ENTERED the bar → toggle camera
        camera_active = not camera_active
        cam_toggle_cooldown = toggle_cooldown_time

        if camera_active:
            static_target_alpha = 120
            print("[CAM] Monitor OPENED")
        else:
            static_target_alpha = 0
            print("[CAM] Monitor CLOSED")

    # update last state
    last_hover_state = hovering

    # slide animation
    camera_bar_target_y = HEIGHT - (bar_height if camera_active else 20)
    camera_bar_y += (camera_bar_target_y - camera_bar_y) * min(dt * 10, 1)

    # draw bar background
    bar_rect = pygame.Rect(0, camera_bar_y, WIDTH, bar_height)
    pygame.draw.rect(screen, (25, 25, 25), bar_rect)

    # draw arrow
    arrow_y = camera_bar_y + 25
    arrow_color = (255, 80, 80) if camera_active else (220, 220, 220)
    pygame.draw.polygon(screen, arrow_color, [
        (WIDTH // 2 - 35, arrow_y + 20),
        (WIDTH // 2 + 35, arrow_y + 20),
        (WIDTH // 2, arrow_y)
    ])

    # glow on hover
    if hovering:
        glow = pygame.Surface((WIDTH, bar_height), pygame.SRCALPHA)
        glow.fill((255, 255, 255, 20))
        screen.blit(glow, (0, camera_bar_y))


def draw_camera_side_panel(surface, active):
    global CAM_BUTTON_RECTS

    CAM_BUTTON_RECTS = []   # <-- reset every frame

    if not active:
        return

    panel_width = 180
    panel_x = WIDTH - panel_width
    panel_y = 120
    button_height = 70
    spacing = 10

    # Panel background
    panel = pygame.Surface((panel_width, HEIGHT - panel_y - 50), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 80))
    surface.blit(panel, (panel_x, panel_y))

    # Title
    title_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 32)
    title = title_font.render("CAMERAS", True, (200, 200, 200))
    surface.blit(title, (panel_x + 25, panel_y - 50))

    btn_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 36)

    mx, my = pygame.mouse.get_pos()

    # Create & draw camera buttons
    for i, cam_name in enumerate(VIEWABLE_CAMERAS[:5]):
        y = panel_y + i * (button_height + spacing)

        rect = pygame.Rect(panel_x + 20, y, panel_width - 40, button_height)

        hovered = rect.collidepoint(mx, my)
        active_cam = (CAMERA_ORDER[camera_index] == cam_name)

        # Colors
        if active_cam:
            color = (180, 40, 40)
        elif hovered:
            color = (150, 150, 150)
        else:
            color = (90, 90, 90)

        pygame.draw.rect(surface, color, rect, border_radius=8)
        pygame.draw.rect(surface, (20, 20, 20), rect, 3, border_radius=8)

        label = btn_font.render(str(i + 1), True, (250, 250, 250))
        surface.blit(label, (
            rect.centerx - label.get_width() // 2,
            rect.centery - label.get_height() // 2
        ))

        CAM_BUTTON_RECTS.append((rect, cam_name))


def mouse_in_camera_ui(mx, my):
    """Returns True if mouse is over any camera UI that should NOT close the cams."""
    # Bottom hover bar
    if my >= HEIGHT - 80:
        return True

    # Right-side camera panel
    panel_width = 180
    panel_x = WIDTH - panel_width
    panel_y = 120
    panel_height = HEIGHT - panel_y - 50

    if panel_x <= mx <= WIDTH and panel_y <= my <= panel_y + panel_height:
        return True

    return False


def handle_camera_switch(key):
    global camera_index, flicker_timer, camera_booting, camera_boot_timer, current_camera_name

    # Trigger camera boot-up sequence
    camera_booting = True
    camera_boot_timer = 0.8  # seconds of static before feed appears

    # Map numeric keys (1..N) to indices in VIEWABLE_CAMERAS
    key_map = {
        pygame.K_1: 0,
        pygame.K_2: 1,
        pygame.K_3: 2,
        pygame.K_4: 3,
        pygame.K_5: 4,
        pygame.K_6: 5,
        pygame.K_7: 6,  # keep if you later add more
        pygame.K_8: 7,
    }

    if key in key_map:
        view_idx = key_map[key]
        if view_idx < len(VIEWABLE_CAMERAS):
            # The 'camera_index' in your rendering code expects an index into CAMERA_ORDER
            # Find the actual index inside CAMERA_ORDER for the selected viewable camera name:
            selected_name = VIEWABLE_CAMERAS[view_idx]
            camera_index = CAMERA_ORDER.index(selected_name)

            flicker_timer = 0.3  # short flicker when switching cams

            if CAMERA_SWITCH_SOUND:
                CAMERA_SWITCH_SOUND.set_volume(0.3)
                CAMERA_SWITCH_SOUND.play()

            # Display a human label for overlay (e.g., "1: Hall" or just "1")
            current_camera_name = f"{view_idx+1}: {selected_name}"
            print(f"[DEBUG] Switched view key {view_idx+1} -> camera_index {camera_index} ({selected_name})")


def toggle_door_between(room_a, room_b):
    """Toggle the door state if a door exists between two rooms."""
    key = (room_a, room_b) if (room_a, room_b) in DOORS else (room_b, room_a)
    if key in DOORS:
        DOORS[key]["closed"] = not DOORS[key]["closed"]

def is_door_closed_between(room_a, room_b):
    key = (room_a, room_b) if (room_a, room_b) in DOORS else (room_b, room_a)
    return DOORS.get(key, {}).get("closed", False)

def drain_power(dt, camera_on):
    """Return new power value after drain."""
    total_drain = POWER_DRAIN_IDLE
    if camera_on:
        total_drain += POWER_DRAIN_CAMERA
    # add drain for each closed door
    for door in DOORS.values():
        if door["closed"]:
            total_drain += POWER_DRAIN_DOOR
    return max(power - total_drain * 60 * dt, 0)


def main_menu():
    """Display the main menu with Start, Controls, and Quit buttons, including static background."""
    # --- Load background music ---
    menu_music = safe_load_sound("../assets/sounds/menu_theme.wav")
    if menu_music:
        menu_music.set_volume(0.5)
        menu_music.play(-1)

    title_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 64)
    button_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)

    # Ensure STATIC_FRAMES exist and are scaled to screen
    if not STATIC_FRAMES:
        # fallback single dark static surface
        local_static = [pygame.Surface((WIDTH, HEIGHT))]
        local_static[0].fill((10, 10, 10))
    else:
        # Use a local reference (avoid stomping global reference), ensure scaled
        local_static = []
        for f in STATIC_FRAMES:
            try:
                local_static.append(pygame.transform.scale(f, (WIDTH, HEIGHT)).convert_alpha())
            except Exception:
                # in case frame isn't suitable for scaling
                local_static.append(pygame.Surface((WIDTH, HEIGHT)).convert())

    # --- Animation state for menu static ---
    frame_index = 0
    frame_timer = 0.0
    frame_delay = 0.04  # seconds between static frames

    # --- Rainer flash (kept minimal) ---
    try:
        rainer_img = pygame.image.load("../assets/images/rainer_flash.png").convert_alpha()
        rainer_img = pygame.transform.scale(rainer_img, (WIDTH, HEIGHT))
    except Exception:
        rainer_img = None
    rainer_timer = random.uniform(5.0, 12.0)
    rainer_alpha = 0

    # --- Buttons ---
    start_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2, 300, 80)
    controls_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 120, 300, 80)
    quit_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 240, 300, 80)

    in_menu = True
    show_controls = False

    def draw_creepy_button(rect, text, hover):
        base_color = (40, 30, 30)
        hover_color = (70, 20, 20) if hover else base_color
        flicker_strength = random.randint(-10, 10)
        color = tuple(max(0, min(255, c + flicker_strength)) for c in hover_color)
        offset_x = random.randint(-1, 1) if hover else 0
        offset_y = random.randint(-1, 1) if hover else 0

        # button rect
        pygame.draw.rect(SCREEN, color, rect, border_radius=12)

        # faint glow when hovered
        if hover:
            glow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 30, 30, 30), glow.get_rect(), border_radius=12)
            SCREEN.blit(glow, (rect.x - 5, rect.y - 5))

        label = button_font.render(text, True, (220, 220, 220))
        SCREEN.blit(label, (rect.centerx - label.get_width() // 2 + offset_x,
                            rect.centery - label.get_height() // 2 + offset_y))

    def draw_controls_screen(dt_local):
        """Draw the controls screen with the same static background (use dt_local to advance static)."""
        nonlocal frame_index, frame_timer, rainer_timer, rainer_alpha

        # Background = static animation
        # --- Static background animation ---
        frame_timer += dt
        if frame_timer >= 0.04:
            frame_timer = 0.0
            frame_index = (frame_index + 1) % len(local_static)

        bg = local_static[frame_index]
        if bg:
            static_surface = bg.copy()
            static_surface.set_alpha(50)  # 🔧 Adjust transparency (30–60 = good range)
            SCREEN.blit(static_surface, (0, 0))

        # optional dark overlay for FNaF-like depth
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(60)  # 🔧 adjust to 60–90 for darker look
        SCREEN.blit(overlay, (0, 0))


        # scanline overlay for CRT feel
        if 'SCANLINE_OVERLAY' in globals() and SCANLINE_OVERLAY:
            SCREEN.blit(SCANLINE_OVERLAY, (0, 0))


        # optional rainer flash (very subtle)
        rainer_timer -= dt_local
        if rainer_img and rainer_timer <= 0:
            rainer_alpha = 255
            rainer_timer = random.uniform(8.0, 14.0)
        if rainer_alpha > 0 and rainer_img:
            rainer_alpha = max(rainer_alpha - 700 * dt_local, 0)
            temp = rainer_img.copy()
            temp.set_alpha(int(rainer_alpha * 0.6))
            SCREEN.blit(temp, (0, 0))
            flash = pygame.Surface((WIDTH, HEIGHT))
            flash.fill((255, 255, 255))
            flash.set_alpha(int(rainer_alpha * 0.25))
            SCREEN.blit(flash, (0, 0))

        # Title & header
        if random.random() < 0.02:
            flicker_color = (random.randint(150, 255), random.randint(150, 255), random.randint(150, 255))
        else:
            flicker_color = (255, 255, 255)
        header = title_font.render("Controls & Info", True, flicker_color)
        SCREEN.blit(header, (WIDTH // 2 - header.get_width() // 2, 120))

        info_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 32)
        lines = [
            "1-6 : Switch cameras",
            "D   : Toggle office door",
            "Hover the bottom arrow : Open cameras",
            "ESC : Quit the game",
        ]
        y = 280
        for line in lines:
            txt = info_font.render(line, True, (200, 200, 200))
            SCREEN.blit(txt, (WIDTH // 2 - txt.get_width() // 2, y))
            y += 60

        # Back button
        back_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT - 200, 300, 80)
        mx, my = pygame.mouse.get_pos()
        draw_creepy_button(back_rect, "Back", back_rect.collidepoint(mx, my))
        return back_rect

    # main menu loop
    while in_menu:
        dt = CLOCK.tick(60) / 1000.0

        # advance static while menu or controls shown
        frame_timer += dt
        if frame_timer >= frame_delay:
            frame_timer = 0.0
            frame_index = (frame_index + 1) % len(local_static)

        # draw static background
        bg = local_static[frame_index]
        bg = local_static[frame_index]
        if bg:
            static_surface = bg.copy()
            static_surface.set_alpha(50)  # LOWER = more transparent (try 30–60)
            SCREEN.blit(static_surface, (0, 0))

        else:
            SCREEN.fill((0, 0, 0))

        # overlay scanlines
        if 'SCANLINE_OVERLAY' in globals() and SCANLINE_OVERLAY:
            SCREEN.blit(SCANLINE_OVERLAY, (0, 0))

        # subtle dark overlay
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(60)
        SCREEN.blit(overlay, (0, 0))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if show_controls:
                    # call draw_controls_screen to get the current back_rect and check click
                    back_rect = draw_controls_screen(dt)
                    if back_rect.collidepoint(mx, my):
                        show_controls = False
                else:
                    if start_rect.collidepoint(mx, my):
                        in_menu = False
                    elif controls_rect.collidepoint(mx, my):
                        show_controls = True
                    elif quit_rect.collidepoint(mx, my):
                        pygame.quit()
                        sys.exit()

        # draw title + buttons or controls screen
        if not show_controls:
            # title with tiny flicker/jitter
            if random.random() < 0.02:
                flicker_color = (random.randint(150, 255), random.randint(150, 255), random.randint(150, 255))
            else:
                flicker_color = (255, 255, 255)
            title = title_font.render("FIVE NIGHTS AT DRACHENSCHANZE", True, flicker_color)
            title_y_offset = random.randint(-1, 1)
            SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 3 - 50 + title_y_offset))

            # Draw buttons
            mx, my = pygame.mouse.get_pos()
            draw_creepy_button(start_rect, "Start Night", start_rect.collidepoint(mx, my))
            draw_creepy_button(controls_rect, "Controls", controls_rect.collidepoint(mx, my))
            draw_creepy_button(quit_rect, "Quit", quit_rect.collidepoint(mx, my))
        else:
            # controls screen: update static + draw controls + back button
            back_rect = draw_controls_screen(dt)

        pygame.display.flip()

    # fade out music briefly as we move into the game
    if menu_music:
        menu_music.fadeout(1500)





def show_night_intro(screen, text="Night 1", duration=3.0):
    """Displays 'Night X' text with fade in/out transition before gameplay."""
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("../assets/fonts/pixel_font.ttf", 80)
    label = font.render(text, True, (255, 255, 255))

    fade_surface = pygame.Surface((WIDTH, HEIGHT))
    fade_surface.fill((0, 0, 0))

    fade_in_time = 1.0   # seconds
    hold_time = 1.0      # seconds text stays visible
    fade_out_time = 1.0  # seconds
    total_time = fade_in_time + hold_time + fade_out_time

    timer = 0.0
    running = True

    while running:
        dt = clock.tick(60) / 1000.0
        timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # calculate fade alpha
        if timer < fade_in_time:
            alpha = int(255 - (timer / fade_in_time) * 255)
        elif timer < fade_in_time + hold_time:
            alpha = 0
        elif timer < total_time:
            alpha = int(((timer - fade_in_time - hold_time) / fade_out_time) * 255)
        else:
            running = False
            break

        # draw black background + text
        screen.fill((0, 0, 0))
        text_x = WIDTH // 2 - label.get_width() // 2
        text_y = HEIGHT // 2 - label.get_height() // 2
        screen.blit(label, (text_x, text_y))

        # fade overlay
        fade_surface.set_alpha(alpha)
        screen.blit(fade_surface, (0, 0))

        pygame.display.flip()

    # after fade, transition back to black
    screen.fill((0, 0, 0))
    pygame.display.flip()
    pygame.time.wait(500)

pygame.mixer.set_num_channels(16)
pygame.mixer.music.set_volume(1.0)


# ----- Main loop -----
def main():
    global game_over, camera_bar_y, click_once, camera_bar_target_y, jumpscare_time,night_timer, camera_index, power, cam_toggle_cooldown, camera_active, camera_button_rect, STATIC_OVERLAY, cam_show_timer, STATIC_FRAME_TIMER, STATIC_FRAME_INDEX, static_alpha, static_target_alpha, jumpscare_active, office_locked, fade, CAM_BAR_ACTIVE_COLOR, CAM_BAR_COLOR, CAM_BAR_FONT, CAM_BAR_HEIGHT, CAM_BAR_TEXT_COLOR, cam_hovered
    running = True
    last_time = pygame.time.get_ticks()
    flicker_timer = 0.0
    camera_active = False
    static_alpha = 0.0         # current transparency level
    STATIC_FRAME_INDEX = 0
    STATIC_FRAME_TIMER = 0.0
    camera_button_rect = pygame.Rect(WIDTH - 180, HEIGHT - 100, 160, 60)
    door_closed = False
    ambient_timer = random.uniform(20.0, 30.0)  # initial random delay before first ambient
    # --- Initialize animatronics (before main loop) ---
    rainer = Animatronic("Rainer", "Stage")
    fliege = Animatronic("Fliege", "Kitchen")
    animatronics = [rainer, fliege]
    camera_booting = False
    camera_boot_timer = 0.0
    cam_toggle_cooldown = 0.0
    current_camera_name = "1A"
    animatronics = [rainer, fliege]
    # --- Initialize Animatronics ---
    rainer = Animatronic("Rainer", start_room="Stage", route=ANIMATRONIC_PATHS["Rainer"])
    fliege = Animatronic("Fliege", start_room="Kitchen", route=ANIMATRONIC_PATHS["Fliege"])
    jumpscare_active = False
    animatronics = [rainer, fliege]
    office_locked = False
    animatronics = [rainer, fliege]
    # --- Camera tablet hover system ---
    CAM_BAR_HEIGHT = 60
    CAM_BAR_COLOR = (10, 10, 10)
    CAM_BAR_ACTIVE_COLOR = (30, 30, 30)
    CAM_BAR_TEXT_COLOR = (200, 255, 200)
    CAM_BAR_FONT = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
    cam_hovered = False
    camera_bar_y = HEIGHT - 20          # current Y position of the hover bar
    camera_bar_target_y = HEIGHT - 20   # target Y (moves smoothly)
    cam_show_timer = 0.0    



    def play_jumpscare_video(path):
        """Play the jumpscare video overlayed on the current game frame (greenscreen removed)."""
        from moviepy.editor import VideoFileClip
        from PIL import Image
        import numpy as np
        import pygame
        import tempfile
        import os

        if not hasattr(Image, "ANTIALIAS"):
            Image.ANTIALIAS = Image.LANCZOS

        clip = VideoFileClip(path, audio=True)

        # --- Chroma key function: produce alpha transparency instead of black ---
        def chroma_key_rgba(frame):
            """Return RGBA frame with transparency where green was detected."""
            frame = np.copy(frame).astype(np.uint8)
            r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
            mask = (g > 1.55 * r) & (g > 1.55 * b) & (g > 40)
            alpha = np.where(mask, 0, 255).astype(np.uint8)
            rgba = np.dstack((r, g, b, alpha))
            return rgba

        clip = clip.fl_image(chroma_key_rgba).resize((WIDTH, HEIGHT))

        # --- Extract and play sound separately ---
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name
            clip.audio.write_audiofile(audio_path, verbose=False, logger=None)

        jumpscare_sound = pygame.mixer.Sound(audio_path)
        jumpscare_sound.set_volume(3.0)
        jumpscare_sound.play()

        # --- Manual Pygame playback ---
        clock = pygame.time.Clock()
        for frame in clip.iter_frames(fps=30, dtype="uint8"):
            if frame.shape[2] == 3:
                # fallback if no alpha
                surf = pygame.image.frombuffer(frame.tobytes(), clip.size, "RGB").convert()
            else:
                surf = pygame.image.frombuffer(frame.tobytes(), clip.size, "RGBA").convert_alpha()

            # --- Redraw last game frame (Office background) first ---
            office_surface = OFFICE_BASE.copy()
            if is_door_closed_between("Hall", "Office"):
                office_surface.blit(DOOR_CLOSED_IMG, (0, 0))
            office_scaled = pygame.transform.scale(office_surface, (WIDTH, HEIGHT))
            SCREEN.blit(office_scaled, (0, 0))

            # --- Then overlay the jumpscare frame with alpha ---
            SCREEN.blit(surf, (0, 0))
            pygame.display.flip()
            clock.tick(30)

        clip.close()

        # Clean up temp file
        try:
            os.remove(audio_path)
        except:
            pass


    # --- Initialize Animatronics ---
    rainer = Animatronic("Rainer", "Stage")
    fliege = Animatronic("Fliege", "Kitchen")

    # Optional: slight speed variation
    rainer.speed = random.uniform(45, 65)
    fliege.speed = random.uniform(55, 70)

    # Register them globally
    ANIMATRONICS = [rainer, fliege]


    # --- Start background ambiance when the night begins (with fade-in) ---
    if BACKGROUND_LOOP:
        BACKGROUND_LOOP.set_volume(0.0)
        BACKGROUND_LOOP.play(-1)
        background_fade_timer = 0.0
        background_target_volume = 0.15  # final volume
    else:
        background_fade_timer = None


    while running:
        now = pygame.time.get_ticks()
        dt = (now - last_time) / 1000.0
        last_time = now
        CLOCK.tick(60)

        # --- Gradually fade in background ambience ---
        if BACKGROUND_LOOP and background_fade_timer is not None:
            background_fade_timer += dt
            fade_duration = 5.0  # seconds for full fade-in
            current_volume = min(background_target_volume * (background_fade_timer / fade_duration),
                                background_target_volume)
            BACKGROUND_LOOP.set_volume(current_volume)
            if current_volume >= background_target_volume:
                background_fade_timer = None  # stop updating after fade-in completes


        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_once = True

            elif event.type == pygame.KEYDOWN:
                handle_camera_switch(event.key)

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_d:
                    toggle_door_between("Office", "Hall")
                    door_closed = not door_closed
                    if door_closed:
                        print("Door Closed")
                        if DOOR_CLOSE_SOUND:
                            DOOR_CLOSE_SOUND.play()
                    else:
                        print("Door Open")
                        if DOOR_OPEN_SOUND:
                            DOOR_OPEN_SOUND.play()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                if camera_active:
                    print("Camera system activated")
                    static_target_alpha = 120  # flash brighter when camera opens
                else:
                    print("Camera closed")
                    static_target_alpha = 0    # fade out when camera closes

        # --- Ambient noise system ---
       
        ambient_timer -= dt
        first_ambient = True

        # Inside the loop:
        ambient_timer -= dt
        if ambient_timer <= 0 and AMBIENT_SOUNDS:
            sound = random.choice(AMBIENT_SOUNDS)
            channel = sound.play()
            if channel:
                left = random.uniform(0.2, 1.0)
                right = random.uniform(0.2, 1.0)
                channel.set_volume(left, right)

            if first_ambient:
                ambient_timer = random.uniform(15.0, 25.0)
                first_ambient = False
            else:
                ambient_timer = random.uniform(20.0, 30.0)


        #drain power each frame
        camera_on = camera_active  # using camera drains more
        power = drain_power(dt, camera_on)

        if power <= 0:
            for door in DOORS.values():
                door["closed"] = False


        # --- Skip updates if player is already dead or jumpscare is active ---
        if game_over or jumpscare_active:
            continue  # freeze all updates this frame

        # --- Normal gameplay updates ---
        # update night timer
        night_timer -= dt
        if night_timer <= 0:
            # survive the night!
            print("You survived the night!")
            running = False

        # update animatronics
        for a in animatronics:
            a.update(dt)

            # Trigger jumpscare if an anim reached the Office and is in jumpscare state
            if not jumpscare_active and a.current_room == PLAYER_ROOM and a.state == "jumpscare":
                print(f"[AI] {a.name} reached the Office! Triggering jumpscare...")

                # --- Prevent duplicate triggers ---
                jumpscare_active = True
                office_locked = True

                # Stop background ambience
                if BACKGROUND_LOOP:
                    BACKGROUND_LOOP.fadeout(1000)

                # Play the appropriate jumpscare
                if a.name == "Rainer":
                    play_jumpscare_video(RAINER_JUMPSCARE_VIDEO_PATH)
                elif a.name == "Fliege":
                    play_jumpscare_video(RAINER_JUMPSCARE_VIDEO_PATH)  # placeholder for Fliege

                # --- Fade to black AFTER jumpscare video ---
                fade_surface = pygame.Surface((WIDTH, HEIGHT))
                fade_surface.fill((0, 0, 0))
                for alpha in range(0, 255, 8):
                    fade_surface.set_alpha(alpha)
                    SCREEN.blit(fade_surface, (0, 0))
                    pygame.display.flip()
                    pygame.time.wait(20)

                print("GAME OVER - Player jumpscared.")
                game_over = True

                # small delay for final sound tail
                pygame.time.wait(1000)

                running = False
                break

        # --- Smooth fade for static overlay ---
        if static_alpha < static_target_alpha:
            static_alpha = min(static_alpha + static_fade_speed * dt, static_target_alpha)
        elif static_alpha > static_target_alpha:
            static_alpha = max(static_alpha - static_fade_speed * dt, static_target_alpha)

        click_once = False

        if camera_active and click_once:
            mx, my = pygame.mouse.get_pos()

            for rect, cam_name in CAM_BUTTON_RECTS:
                if rect.collidepoint(mx, my):
                    camera_index = CAMERA_ORDER.index(cam_name)
                    current_camera_name = cam_name
                    print(f"[CAM] Switched to {cam_name}")

                    if CAMERA_SWITCH_SOUND:
                        CAMERA_SWITCH_SOUND.play()

                    break

        # draw ....................................................................................................................................
        SCREEN.fill((10,10,10))
        # center large camera view
        big_room = ROOMS[CAMERA_ORDER[camera_index]]
        big_view = big_room.view_surface.copy()

        # --- Fade the static in/out smoothly ---
        fade_speed = 100 * dt  # how fast to fade
        target_alpha = 255 if camera_active else 0
        if static_alpha < target_alpha:
            static_alpha = min(static_alpha + fade_speed, target_alpha)
        elif static_alpha > target_alpha:
            static_alpha = max(static_alpha - fade_speed, target_alpha)

        # --- Camera flicker and static ---
        if camera_active:
            # --- Draw the camera feed ---
            big_room = ROOMS[CAMERA_ORDER[camera_index]]
            big_view = big_room.view_surface.copy()
            draw_camera_side_panel(SCREEN, camera_active)

            # --- Draw animatronic image for the current camera (once per frame) ---
            drawn_rooms = set()
            for a in animatronics:
                if a.current_room == big_room.name and a.visible and a.current_room not in drawn_rooms:
                    anim_img = a.get_room_image()
                    big_view.blit(anim_img, (0, 0))
                    drawn_rooms.add(a.current_room)



            big_scaled = pygame.transform.scale(big_view, (1280, 720))
            SCREEN.blit(big_scaled, (WIDTH//2 - 640, HEIGHT//2 - 360))

                # --- Animated static overlay for 1080p (with fade) ---
            if CAMERA_ORDER[camera_index] != "Office" and STATIC_FRAMES:
                STATIC_FRAME_TIMER += dt
                if STATIC_FRAME_TIMER > 0.05:
                    STATIC_FRAME_INDEX = (STATIC_FRAME_INDEX + 1) % len(STATIC_FRAMES)
                    STATIC_FRAME_TIMER = 0.0

            static_frame = pygame.transform.scale(
                STATIC_FRAMES[STATIC_FRAME_INDEX], (1280, 720)
            ).convert_alpha()

            translucent_static = pygame.Surface(static_frame.get_size(), pygame.SRCALPHA)
            translucent_static.blit(static_frame, (0, 0))
           
                
            translucent_static.set_alpha(int(static_alpha * 0.25))  # fade amount

            SCREEN.blit(translucent_static, (WIDTH // 2 - 640, HEIGHT // 2 - 360))


            # --- Animated static overlay for 1080p ---
            if camera_active and CAMERA_ORDER[camera_index] != "Office" and STATIC_FRAMES:
                STATIC_FRAME_TIMER += dt
                if STATIC_FRAME_TIMER > 0.05:
                    STATIC_FRAME_INDEX = (STATIC_FRAME_INDEX + 1) % len(STATIC_FRAMES)
                    STATIC_FRAME_TIMER = 0.0

                static_frame = pygame.transform.scale(
                    STATIC_FRAMES[STATIC_FRAME_INDEX], (1280, 720)
                ).convert_alpha()  # make sure it's using per-pixel alpha

                # --- custom transparent blend ---
                translucent_static = pygame.Surface(static_frame.get_size(), pygame.SRCALPHA)
                translucent_static.blit(static_frame, (0, 0))
                translucent_static.set_alpha(int(static_alpha * 0.05))  # only half opacity for subtle static

                SCREEN.blit(translucent_static, (WIDTH // 2 - 640, HEIGHT // 2 - 360))

            if camera_active:
                if camera_booting:
                    camera_boot_timer -= dt
                    STATIC_OVERLAY.set_alpha(180)
                    SCREEN.blit(STATIC_OVERLAY, (0, 0))
                    if camera_boot_timer <= 0:
                        camera_booting = False
                else:
                    draw_camera_overlay(SCREEN, current_camera_name, booting=camera_booting)



        else:
            if not camera_active:
                # --- Draw the office ---
                office_surface = OFFICE_BASE.copy()
                


                # --- Draw closed door overlay ---
                if door_closed:
                    office_surface.blit(DOOR_CLOSED_IMG, (0, 0))  # adjust coordinates if needed

                # --- Draw any animatronics visible in the office ---
                for a in animatronics:
                    if a.current_room == "Office" and a.visible:
                        a.draw_on_surface(office_surface)


                # draw any animatronics visible in the office (like jumpscare proximity)
                for a in animatronics:
                    if a.current_room == "Office" and a.visible:
                        a.draw_on_surface(office_surface)

                office_scaled = pygame.transform.scale(office_surface, (WIDTH, HEIGHT))
                SCREEN.blit(office_scaled, (0, 0))



        draw_ui()

        def draw_camera_overlay(surface, camera_name, booting=False):
            """Draw realistic FNaF-style camera overlay on top of the camera feed."""
            global rec_flash_timer, rec_visible

            # --- Base scanline overlay ---
            surface.blit(SCANLINE_OVERLAY, (0, 0))

            # --- Slight vignette ---
            vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for i in range(0, 255, 15):
                pygame.draw.rect(vignette, (0, 0, 0, i // 8),
                                (i // 6, i // 6, WIDTH - i // 3, HEIGHT - i // 3), 5)
            surface.blit(vignette, (0, 0))

            # --- REC indicator (now top-left) ---
            rec_flash_timer += 1 / 60
            if rec_flash_timer >= 0.5:
                rec_flash_timer = 0
                rec_visible = not rec_visible

            if rec_visible:
                rec_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
                rec_text = rec_font.render("REC", True, (255, 40, 40))
                surface.blit(rec_text, (50, 40))
                pygame.draw.circle(surface, (255, 0, 0), (130, 50), 8)

            # --- Booting effect (signal lost) ---
            if booting:
                signal_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 38)
                signal_label = signal_font.render("SIGNAL LOST", True, (255, 255, 255))
                surface.blit(signal_label, (WIDTH//2 - signal_label.get_width()//2,
                                            HEIGHT//2 - signal_label.get_height()//2))
                # Black flicker overlay
                boot_overlay = pygame.Surface((WIDTH, HEIGHT))
                boot_overlay.fill((0, 0, 0))
                boot_overlay.set_alpha(random.randint(160, 220))
                surface.blit(boot_overlay, (0, 0))

            # --- Random flicker ---
            if random.random() < 0.02:
                flicker_overlay = pygame.Surface((WIDTH, HEIGHT))
                brightness = random.randint(15, 40)
                flicker_overlay.fill((brightness, brightness, brightness))
                flicker_overlay.set_alpha(random.randint(20, 60))
                surface.blit(flicker_overlay, (0, 0))



        draw_camera_overlay(SCREEN, current_camera_name, booting=camera_booting)



        #blackout
        if power <= 0:
            blackout = pygame.Surface((WIDTH, HEIGHT))
            blackout.set_alpha(180)
            blackout.fill((0, 0, 0))
            SCREEN.blit(blackout, (0, 0))

        if game_over:
            # show jumpscare overlay for a short time
            SCREEN.blit(JUMPSCARE_IMG, (0,0))
            jumpscare_time -= dt
            if jumpscare_time <= 0:
                # end menu / quit
                running = False

        mx, my = pygame.mouse.get_pos()
        draw_camera_hover_bar(SCREEN, my, dt)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_menu()
    show_night_intro(SCREEN, "Night 1")
    main()
