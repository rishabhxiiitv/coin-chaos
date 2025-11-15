import asyncio
import json
import pygame
import websockets
import time
import random 

# --- MODIFIED: Constants ---
WIDTH, HEIGHT = 800, 600
SIDE_PANEL_WIDTH = 200
PANEL_COLOR = (30, 30, 30) 

FRAME_RATE = 60
WEBSOCKET_SEND_TIMEOUT = 0.1
PLAYER_SPEED = 7
PLAYER_SIZE = 64
RESOURCE_SIZE = 32
BACKGROUND_COLOR = (127, 64, 0)
TEXT_COLOR = (255, 255, 255) # White
TEXT_SIZE = 24
CHAT_TEXT_SIZE = 18 # Old chat font
CHAT_HISTORY_MAX = 15 # Increased max

KNOWN_PLAYER_COUNT = 0

# --- MODIFIED: Sprite Constants ---
PLAYER_IDLE_FILENAME = "Player.png" # With shadow, for idle
PLAYER_SPRITE_SHADOWLESS_FILENAME = "Player without shadow.png"
VISOR_COLOR = (60, 220, 220) 

# --- MODIFIED: Caches for L/R sprites ---
LOBBY_SPRITE_CACHE = {}
GAME_SPRITE_CACHE_L = {} # Will hold [idle]
GAME_SPRITE_CACHE_R = {} # Will hold [idle]

IDLE_TEMPLATE_L = None
IDLE_TEMPLATE_R = None
IDLE_TEMPLATE_SHADOWLESS = None

LOBBY_VISUALS = {}

# --- NEW: Chat UI Assets ---
# --- MODIFIED: Bubble images no longer needed ---
# chat_bubble_left_img = None
# chat_bubble_right_img = None
chat_send_img = None
chat_input_rect = None
chat_send_rect = None


# --- NEW: Helper function for chat timestamp ---
def get_chat_timestamp():
    """Returns a formatted string for the chat timestamp, e.g., '14:32'"""
    return time.strftime("%H:%M", time.localtime())

# --- MODIFIED: Pygame setup ---
pygame.init()
pygame.mixer.init()
pygame.font.init() # --- NEW: Ensure font module is initialized ---

# Font setup
try:
    FONT_NAME = 'Arial'
    font = pygame.font.SysFont(FONT_NAME, TEXT_SIZE)
    duration_font = pygame.font.SysFont(FONT_NAME, 28, bold=True)
    button_font = pygame.font.SysFont(FONT_NAME, 60, bold=True)
    panel_title_font = pygame.font.SysFont(FONT_NAME, 36, bold=True)
    panel_text_font = pygame.font.SysFont(FONT_NAME, 28)
    title_font = pygame.font.SysFont(FONT_NAME, 72, bold=True)

    # --- NEW: Load Custom Pixel Font ---
    pixel_title_font = pygame.font.Font('Jacquard24-Regular.ttf', 96) # Size 96
    # --- NEW: Smaller pixel font for timer screen ---
    pixel_title_font_small = pygame.font.Font('Jacquard24-Regular.ttf', 72) 

    lobby_name_font = pygame.font.SysFont(FONT_NAME, 18)

    # --- NEW: Fonts for the New Panel ---
    panel_tab_font = pygame.font.SysFont(FONT_NAME, 24, bold=True)
    panel_list_font = pygame.font.SysFont(FONT_NAME, 22)
    panel_leaderboard_font = pygame.font.SysFont(FONT_NAME, 18) # <-- NEW
    # --- END NEW ---

    # --- MODIFIED: Chat UI Fonts (Using default font) ---

    chat_bubble_font = pygame.font.Font(None, 18) # Use default font
    chat_timestamp_font = pygame.font.Font(None, 12) # Use default font
    chat_name_font = pygame.font.Font(None, 16) # Use default font
    chat_name_font.set_bold(True)
    chat_system_font = pygame.font.Font(None, 16) # Use default font
    chat_system_font.set_italic(True)
    chat_input_font = pygame.font.Font(None, 18) # Use default font
    
    # --- NEW: Timer Screen Font ---
    timer_number_font = pygame.font.Font('Jacquard24-Regular.ttf', 80)
    
    # --- NEW: In-Game Score Font ---
    score_box_font = pygame.font.SysFont(FONT_NAME, 18, bold=True)


except Exception as e:
    print(f"Warning: Could not load 'Jacquard24-Regular.ttf' or '{FONT_NAME}' font. Falling back to default. Error: {e}")
    # Fallback fonts
    font = pygame.font.Font(None, TEXT_SIZE)
    duration_font = pygame.font.Font(None, 28)
    button_font = pygame.font.Font(None, 60)
    panel_title_font = pygame.font.Font(None, 36)
    panel_text_font = pygame.font.Font(None, 28)
    title_font = pygame.font.Font(None, 72)
    
    # --- NEW: Fallback for Custom Font ---
    pixel_title_font = title_font # Use the default title font as a fallback
    pixel_title_font_small = title_font

    lobby_name_font = pygame.font.Font(None, 18)

    # --- NEW: Fallbacks for New Panel Fonts ---
    panel_tab_font = pygame.font.Font(None, 24)
    panel_list_font = pygame.font.Font(None, 22)
    panel_leaderboard_font = pygame.font.Font(None, 18) # <-- NEW
    # --- END NEW ---
    
    # --- MODIFIED: Chat Fonts Fallback ---
    chat_bubble_font = pygame.font.Font(None, 18)
    chat_timestamp_font = pygame.font.Font(None, 12)
    chat_name_font = pygame.font.Font(None, 16)
    chat_name_font.set_bold(True)
    chat_system_font = pygame.font.Font(None, 16)
    chat_system_font.set_italic(True)
    chat_input_font = pygame.font.Font(None, 18)
    
    # --- NEW: Timer Font Fallback ---
    timer_number_font = button_font
    
    # --- NEW: Score Font Fallback ---
    score_box_font = pygame.font.Font(None, 18)
    score_box_font.set_bold(True)


# --- MODIFIED: Removed pygame.FULLSCREEN flag ---
window = pygame.display.set_mode((WIDTH + SIDE_PANEL_WIDTH, HEIGHT))
pygame.display.set_caption("Multiplayer Game")
clock = pygame.time.Clock()
playground_rect = pygame.Rect(0, 0, WIDTH, HEIGHT)
panel_rect = pygame.Rect(WIDTH, 0, SIDE_PANEL_WIDTH, HEIGHT)

# --- NEW: Chat State Variables ---
chat_history = []
is_chatting = False
current_chat_message = ""
active_panel_tab = "lobby" # --- NEW: Tracks active tab
chat_scroll_offset = 0 # --- NEW: For scrolling

# --- NEW: Chat UI Rects ---
# We define the rectangles for the new chat UI
# --- MODIFIED: Moved chat input up to fit above the new footer ---
chat_input_rect = pygame.Rect(WIDTH + 10, HEIGHT - 230, SIDE_PANEL_WIDTH - 55, 40)
chat_send_rect = pygame.Rect(chat_input_rect.right + 5, HEIGHT - 230, 40, 40)


# Load Coin Sprite (Unchanged)
try:
    coin_sprite = pygame.image.load("Coin.png")
    coin_sprite = pygame.transform.scale(coin_sprite, (RESOURCE_SIZE, RESOURCE_SIZE))
except Exception as e:
    print(f"Warning: Could not load 'Coin.png': {e}")
    coin_sprite = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    pygame.draw.circle(coin_sprite, (255, 215, 0), (RESOURCE_SIZE//2, RESOURCE_SIZE//2), RESOURCE_SIZE//2)


# Load Background Tile (Unchanged)
try:
    ground_tile = pygame.image.load("ground.png").convert()
except pygame.error as e:
    print(f"Warning: Could not load ground.png: {e}")
    ground_tile = pygame.Surface((32, 32)); ground_tile.fill(BACKGROUND_COLOR)
tile_width, tile_height = ground_tile.get_width(), ground_tile.get_height()

# --- MODIFIED: Load Player Sprite Templates ---
try:
    # 1. Load IDLE sprites (L/R)
    IDLE_TEMPLATE_L = pygame.image.load(PLAYER_IDLE_FILENAME).convert_alpha() 
    IDLE_TEMPLATE_L = pygame.transform.scale(IDLE_TEMPLATE_L, (90, 110)) 
    IDLE_TEMPLATE_R = pygame.transform.flip(IDLE_TEMPLATE_L, True, False)
    
    # 2. Load shadowless sprite (for lobby)
    IDLE_TEMPLATE_SHADOWLESS = pygame.image.load(PLAYER_SPRITE_SHADOWLESS_FILENAME).convert_alpha()
    IDLE_TEMPLATE_SHADOWLESS = pygame.transform.scale(IDLE_TEMPLATE_SHADOWLESS, (70, 90))

except Exception as e:
    print(f"CRITICAL: Could not load player sprites. Check filenames (Player.png, Player without shadow.png). Error: {e}")
    IDLE_TEMPLATE_L, IDLE_TEMPLATE_R, IDLE_TEMPLATE_SHADOWLESS = [None]*3

# --- NEW: Load Chat Assets ---
try:
    # --- MODIFIED: Bubble images no longer needed ---
    # chat_bubble_left_img = pygame.image.load("chat_bubble_left.png").convert_alpha()
    # chat_bubble_right_img = pygame.image.load("chat_bubble_right.png").convert_alpha()
    chat_send_img = pygame.image.load("Send logo.png").convert_alpha()
    
    # Scale them to fit
    # bubble_height = 50
    # chat_bubble_left_img = pygame.transform.scale(chat_bubble_left_img, (140, bubble_height))
    # chat_bubble_right_img = pygame.transform.scale(chat_bubble_right_img, (140, bubble_height))
    chat_send_img = pygame.transform.scale(chat_send_img, (25, 25))
    
except Exception as e:
    print(f"CRITICAL: Could not load chat assets. {e}")


# --- MODIFIED: Load sounds ---
try:
    click_sound = pygame.mixer.Sound("click.wav")
    coin_sound = pygame.mixer.Sound("coin.wav")
    connect_sound = pygame.mixer.Sound("connect.wav")
    disconnect_sound = pygame.mixer.Sound("disconnect.wav")
    walking_sound = None # We'll load this one later if it exists
    
    # --- NEW: Game Over Sound ---
    try:
        game_over_sound = pygame.mixer.Sound("game_over.wav")
    except FileNotFoundError:
        print("Warning: 'game_over.wav' not found, using dummy sound.")
        class DummySound:
            def play(self, *args, **kwargs): pass
            def stop(self): pass
        game_over_sound = DummySound()
    # --- END NEW ---
    
    # --- NEW: Safely load chat sound ---
    try:
        chat_message_sound = pygame.mixer.Sound("chat_message.wav")
    except FileNotFoundError:
        print("Warning: 'chat_message.wav' not found, using dummy sound.")
        class DummySound:
            def play(self, *args, **kwargs): pass
            def stop(self): pass
        chat_message_sound = DummySound()
        
    walking_sound_channel = None 
except pygame.error as e:
    print(f"Warning: Core sound files not found. {e}")
    class DummySound:
        def play(self, *args, **kwargs): pass
        def stop(self): pass
    click_sound, coin_sound, connect_sound, disconnect_sound, walking_sound = [DummySound()]*5
    chat_message_sound = DummySound() # Add fallback here too
    game_over_sound = DummySound() # <-- Add fallback here
    walking_sound_channel = DummySound()

# --- Helper function to draw background (Unchanged) ---
def draw_playground_background():
    # Tile the background
    for y in range(0, HEIGHT, tile_height):
        for x in range(0, WIDTH, tile_width):
            window.blit(ground_tile, (x, y))

# --- Helper function to draw outlined text (Unchanged) ---
def draw_text_outline(text_surface, position, outline_color=(0,0,0)):
    # Helper to draw outline
    x, y = position
    # Blit the outline surfaces in 8 directions
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0: continue # Don't draw center
            # Re-render the text in black for the outline
            outline_surf = text_surface.copy()
            # This complex fill is to preserve antialiasing
            outline_surf.fill(outline_color, special_flags=pygame.BLEND_RGB_MULT)
            window.blit(outline_surf, (x + dx, y + dy))

# --- "Two-Tone" color swapping function (Unchanged) ---
def create_colored_sprite(base_sprite, new_color_tuple):
    if base_sprite is None: return None
    colored_sprite = base_sprite.copy()
    dark_shade = (int(new_color_tuple[0] * 0.5), int(new_color_tuple[1] * 0.5), int(new_color_tuple[2] * 0.5))
    for x in range(colored_sprite.get_width()):
        for y in range(colored_sprite.get_height()):
            pixel_color = colored_sprite.get_at((x, y))
            r, g, b, a = pixel_color
            if a < 50: continue
            # These color checks are specific to the template image
            is_green_visor = (g > 150 and g > r and g > b)
            is_red_body = (r > 150 and r > g and r > b)
            is_blue_shadow = (b > 150 and b > r and b > g)
            if is_green_visor:
                colored_sprite.set_at((x, y), VISOR_COLOR)
            elif is_red_body:
                colored_sprite.set_at((x, y), new_color_tuple)
            elif is_blue_shadow:
                colored_sprite.set_at((x, y), dark_shade)
    return colored_sprite

# --- MODIFIED: Two cache management functions ---
def update_lobby_sprite_cache(players_data):
    """Updates the LOBBY (shadowless) sprite cache."""
    global LOBBY_SPRITE_CACHE, IDLE_TEMPLATE_SHADOWLESS
    for player_id_str, player_data in players_data.items():
        if player_id_str not in LOBBY_SPRITE_CACHE:
            new_color_tuple = tuple(player_data.get("color", (255, 255, 255))) 
            LOBBY_SPRITE_CACHE[player_id_str] = create_colored_sprite(IDLE_TEMPLATE_SHADOWLESS, new_color_tuple)
    for cached_id in list(LOBBY_SPRITE_CACHE.keys()):
        if cached_id not in players_data:
            del LOBBY_SPRITE_CACHE[cached_id]

def update_game_sprite_cache(players_data):
    """Updates the GAME (L & R, with animation) sprite cache."""
    global GAME_SPRITE_CACHE_L, GAME_SPRITE_CACHE_R, IDLE_TEMPLATE_L, IDLE_TEMPLATE_R
    
    for player_id_str, player_data in players_data.items():
        if player_id_str not in GAME_SPRITE_CACHE_L: # Check only one cache
            new_color_tuple = tuple(player_data.get("color", (255, 255, 255))) 
            
            # Create LEFT animation frames
            colored_idle_L = create_colored_sprite(IDLE_TEMPLATE_L, new_color_tuple)
            GAME_SPRITE_CACHE_L[player_id_str] = [colored_idle_L]
            
            # Create RIGHT animation frames
            colored_idle_R = create_colored_sprite(IDLE_TEMPLATE_R, new_color_tuple)
            GAME_SPRITE_CACHE_R[player_id_str] = [colored_idle_R]

    for cached_id in list(GAME_SPRITE_CACHE_L.keys()):
        if cached_id not in players_data:
            del GAME_SPRITE_CACHE_L[cached_id]
            del GAME_SPRITE_CACHE_R[cached_id]


# --- NEW: Text Wrapping Helper ---
def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + word + " "
        try:
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        except pygame.error as e:
            print(f"Warning: Pygame font error during text wrap: {e}")
            lines.append(current_line.strip()) # Add what we have
            current_line = word + " "
    lines.append(current_line.strip())
    return lines


# --- COMPLETELY MODIFIED: draw_chat_ui ---
def draw_chat_ui(my_player_id, chat_area_bottom): # <-- ADDED PARAMETER
    """Draws the new reference image chat UI."""
    global chat_history, is_chatting, current_chat_message, chat_input_rect, chat_send_rect
    global chat_bubble_font, chat_timestamp_font, chat_name_font, chat_system_font, chat_input_font
    global chat_send_img
    
    # --- 1. Draw the Input Box (at the bottom) ---
    # --- THIS SECTION IS NOW DRAWN INSIDE THE GAME_LOOP/LOBBY_LOOP ---
    
    # --- 2. Draw the Chat History (at the top) ---
    chat_area_top = 60
    # --- MODIFIED: Use parameter ---
    # chat_area_bottom = chat_input_rect.top - 10 
    
    # --- NEW: Apply scroll offset ---
    y_scroll_pixels = chat_scroll_offset * 30 # 30 pixels per "tick"
    y_offset = chat_area_bottom + y_scroll_pixels # Start drawing from the bottom, offset by scroll
    
    # --- NEW: Set a clipping rect to contain the history ---
    chat_clip_rect = pygame.Rect(WIDTH, chat_area_top, SIDE_PANEL_WIDTH, chat_area_bottom - chat_area_top)
    original_clip = window.get_clip()
    window.set_clip(chat_clip_rect)
    
    sprite_size = (35, 45)
    avatar_x_padding = 10
    box_x_padding = 10 # Padding inside the white box
    box_y_padding = 10
    
    # Calculate available width for the box and text
    box_width = SIDE_PANEL_WIDTH - sprite_size[0] - avatar_x_padding * 3
    text_wrap_width = box_width - box_x_padding * 2
    
    # --- NEW: Initialize variable to prevent UnboundLocalError ---
    message_total_height = 0 
    
    # Loop through messages *in reverse*
    for msg in reversed(chat_history):
        msg_type = msg.get("type", "chat")
        
        if msg_type == "system":
            # --- Draw System Message (Unchanged) ---
            text = msg.get("msg", "")
            system_surface = chat_system_font.render(text, True, (150, 150, 150))
            system_rect = system_surface.get_rect(center=(WIDTH + SIDE_PANEL_WIDTH // 2, y_offset))
            window.blit(system_surface, system_rect)
            y_offset -= 30 # Move up for next message
            
        elif msg_type == "chat":
            # --- Draw Chat Message (New Layout) ---
            sender_id = str(msg.get("sender_id", 0))
            is_my_message = (sender_id == str(my_player_id))
            
            # 1. Get text and wrap it
            message_text = msg.get("msg", "")
            wrapped_lines = wrap_text(message_text, chat_bubble_font, text_wrap_width)
            
            # 2. Calculate heights
            text_block_height = len(wrapped_lines) * 18 # 18px per line (font size)
            box_height = text_block_height + (box_y_padding * 2)
            if box_height < sprite_size[1]: # Ensure box is at least as tall as avatar
                box_height = sprite_size[1]
                
            name_bar_height = 20 # Space for name + timestamp
            message_total_height = box_height + name_bar_height + 5 # +5 for padding
            
            # 3. Move Y-offset up
            y_offset -= message_total_height
            
            # 4. Get Avatar
            sprite = LOBBY_SPRITE_CACHE.get(sender_id)
            if sprite:
                sprite = pygame.transform.scale(sprite, sprite_size)
            
            # 5. Define rects based on sender
            name_y = y_offset + 3
            box_y = y_offset + name_bar_height
            
            if is_my_message:
                # --- My Message (Right Aligned) ---
                avatar_x = WIDTH + SIDE_PANEL_WIDTH - avatar_x_padding - sprite_size[0]
                box_x = WIDTH + SIDE_PANEL_WIDTH - avatar_x_padding - sprite_size[0] - box_width - 5
                
                # Draw Name (You)
                name_surface = chat_name_font.render(msg.get("name", "Me"), True, tuple(msg.get("color", TEXT_COLOR)))
                name_rect = name_surface.get_rect(topright=(avatar_x + sprite_size[0], name_y))
                window.blit(name_surface, name_rect)
                
                # Draw Timestamp
                ts_surface = chat_timestamp_font.render(msg.get("timestamp", ""), True, (150, 150, 150))
                ts_rect = ts_surface.get_rect(topright=(name_rect.left - 5, name_y + 2))
                window.blit(ts_surface, ts_rect)
                
                # Draw Avatar
                if sprite:
                    # --- NEW: Flip avatar for sender ---
                    flipped_sprite = pygame.transform.flip(sprite, True, False)
                    window.blit(flipped_sprite, (avatar_x, box_y))
                
                # Draw Box
                pygame.draw.rect(window, (255, 255, 255), (box_x, box_y, box_width, box_height), border_radius=15)
                
                # Draw Wrapped Text
                line_y_offset = box_y + box_y_padding
                for line in wrapped_lines:
                    line_surface = chat_bubble_font.render(line, True, (0, 0, 0)) # Black text
                    window.blit(line_surface, (box_x + box_x_padding, line_y_offset))
                    line_y_offset += 18 # Match font size

            else:
                # --- Other's Message (Left Aligned) ---
                avatar_x = WIDTH + avatar_x_padding
                box_x = avatar_x + sprite_size[0] + 5
                
                # Draw Name
                name_surface = chat_name_font.render(msg.get("name", "Player"), True, tuple(msg.get("color", TEXT_COLOR)))
                name_rect = name_surface.get_rect(topleft=(box_x, name_y))
                window.blit(name_surface, name_rect)
                
                # Draw Timestamp
                ts_surface = chat_timestamp_font.render(msg.get("timestamp", ""), True, (150, 150, 150))
                ts_rect = ts_surface.get_rect(topleft=(name_rect.right + 5, name_y + 2))
                window.blit(ts_surface, ts_rect)
                
                # Draw Avatar
                if sprite:
                    window.blit(sprite, (avatar_x, box_y))
                
                # Draw Box
                pygame.draw.rect(window, (255, 255, 255), (box_x, box_y, box_width, box_height), border_radius=15)
                
                # Draw Wrapped Text
                line_y_offset = box_y + box_y_padding
                for line in wrapped_lines:
                    line_surface = chat_bubble_font.render(line, True, (0, 0, 0)) # Black text
                    window.blit(line_surface, (box_x + box_x_padding, line_y_offset))
                    line_y_offset += 18 # Match font size

            y_offset -= 10 # Padding between messages

        # --- MODIFIED: Stop drawing if we go off-screen ---
        if y_offset < chat_area_top - message_total_height: # Give a buffer
            break
            
    # --- NEW: Restore the original clipping rect ---
    window.set_clip(original_clip)


# --- MODIFIED: lobby_loop (returns data) ---
async def lobby_loop(websocket, my_player_id):
    global font, KNOWN_PLAYER_COUNT, click_sound, connect_sound, disconnect_sound
    global button_font, lobby_name_font, duration_font, LOBBY_VISUALS
    # --- NEW: Make chat variables global ---
    global is_chatting, current_chat_message, chat_history, chat_message_sound, active_panel_tab, chat_scroll_offset
    
    players = {}
    host_player_id = 0
    
    # --- NEW: Lobby state variables ---
    current_lobby_screen = "main" # "main" or "timer_select"
    selected_minutes = 2 
    
    # --- Button Colors ---
    BUTTON_TEXT_COLOR = (0, 0, 0)
    start_color_inactive = (0, 200, 0); start_color_hover = (0, 255, 0); start_color_click = (0, 150, 0) 
    leave_color_inactive = (200, 50, 50); leave_color_hover = (255, 100, 100); leave_color_click = (150, 0, 0)
    
    # --- Main Lobby Buttons ---
    lobby_start_button_rect = pygame.Rect(WIDTH // 2 - 100, 400, 200, 60)
    lobby_start_button_text = font.render("Play", True, BUTTON_TEXT_COLOR)
    leave_button_rect = pygame.Rect(20, 20, 100, 40)
    leave_text = font.render("Leave", True, BUTTON_TEXT_COLOR)

    # --- Panel Tab Definitions ---
    lobby_tab_rect = pygame.Rect(WIDTH, 10, 95, 40)
    chat_tab_rect = pygame.Rect(WIDTH + 105, 10, 95, 40)
    TAB_COLOR_INACTIVE = (30, 30, 30)
    TAB_COLOR_ACTIVE = (50, 50, 50)
    TAB_TEXT_COLOR = (255, 255, 255)
    TAB_LINE_COLOR = (100, 100, 100)

    # --- NEW: Timer Select Screen Buttons ---
    back_button_rect = pygame.Rect(20, 20, 60, 60) # Circle, center (50, 50), radius 30
    timer_start_button_rect = pygame.Rect(WIDTH // 2 - 100, 500, 200, 60)
    timer_start_button_text = font.render("Start Game", True, BUTTON_TEXT_COLOR)
    
    # Timer boxes
    min_box_rect = pygame.Rect(WIDTH//2 - 120, 350, 100, 100)
    sec_box_rect = pygame.Rect(WIDTH//2 + 20, 350, 100, 100)
    
    # Timer arrows
    min_up_rect = pygame.Rect(min_box_rect.left, min_box_rect.top - 50, 100, 40)
    min_down_rect = pygame.Rect(min_box_rect.left, min_box_rect.bottom + 10, 100, 40)
    sec_up_rect = pygame.Rect(sec_box_rect.left, sec_box_rect.top - 50, 100, 40)
    sec_down_rect = pygame.Rect(sec_box_rect.left, sec_box_rect.bottom + 10, 100, 40)
    
    # Arrow button colors
    ARROW_COLOR_INACTIVE = (100, 100, 100)
    ARROW_COLOR_HOVER = (150, 150, 150)
    ARROW_COLOR_CLICK = (200, 200, 200)
    ARROW_COLOR_DISABLED = (50, 50, 50)
    
    # --- NEW: Lobby-specific chat rects (at the bottom) ---
    lobby_chat_input_rect = pygame.Rect(WIDTH + 10, HEIGHT - 50, SIDE_PANEL_WIDTH - 55, 40)
    lobby_chat_send_rect = pygame.Rect(lobby_chat_input_rect.right + 5, HEIGHT - 50, 40, 40)


    lobby_running = True
    while lobby_running:
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=WEBSOCKET_SEND_TIMEOUT)
            data = json.loads(response)

            # --- NEW: Handle NEW Chat Broadcast ---
            if data.get("type") == "chat_broadcast":
                chat_history.append({
                    "type": "chat",
                    "sender_id": data.get("sender_id"),
                    "name": data.get("sender_name", "System"),
                    "color": data.get("sender_color", (200, 200, 200)),
                    "msg": data.get("message", ""),
                    "timestamp": data.get("timestamp", "")
                })
                if len(chat_history) > CHAT_HISTORY_MAX:
                    chat_history.pop(0)
                if not is_chatting:
                    chat_message_sound.play()
                continue
            # --- NEW: Handle System Message ---
            elif data.get("type") == "system_message":
                chat_history.append({
                    "type": "system",
                    "msg": data.get("message", ""),
                    "timestamp": data.get("timestamp", "")
                })
                if len(chat_history) > CHAT_HISTORY_MAX:
                    chat_history.pop(0)
                #chat_message_sound.play()
                continue
            # --- END NEW ---

            players = data.get("players", {})
            host_player_id = data.get("host_player_id", 0) 
            update_lobby_sprite_cache(players)
            new_player_count = len(players)
            for pid_str in players:
                if pid_str not in LOBBY_VISUALS:
                    LOBBY_VISUALS[pid_str] = {
                        "x": random.randint(0, WIDTH - PLAYER_SIZE),
                        "y": random.randint(0, HEIGHT - PLAYER_SIZE),
                        "dx": random.choice([-1, 1, 1.5, -1.5]), 
                        "dy": random.choice([-1, 1, 1.5, -1.5]),
                        "angle": random.randint(0, 360),
                        "rotation_speed": random.choice([-2, -1, 1, 2])
                    }
            for pid_str in list(LOBBY_VISUALS.keys()):
                if pid_str not in players:
                    del LOBBY_VISUALS[pid_str]
            if new_player_count > KNOWN_PLAYER_COUNT: connect_sound.play()
            elif new_player_count < KNOWN_PLAYER_COUNT: disconnect_sound.play()
            KNOWN_PLAYER_COUNT = new_player_count
            
            current_game_state = data.get("game_state")
            if current_game_state == "playing" or current_game_state == "countdown":
                lobby_running = False
                return data 

        except asyncio.TimeoutError:
            pass 
        except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError):
            print("Connection error in lobby."); return None 

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); return None
            
            # --- Chat Input Handling (Shared) ---
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if is_chatting:
                        # Send message
                        if current_chat_message:
                            try:
                                await websocket.send(json.dumps({"type": "chat", "message": current_chat_message}))
                                
                                # --- NEW: Local Echo ---
                                my_player_data = players.get(str(my_player_id), {})
                                chat_history.append({
                                    "type": "chat",
                                    "sender_id": str(my_player_id),
                                    "name": my_player_data.get("name", "Me"),
                                    "color": my_player_data.get("color", TEXT_COLOR),
                                    "msg": current_chat_message,
                                    "timestamp": get_chat_timestamp()
                                })
                                if len(chat_history) > CHAT_HISTORY_MAX:
                                    chat_history.pop(0)
                                chat_message_sound.play() # <-- NEW: Play sound on local echo
                                # --- END NEW ---
                                
                            except websockets.exceptions.ConnectionClosed:
                                print("Failed to send chat."); lobby_running = False; return None
                        current_chat_message = ""
                        is_chatting = False
                    else:
                        # Activate chat (if chat tab is active and on main screen)
                        # --- MODIFIED: Allow chat activation on timer screen too ---
                        if active_panel_tab == "chat": # and current_lobby_screen == "main":
                            is_chatting = True
                elif is_chatting:
                    if event.key == pygame.K_BACKSPACE:
                        current_chat_message = current_chat_message[:-1]
                    elif event.unicode.isprintable(): # Only add printable chars
                        # Limit chat message length
                        if chat_input_font.size(current_chat_message + event.unicode)[0] < lobby_chat_input_rect.width - 20: # Use lobby rect width
                            current_chat_message += event.unicode
            
            # --- NEW: Scroll Wheel Handling (Lobby) ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Define the chat history area
                chat_history_area_rect = pygame.Rect(WIDTH, 60, SIDE_PANEL_WIDTH, lobby_chat_input_rect.top - 60) # From tabs to input box
                
                if active_panel_tab == 'chat' and chat_history_area_rect.collidepoint(event.pos):
                    if event.button == 4: # Scroll Up
                        chat_scroll_offset = max(0, chat_scroll_offset - 1)
                        continue # This click was for scrolling
                    elif event.button == 5: # Scroll Down
                        chat_scroll_offset += 1
                        continue # This click was for scrolling
                    # --- BUG FIX: Removed 'continue' from here. ---
                    # A left-click (button 1) should now fall through.

            # --- MOUSEBUTTONDOWN HANDLER (Split by screen state) ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                
                # --- 1. Handle Panel Clicks FIRST (Tabs & Chat UI) ---
                # These should work on BOTH screens.
                
                # 1a. Tab Clicks
                if lobby_tab_rect.collidepoint(event.pos):
                    active_panel_tab = "lobby"
                    is_chatting = False # Deactivate chat when switching tabs
                    click_sound.play()
                    continue # Done with this click
                if chat_tab_rect.collidepoint(event.pos):
                    active_panel_tab = "chat"
                    is_chatting = True # Auto-focus chat
                    click_sound.play()
                    continue # Done with this click

                # 1b. Chat UI Clicks
                if is_chatting:
                    if lobby_chat_send_rect.collidepoint(event.pos): # <-- USE LOBBY RECT
                        if current_chat_message:
                            try:
                                await websocket.send(json.dumps({"type": "chat", "message": current_chat_message}))
                                
                                # --- NEW: Local Echo ---
                                my_player_data = players.get(str(my_player_id), {})
                                chat_history.append({
                                    "type": "chat",
                                    "sender_id": str(my_player_id),
                                    "name": my_player_data.get("name", "Me"),
                                    "color": my_player_data.get("color", TEXT_COLOR),
                                    "msg": current_chat_message,
                                    "timestamp": get_chat_timestamp()
                                })
                                if len(chat_history) > CHAT_HISTORY_MAX:
                                    chat_history.pop(0)
                                chat_message_sound.play() # <-- NEW: Play sound on local echo
                                # --- END NEW ---
                                
                            except websockets.exceptions.ConnectionClosed:
                                print("Failed to send chat."); lobby_running = False; return None
                        current_chat_message = ""
                        continue 
                    
                    if lobby_chat_input_rect.collidepoint(event.pos): # <-- USE LOBBY RECT
                        continue # Just focusing chat
                    
                    # Clicked outside chat UI
                    is_chatting = False
                    # Let click fall through
                
                # --- 2. Handle Screen-Specific Clicks ---
                if current_lobby_screen == "main":
                    # --- 1. Handle Main Lobby Clicks ---
                    
                    # 1c. Main Buttons (Leave, Start)
                    if leave_button_rect.collidepoint(event.pos):
                        click_sound.play(); return None
                        
                    if my_player_id == host_player_id: 
                        if lobby_start_button_rect.collidepoint(event.pos):
                            click_sound.play() 
                            # --- MODIFIED: Switch to timer screen ---
                            current_lobby_screen = "timer_select"
                            # is_chatting = False # No longer needed, panel is always active
                            continue # Stop processing click

                elif current_lobby_screen == "timer_select":
                    # --- 2. Handle Timer Select Screen Clicks ---
                    
                    if back_button_rect.collidepoint(event.pos):
                        current_lobby_screen = "main"
                        click_sound.play()
                        continue

                    if min_up_rect.collidepoint(event.pos):
                        selected_minutes = min(99, selected_minutes + 1)
                        click_sound.play()
                        continue

                    if min_down_rect.collidepoint(event.pos):
                        selected_minutes = max(1, selected_minutes - 1)
                        click_sound.play()
                        continue
                        
                    if timer_start_button_rect.collidepoint(event.pos):
                        click_sound.play() 
                        try:
                            # --- MODIFIED: Send selected time ---
                            await websocket.send(json.dumps({"type": "start_game", "duration": selected_minutes}))
                        except websockets.exceptions.ConnectionClosed:
                            print("Failed to send start command."); return None 
                        # Loop will exit on its own when server sends "countdown" state
                        continue
            # --- END OF MOUSEBUTTONDOWN HANDLER ---
                        
        # --- Player Bouncing Logic (Only for main screen) ---
        if current_lobby_screen == "main":
            for pid_str, visual in LOBBY_VISUALS.items():
                visual["x"] += visual["dx"]
                visual["y"] += visual["dy"]
                visual["angle"] = (visual["angle"] + visual["rotation_speed"]) % 360
                sprite = LOBBY_SPRITE_CACHE.get(pid_str) 
                if sprite:
                    w, h = sprite.get_size()
                    if visual["x"] <= 0 or visual["x"] >= WIDTH - w:
                        visual["dx"] *= -1
                    if visual["y"] <= 0 or visual["y"] >= HEIGHT - h:
                        visual["dy"] *= -1
            
        # --- DRAWING SECTION (Split by screen state) ---
        
        # --- 1. Draw Background (Screen-specific) ---
        if current_lobby_screen == "main":
            # --- 1. Draw Main Lobby Screen ---
            draw_playground_background()
            
            # Draw bouncing players
            for pid_str, visual in LOBBY_VISUALS.items():
                original_sprite = LOBBY_SPRITE_CACHE.get(pid_str) 
                if original_sprite:
                    rotated_sprite = pygame.transform.rotate(original_sprite, visual["angle"])
                    original_rect = original_sprite.get_rect(topleft=(visual["x"], visual["y"]))
                    new_rect = rotated_sprite.get_rect(center = original_rect.center)
                    window.blit(rotated_sprite, new_rect)
            
        elif current_lobby_screen == "timer_select":
            # --- MODIFIED: Draw a solid grey background instead of the playground ---
            # pygame.draw.rect(window, (80, 80, 80), playground_rect) # <-- OLD
            draw_playground_background() # <-- NEW: Reverted to standard tile
            
        # --- 2. Draw Panel (ALWAYS) ---
        pygame.draw.rect(window, PANEL_COLOR, panel_rect)
        
        # Draw Title (Moved from being inside "main" screen logic)
        if current_lobby_screen == "main":
            TITLE_TEXT = "Coin Chaos"
            SHADOW_COLOR = (0, 0, 0) # Black shadow
            TITLE_COLOR = (255, 255, 255) # White text
            SHADOW_OFFSET = 5
            TITLE_POSITION = (WIDTH // 2, 150)

            shadow_surface = pixel_title_font.render(TITLE_TEXT, True, SHADOW_COLOR)
            shadow_rect = shadow_surface.get_rect(center=(TITLE_POSITION[0] + SHADOW_OFFSET, TITLE_POSITION[1] + SHADOW_OFFSET))
            window.blit(shadow_surface, shadow_rect)
            title_surface = pixel_title_font.render(TITLE_TEXT, True, TITLE_COLOR)
            title_rect = title_surface.get_rect(center=TITLE_POSITION)
            window.blit(title_surface, title_rect)

        # Draw Tabs
        lobby_color = TAB_COLOR_ACTIVE if active_panel_tab == "lobby" else TAB_COLOR_INACTIVE
        chat_color = TAB_COLOR_ACTIVE if active_panel_tab == "chat" else TAB_COLOR_INACTIVE
        pygame.draw.rect(window, lobby_color, lobby_tab_rect)
        pygame.draw.rect(window, chat_color, chat_tab_rect)
        lobby_text_surface = panel_tab_font.render("Lobby", True, TAB_TEXT_COLOR)
        window.blit(lobby_text_surface, lobby_text_surface.get_rect(center=lobby_tab_rect.center))
        chat_text_surface = panel_tab_font.render("Chat", True, TAB_TEXT_COLOR)
        window.blit(chat_text_surface, chat_text_surface.get_rect(center=chat_tab_rect.center))
        pygame.draw.line(window, TAB_LINE_COLOR, (WIDTH, 50), (WIDTH + SIDE_PANEL_WIDTH, 50), 2)
        
        # Draw Tab Content
        if active_panel_tab == "lobby":
            title_y_offset = 70
            active_title_surface = panel_tab_font.render("Active Player", True, TEXT_COLOR)
            window.blit(active_title_surface, (WIDTH + 10, title_y_offset))
            y_offset = title_y_offset + 50
            for pid_str, player_data in players.items():
                sprite = LOBBY_SPRITE_CACHE.get(pid_str) 
                if sprite:
                    small_sprite = pygame.transform.scale(sprite, (35, 45)) 
                    window.blit(small_sprite, (WIDTH + 20, y_offset))
                player_text_surface = panel_list_font.render(player_data['name'], True, tuple(player_data['color']))
                window.blit(player_text_surface, (WIDTH + 70, y_offset + 10))
                y_offset += 60
        elif active_panel_tab == "chat":
            # --- MODIFIED: Chat input is now part of the tab content area ---
            draw_chat_ui(my_player_id, lobby_chat_input_rect.top - 10) # <-- USE LOBBY RECT
            
            # Draw the Input Box (at the bottom)
            input_color = (255, 255, 255) if is_chatting else (100, 100, 100)
            pygame.draw.rect(window, input_color, lobby_chat_input_rect, 2, border_radius=20) # <-- USE LOBBY RECT
            
            pygame.draw.circle(window, input_color, lobby_chat_send_rect.center, 20, 2) # <-- USE LOBBY RECT
            if chat_send_img:
                window.blit(chat_send_img, chat_send_img.get_rect(center=lobby_chat_send_rect.center)) # <-- USE LOBBY RECT
            
            text_to_draw = current_chat_message
            if is_chatting:
                if int(time.time() * 2) % 2 == 0: text_to_draw += "|"
            elif not current_chat_message:
                text_to_draw = "Enter Here..."
                input_color = (100, 100, 100) 
            
            text_surface = chat_input_font.render(text_to_draw, True, input_color)
            text_rect = text_surface.get_rect(midleft=(lobby_chat_input_rect.left + 15, lobby_chat_input_rect.centery)) # <-- USE LOBBY RECT
            
            clip_area = pygame.Rect(lobby_chat_input_rect.left + 15, lobby_chat_input_rect.top, lobby_chat_input_rect.width - 20, lobby_chat_input_rect.height) # <-- USE LOBBY RECT
            original_clip = window.get_clip()
            window.set_clip(clip_area)
            window.blit(text_surface, text_rect)
            window.set_clip(original_clip)
            
        # --- 3. Draw Foreground UI (Screen-specific) ---
        if current_lobby_screen == "main":
            # Draw Start/Wait button
            if my_player_id == host_player_id:
                if lobby_start_button_rect.collidepoint(mouse_pos) and not is_chatting:
                    if mouse_pressed[0]: color = start_color_click
                    else: color = start_color_hover
                else: color = start_color_inactive
                pygame.draw.rect(window, color, lobby_start_button_rect, border_radius=15)
                window.blit(lobby_start_button_text, lobby_start_button_text.get_rect(center=lobby_start_button_rect.center))
            else:
                wait_text_surface = font.render(f"Waiting for host to start...", True, TEXT_COLOR)
                wait_rect = wait_text_surface.get_rect(center=lobby_start_button_rect.center)
                outline_surface = font.render(f"Waiting for host to start...", True, (0,0,0))
                draw_text_outline(outline_surface, wait_rect.topleft)
                window.blit(wait_text_surface, wait_rect)

            # Draw LEAVE Button
            if leave_button_rect.collidepoint(mouse_pos) and not is_chatting:
                color = leave_color_click if mouse_pressed[0] else leave_color_hover
            else:
                color = leave_color_inactive
            pygame.draw.rect(window, color, leave_button_rect, border_radius=15)
            window.blit(leave_text, leave_text.get_rect(center=leave_button_rect.center))

        elif current_lobby_screen == "timer_select":
            # --- Draw Timer Select Screen ---
            
            # Draw Title
            title_surface = pixel_title_font_small.render("Coin Chaos", True, TEXT_COLOR)
            title_rect = title_surface.get_rect(center=(WIDTH // 2, 100))
            shadow_surface = pixel_title_font_small.render("Coin Chaos", True, (0,0,0))
            shadow_rect = shadow_surface.get_rect(center=(title_rect.centerx + 3, title_rect.centery + 3))
            window.blit(shadow_surface, shadow_rect)
            window.blit(title_surface, title_rect)

            # Draw Subtitle
            subtitle_surface = panel_title_font.render("Set Timer", True, TEXT_COLOR)
            subtitle_rect = subtitle_surface.get_rect(center=(WIDTH // 2, 200))
            window.blit(subtitle_surface, subtitle_rect)

            # Draw Back Button
            back_color = leave_color_inactive
            if back_button_rect.collidepoint(mouse_pos):
                back_color = leave_color_hover if not mouse_pressed[0] else leave_color_click
            pygame.draw.circle(window, back_color, back_button_rect.center, 30)
            pygame.draw.polygon(window, (255, 255, 255), [(back_button_rect.centerx + 10, back_button_rect.top + 15), 
                                                          (back_button_rect.left + 15, back_button_rect.centery), 
                                                          (back_button_rect.centerx + 10, back_button_rect.bottom - 15)])
            
            # Draw Timer Boxes
            pygame.draw.rect(window, (50, 50, 50), min_box_rect, border_radius=15)
            pygame.draw.rect(window, (50, 50, 50), sec_box_rect, border_radius=15)
            
            min_text = timer_number_font.render(f"{selected_minutes:02d}", True, TEXT_COLOR)
            sec_text = timer_number_font.render("00", True, (100, 100, 100)) # Disabled seconds
            window.blit(min_text, min_text.get_rect(center=min_box_rect.center))
            window.blit(sec_text, sec_text.get_rect(center=sec_box_rect.center))
            
            # Draw Colon
            colon_text = timer_number_font.render(":", True, TEXT_COLOR)
            window.blit(colon_text, colon_text.get_rect(center=(WIDTH // 2, min_box_rect.centery)))

            # Draw Minute Arrows
            min_up_color = ARROW_COLOR_INACTIVE
            if min_up_rect.collidepoint(mouse_pos):
                min_up_color = ARROW_COLOR_HOVER if not mouse_pressed[0] else ARROW_COLOR_CLICK
            pygame.draw.polygon(window, min_up_color, [(min_up_rect.centerx, min_up_rect.top), 
                                                     (min_up_rect.left + 20, min_up_rect.bottom), 
                                                     (min_up_rect.right - 20, min_up_rect.bottom)])
            
            min_down_color = ARROW_COLOR_INACTIVE
            if min_down_rect.collidepoint(mouse_pos):
                min_down_color = ARROW_COLOR_HOVER if not mouse_pressed[0] else ARROW_COLOR_CLICK
            pygame.draw.polygon(window, min_down_color, [(min_down_rect.centerx, min_down_rect.bottom), 
                                                         (min_down_rect.left + 20, min_down_rect.top), 
                                                         (min_down_rect.right - 20, min_down_rect.top)])

            # Draw Disabled Second Arrows
            pygame.draw.polygon(window, ARROW_COLOR_DISABLED, [(sec_up_rect.centerx, sec_up_rect.top), 
                                                             (sec_up_rect.left + 20, sec_up_rect.bottom), 
                                                             (sec_up_rect.right - 20, sec_up_rect.bottom)])
            pygame.draw.polygon(window, ARROW_COLOR_DISABLED, [(sec_down_rect.centerx, sec_down_rect.bottom), 
                                                             (sec_down_rect.left + 20, sec_down_rect.top), 
                                                             (sec_down_rect.right - 20, sec_down_rect.top)])
            
            # Draw Timer Start Button
            start_color = start_color_inactive
            if timer_start_button_rect.collidepoint(mouse_pos):
                start_color = start_color_hover if not mouse_pressed[0] else start_color_click
            pygame.draw.rect(window, start_color, timer_start_button_rect, border_radius=15)
            window.blit(timer_start_button_text, timer_start_button_text.get_rect(center=timer_start_button_rect.center))


        pygame.display.flip()
        await asyncio.sleep(0.01)

    return None # Return None if loop exits normally (e.g. leave button)


# --- MODIFIED: game_loop (individual facing, IDLE frame only) ---
async def game_loop(websocket, my_player_id, initial_data):
    
    # --- NEW: Initialize state from the data packet ---
    players = initial_data.get("players", {})
    resources = initial_data.get("resources", [])
    game_end_time = initial_data.get("game_end_time", 0)
    game_start_time = initial_data.get("game_start_time", time.time()) 
    
    my_score = 0
    if str(my_player_id) in players:
        my_score = players[str(my_player_id)].get("score", 0)

    global font, coin_sound, KNOWN_PLAYER_COUNT, click_sound, connect_sound, disconnect_sound, walking_sound_channel, walking_sound
    global panel_title_font, panel_text_font, title_font, score_box_font, timer_number_font, panel_leaderboard_font 
    global game_over_sound # <-- NEW: Import global sound
    # --- NEW: Make chat variables global ---
    global is_chatting, current_chat_message, chat_history, chat_message_sound, active_panel_tab, chat_scroll_offset

    running = True

    BUTTON_TEXT_COLOR = (0, 0, 0)
    # --- MODIFIED: Leave Button for New UI ---
    leave_button_rect = pygame.Rect(WIDTH + (SIDE_PANEL_WIDTH // 2) - 60, HEIGHT - 55, 120, 40) # Centered in footer
    leave_color_inactive = (200, 50, 50); leave_color_hover = (255, 100, 100); leave_color_click = (150, 0, 0)
    leave_text = panel_list_font.render("Leave", True, TEXT_COLOR) # Use list font

    # --- NEW: Tab Definitions ---
    lobby_tab_rect = pygame.Rect(WIDTH, 10, 95, 40)
    chat_tab_rect = pygame.Rect(WIDTH + 105, 10, 95, 40)
    
    # --- MODIFIED: Tab colors for new design ---
    TAB_COLOR_INACTIVE = (30, 30, 30)
    TAB_COLOR_ACTIVE = (50, 50, 50)
    TAB_TEXT_COLOR = (255, 255, 255)
    TAB_LINE_COLOR = (100, 100, 100)
    
    local_player_facing_direction = "right" 
    local_is_moving = False 
    
    player_visual_state = {} 
    prev_players_state = {}  
    
    update_game_sprite_cache(players)
    for pid, pdata in players.items():
        player_visual_state[pid] = {"facing": "right"}
        prev_players_state[pid] = {"x": pdata["x"], "y": pdata["y"]}

    while running:
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        
        # --- 1. Check events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False; return None
            
            # --- NEW: Chat Input Handling ---
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if is_chatting:
                        # Send message
                        if current_chat_message:
                            try:
                                await websocket.send(json.dumps({"type": "chat", "message": current_chat_message}))
                                
                                # --- NEW: Local Echo ---
                                my_player_data = players.get(str(my_player_id), {})
                                chat_history.append({
                                    "type": "chat",
                                    "sender_id": str(my_player_id),
                                    "name": my_player_data.get("name", "Me"),
                                    "color": my_player_data.get("color", TEXT_COLOR),
                                    "msg": current_chat_message,
                                    "timestamp": get_chat_timestamp()
                                })
                                if len(chat_history) > CHAT_HISTORY_MAX:
                                    chat_history.pop(0)
                                chat_message_sound.play() # <-- NEW: Play sound on local echo
                                # --- END NEW ---
                                
                            except websockets.exceptions.ConnectionClosed:
                                print("Failed to send chat."); running = False; return None
                        current_chat_message = ""
                        is_chatting = False
                    else:
                        # Activate chat (if chat tab is active)
                        if active_panel_tab == "chat":
                            is_chatting = True
                elif is_chatting:
                    if event.key == pygame.K_BACKSPACE:
                        current_chat_message = current_chat_message[:-1]
                    elif event.unicode.isprintable(): # Only add printable chars
                         if chat_input_font.size(current_chat_message + event.unicode)[0] < chat_input_rect.width - 20:
                            current_chat_message += event.unicode
            # --- END NEW ---
            
            # --- NEW: Scroll Wheel Handling (Game) ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                # --- MODIFIED: Define the chat history area for new layout ---
                chat_history_area_rect = pygame.Rect(WIDTH, 60, SIDE_PANEL_WIDTH, (HEIGHT - 230) - 60) # From tabs to input box
                
                if active_panel_tab == 'chat' and chat_history_area_rect.collidepoint(event.pos):
                    if event.button == 4: # Scroll Up
                        chat_scroll_offset = max(0, chat_scroll_offset - 1)
                        continue # This click was for scrolling
                    elif event.button == 5: # Scroll Down
                        chat_scroll_offset += 1
                        continue # This click was for scrolling
                    # --- BUG FIX: Removed 'continue' from here. ---
                    # A left-click (button 1) should now fall through.

            # --- ENTIRE MOUSEBUTTONDOWN HANDLER RE-ORDERED ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                
                # --- 1. Handle Tab Clicks FIRST ---
                # These should work regardless of chat state.
                if lobby_tab_rect.collidepoint(event.pos):
                    active_panel_tab = "lobby"
                    is_chatting = False # Deactivate chat when switching tabs
                    click_sound.play()
                    continue # Done with this click
                if chat_tab_rect.collidepoint(event.pos):
                    active_panel_tab = "chat"
                    is_chatting = True # Auto-focus chat
                    click_sound.play()
                    continue # Done with this click

                # --- 2. Handle Chat-Related Clicks ---
                if is_chatting:
                    # Check for send button click
                    if chat_send_rect.collidepoint(event.pos):
                        if current_chat_message:
                            try:
                                await websocket.send(json.dumps({"type": "chat", "message": current_chat_message}))
                                
                                # --- NEW: Local Echo ---
                                my_player_data = players.get(str(my_player_id), {})
                                chat_history.append({
                                    "type": "chat",
                                    "sender_id": str(my_player_id),
                                    "name": my_player_data.get("name", "Me"),
                                    "color": my_player_data.get("color", TEXT_COLOR),
                                    "msg": current_chat_message,
                                    "timestamp": get_chat_timestamp()
                                })
                                if len(chat_history) > CHAT_HISTORY_MAX:
                                    chat_history.pop(0)
                                chat_message_sound.play() # <-- NEW: Play sound on local echo
                                # --- END NEW ---
                                
                            except websockets.exceptions.ConnectionClosed:
                                print("Failed to send chat."); running = False; return None
                        current_chat_message = ""
                        # Don't deactivate chat, just clear message
                        continue # Done with this click
                    
                    # Check if click is on the input box
                    if chat_input_rect.collidepoint(event.pos):
                        # User is just focusing the input box, do nothing
                        continue # Done with this click

                    # --- 3. Clicked *outside* chat UI ---
                    # Deactivate chat and let the click be processed
                    # by other buttons (like "Leave" or "Start")
                    is_chatting = False
                    # --- DO NOT CONTINUE HERE ---
                    # Let the click fall through to the buttons below

                # --- 4. Handle Other Buttons (Leave, Start, etc.) ---
                if leave_button_rect.collidepoint(event.pos):
                    click_sound.play(); running = False; return None
            # --- END OF RE-ORDERED MOUSEBUTTONDOWN HANDLER ---


        time_to_start = game_start_time - time.time()
        game_has_started = time_to_start <= 0

        # --- 2. MODIFIED: Handle player input (updates LOCAL variables) ---
        local_is_moving = False # Assume not moving
        
        # --- MODIFIED: Only allow movement if game has started AND not chatting ---
        if game_has_started and not is_chatting:
            keys = pygame.key.get_pressed()
            dx, dy = 0, 0
            
            if keys[pygame.K_LEFT] or keys[pygame.K_a]: # <-- ADDED
                dx = -PLAYER_SPEED
                local_player_facing_direction = "right" # Your custom direction
                local_is_moving = True
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]: # <-- ADDED
                dx = PLAYER_SPEED
                local_player_facing_direction = "left" # Your custom direction
                local_is_moving = True
            if keys[pygame.K_UP] or keys[pygame.K_w]: # <-- ADDED
                dy = -PLAYER_SPEED
                local_is_moving = True
            if keys[pygame.K_DOWN] or keys[pygame.K_s]: # <-- ADDED
                dy = PLAYER_SPEED
                local_is_moving = True
                
            if dx != 0 or dy != 0:
                try:
                    await websocket.send(json.dumps({"type": "move", "dx": dx, "dy": dy}))
                except websockets.exceptions.ConnectionClosed:
                    running = False; return None 
        
        # --- 3. Receive updates ---
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=WEBSOCKET_SEND_TIMEOUT)
            data = json.loads(response)

            # --- NEW: Handle NEW Chat Broadcast ---
            if data.get("type") == "chat_broadcast":
                chat_history.append({
                    "type": "chat",
                    "sender_id": data.get("sender_id"),
                    "name": data.get("sender_name", "System"),
                    "color": data.get("sender_color", (200, 200, 200)),
                    "msg": data.get("message", ""),
                    "timestamp": data.get("timestamp", "")
                })
                if len(chat_history) > CHAT_HISTORY_MAX:
                    chat_history.pop(0)
                if not is_chatting:
                    chat_message_sound.play()
                continue
            # --- NEW: Handle System Message ---
            elif data.get("type") == "system_message":
                chat_history.append({
                    "type": "system",
                    "msg": data.get("message", ""),
                    "timestamp": data.get("timestamp", "")
                })
                if len(chat_history) > CHAT_HISTORY_MAX:
                    chat_history.pop(0)
                #chat_message_sound.play()
                continue
            # --- END NEW ---

            players = data.get("players", {})
            resources = data.get("resources", [])
            game_end_time = data.get("game_end_time", 0)
            
            update_game_sprite_cache(players)
            update_lobby_sprite_cache(players) # <-- ADDED THIS LINE
            new_player_count = len(players)
            if new_player_count > KNOWN_PLAYER_COUNT: connect_sound.play()
            elif new_player_count < KNOWN_PLAYER_COUNT: disconnect_sound.play()
            KNOWN_PLAYER_COUNT = new_player_count
            
            player_data = players.get(str(my_player_id), {})
            new_score = player_data.get("score", 0)
            if new_score > my_score: coin_sound.play()
            my_score = new_score
            
            # --- NEW: Update visual state for ALL players ---
            for player_id_str, player_data in players.items():
                if player_id_str not in player_visual_state:
                    # Player just joined
                    player_visual_state[player_id_str] = {"facing": "right"}
                    prev_players_state[player_id_str] = {"x": player_data["x"], "y": player_data["y"]}
                
                current_visuals = player_visual_state[player_id_str]
                prev_state = prev_players_state[player_id_str]

                new_facing = current_visuals["facing"] 
                
                if int(player_id_str) == my_player_id:
                    # --- MODIFIED: Only update facing if NOT chatting ---
                    if not is_chatting:
                        new_facing = local_player_facing_direction
                else:
                    dx = player_data["x"] - prev_state["x"]
                    
                    if dx > 0:
                        new_facing = "left" # Your "right" sprite
                    elif dx < 0:
                        new_facing = "right" # Your "left" sprite
                
                player_visual_state[player_id_str] = {"facing": new_facing}
            
            for player_id_str, player_data in players.items():
                prev_players_state[player_id_str] = {"x": player_data["x"], "y": player_data["y"]}

            if data.get("game_state") == "leaderboard":
                game_over_sound.play() # <-- NEW: Play sound
                running = False; break 
        except asyncio.TimeoutError:
            pass 
        except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError) as e:
            print(f"Connection error in game: {e}"); running = False; return None 

        
            
        # --- 5. Draw the UI ---
        draw_playground_background()
        pygame.draw.rect(window, PANEL_COLOR, panel_rect)

        # --- 6. MODIFIED: Draw players (IDLE frame only) ---
        for player_id_str, player in players.items():
            visuals = player_visual_state.get(player_id_str, {"facing": "right"})
            current_facing = visuals['facing']
            animation_frame_index = 0
            
            sprite_list = None
            if current_facing == "left":
                sprite_list = GAME_SPRITE_CACHE_L.get(player_id_str)
            else:
                sprite_list = GAME_SPRITE_CACHE_R.get(player_id_str)
            
            if sprite_list:
                sprite = sprite_list[animation_frame_index]
                if sprite:
                    sprite_rect = sprite.get_rect(center=(player["x"], player["y"]))
                    window.blit(sprite, sprite_rect)
                else:
                    pygame.draw.circle(window, tuple(player["color"]), (player["x"], player["y"]), PLAYER_SIZE // 2)
            else:
                pygame.draw.circle(window, tuple(player["color"]), (player["x"], player["y"]), PLAYER_SIZE // 2)

            text_content = f"{player['name']}: {player['score']}"
            text_surface = font.render(text_content, True, TEXT_COLOR)
            text_rect = text_surface.get_rect(center=(player["x"], player["y"] - PLAYER_SIZE // 2 - 25))
            
            outline_surface = font.render(text_content, True, (0,0,0))
            # Use a simpler outline for in-game text
            for dx in [-1, 1]:
                for dy in [-1, 1]:
                    window.blit(outline_surface, (text_rect.x + dx, text_rect.y + dy))
            
            window.blit(text_surface, text_rect)
        
        for resource in resources:
            window.blit(coin_sprite, (resource["x"] - RESOURCE_SIZE // 2, resource["y"] - RESOURCE_SIZE // 2))

        # --- NEW: Tab Drawing and Content Switching ---
        
        # 1. Draw the Tabs
        lobby_color = TAB_COLOR_ACTIVE if active_panel_tab == "lobby" else TAB_COLOR_INACTIVE
        chat_color = TAB_COLOR_ACTIVE if active_panel_tab == "chat" else TAB_COLOR_INACTIVE
        
        pygame.draw.rect(window, lobby_color, lobby_tab_rect)
        pygame.draw.rect(window, chat_color, chat_tab_rect)
        
        lobby_text_surface = panel_tab_font.render("Lobby", True, TAB_TEXT_COLOR)
        lobby_text_rect = lobby_text_surface.get_rect(center=lobby_tab_rect.center)
        window.blit(lobby_text_surface, lobby_text_rect)
        
        chat_text_surface = panel_tab_font.render("Chat", True, TAB_TEXT_COLOR)
        chat_text_rect = chat_text_surface.get_rect(center=chat_tab_rect.center)
        window.blit(chat_text_surface, chat_text_rect)

        # Draw the dividing line
        pygame.draw.line(window, TAB_LINE_COLOR, (WIDTH, 50), (WIDTH + SIDE_PANEL_WIDTH, 50), 2)
        
        # 2. Draw Content Based on Active Tab
        # --- MODIFIED: This area is now dedicated to tab content ---
        if active_panel_tab == "lobby":
            # --- MODIFIED: Draw the new Leaderboard UI ---
            title_y_offset = 70 # Y-position for the title
            active_title_surface = panel_tab_font.render("Leaderboard", True, TEXT_COLOR)
            window.blit(active_title_surface, (WIDTH + 20, title_y_offset))
            
            y_offset = title_y_offset + 50
            sorted_players = sorted(players.items(), key=lambda p: p[1]["score"], reverse=True)
            for i, (player_id, player) in enumerate(sorted_players):
                # Avatar
                sprite = LOBBY_SPRITE_CACHE.get(player_id) 
                if sprite:
                    small_sprite = pygame.transform.scale(sprite, (35, 45)) 
                    window.blit(small_sprite, (WIDTH + 20, y_offset - 5)) # -5 to align
                
                # Name
                player_text_surface = panel_leaderboard_font.render( # <-- USE NEW FONT
                    player['name'], 
                    True, 
                    tuple(player['color'])
                )
                window.blit(player_text_surface, (WIDTH + 70, y_offset + 5)) # <-- Added 5px Y offset for centering
                
                # --- Score Box ---
                score_str = str(player['score'])
                score_text_surface = score_box_font.render(score_str, True, (0,0,0)) # Black text
                score_text_rect = score_text_surface.get_rect()
                
                box_width = max(30, score_text_rect.width + 10)
                box_height = 25
                box_x = WIDTH + SIDE_PANEL_WIDTH - box_width - 15
                box_y = y_offset
                
                pygame.draw.rect(window, (255, 255, 255), (box_x, box_y, box_width, box_height), border_radius=8)
                score_text_rect.center = (box_x + box_width // 2, box_y + box_height // 2)
                window.blit(score_text_surface, score_text_rect)
                # --- End Score Box ---
                
                y_offset += 50
        
        elif active_panel_tab == "chat":
            # --- Draw the NEW Chat UI ---
            # This function now draws the history
            draw_chat_ui(my_player_id, chat_input_rect.top - 10) # <-- USE GLOBAL RECT
            
            # --- MODIFIED: Draw the input box here ---
            input_color = (255, 255, 255) if is_chatting else (100, 100, 100)
            pygame.draw.rect(window, input_color, chat_input_rect, 2, border_radius=20)
            
            pygame.draw.circle(window, input_color, chat_send_rect.center, 20, 2)
            if chat_send_img:
                window.blit(chat_send_img, chat_send_img.get_rect(center=chat_send_rect.center))
            
            text_to_draw = current_chat_message
            if is_chatting:
                if int(time.time() * 2) % 2 == 0: text_to_draw += "|"
            elif not current_chat_message:
                text_to_draw = "Enter Here..."
                input_color = (100, 100, 100) 
            
            text_surface = chat_input_font.render(text_to_draw, True, input_color)
            text_rect = text_surface.get_rect(midleft=(chat_input_rect.left + 15, chat_input_rect.centery))
            
            clip_area = pygame.Rect(chat_input_rect.left + 15, chat_input_rect.top, chat_input_rect.width - 20, chat_input_rect.height)
            original_clip = window.get_clip()
            window.set_clip(clip_area)
            window.blit(text_surface, text_rect)
            window.set_clip(original_clip)
            
        # --- END MODIFIED ---
        
        # --- MODIFIED: Draw Timer and Leave Button (part of new UI) ---
        # This footer section is now drawn ALWAYS, regardless of the tab.
        
        # Draw the divider line above "Time Left"
        divider_y = HEIGHT - 190 
        pygame.draw.line(window, TAB_LINE_COLOR, (WIDTH, divider_y), (WIDTH + SIDE_PANEL_WIDTH, divider_y), 2)

        if game_end_time > 0:
            time_remaining = max(0, game_end_time - time.time())
            minutes = int(time_remaining // 60); seconds = int(time_remaining % 60)
            timer_text_str = f"{minutes:02d}:{seconds:02d}"
            timer_color = (255, 0, 0) if time_remaining < 10 else TEXT_COLOR
            
            timer_title_surface = panel_tab_font.render("Time Left", True, TEXT_COLOR)
            # --- MODIFIED: Moved title up ---
            title_rect = timer_title_surface.get_rect(center=(WIDTH + SIDE_PANEL_WIDTH // 2, divider_y + 30)) # Was + 35
            window.blit(timer_title_surface, title_rect)
            
            timer_text_surface = timer_number_font.render(timer_text_str, True, timer_color)
            # --- MODIFIED: Moved timer up significantly ---
            text_rect = timer_text_surface.get_rect(center=(WIDTH + SIDE_PANEL_WIDTH // 2, divider_y + 65)) # Was + 80
            window.blit(timer_text_surface, text_rect)
        
        # Draw Leave Button (position is unchanged, but now has space above it)
        if leave_button_rect.collidepoint(mouse_pos) and not is_chatting:
            color = leave_color_click if mouse_pressed[0] else leave_color_hover
        else:
            color = leave_color_inactive
        pygame.draw.rect(window, color, leave_button_rect, border_radius=15)
        window.blit(leave_text, leave_text.get_rect(center=leave_button_rect.center))
        
        # --- Countdown Overlay (Unchanged) ---
        if not game_has_started:
            countdown_num = int(time_to_start) + 1
            countdown_text_str = f"Starting in {countdown_num}..."
            if countdown_num <= 0:
                countdown_text_str = "GO!"
                
            countdown_text_surface = title_font.render(countdown_text_str, True, TEXT_COLOR)
            countdown_rect = countdown_text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))
            window.blit(overlay, (0, 0))
            
            outline_surface = title_font.render(countdown_text_str, True, (0,0,0))
            # Use a simpler outline
            for dx in [-2, 2]:
                for dy in [-2, 2]:
                    window.blit(outline_surface, (countdown_rect.x + dx, countdown_rect.y + dy))
            
            window.blit(countdown_text_surface, countdown_rect)

        pygame.display.flip()
        await asyncio.sleep(0.01)
    
    if walking_sound_channel:
        walking_sound_channel.stop()
    return players


# --- MODIFIED: show_leaderboard_screen (Uses frame 0) ---
def show_leaderboard_screen(final_players):
    global font, window, clock, title_font
    global GAME_SPRITE_CACHE_R # Use R cache for consistency
    
    title_text_surface = title_font.render("ROUND OVER", True, (255, 0, 0))
    title_rect = title_text_surface.get_rect(center=(WIDTH // 2, 100))
    
    sorted_player_data = sorted(final_players.values(), key=lambda p: p["score"], reverse=True)
    
    start_ticks = pygame.time.get_ticks()
    DURATION = 10000 

    running = True
    while running:
        elapsed = pygame.time.get_ticks() - start_ticks
        if elapsed > DURATION: running = False 
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
        
        draw_playground_background()
        pygame.draw.rect(window, PANEL_COLOR, panel_rect)
        
        window.blit(title_text_surface, title_rect)
        
        time_left_sec = (DURATION - elapsed) // 1000 + 1
        return_text_surface = font.render(f"Game exiting in {time_left_sec}...", True, TEXT_COLOR)
        return_rect = return_text_surface.get_rect(center=(WIDTH + SIDE_PANEL_WIDTH // 2, HEIGHT - 50))
        window.blit(return_text_surface, return_rect)

        y_offset = 200
        for i, player_data in enumerate(sorted_player_data):
            player_id_str = None
            for pid, pdata in final_players.items():
                if pdata["name"] == player_data["name"]: 
                    player_id_str = pid
                    break
            
            # --- MODIFIED: Get idle frame (index 0) ---
            sprite_list = GAME_SPRITE_CACHE_R.get(player_id_str) 
            if sprite_list:
                sprite = sprite_list[0] # Get idle frame
                if sprite:
                    big_sprite = pygame.transform.scale(sprite, (PLAYER_SIZE * 1.5, int(PLAYER_SIZE * 1.1 * 1.5)))
                    sprite_rect = big_sprite.get_rect(center=(WIDTH // 2 - 150, y_offset))
                    window.blit(big_sprite, sprite_rect)

            line_text_str = f"#{i+1}: {player_data['name']} - {player_data['score']} points"
            line_color = tuple(player_data['color'])
            line_text_surface = font.render(line_text_str, True, line_color)
            line_rect = line_text_surface.get_rect(midleft=(WIDTH // 2 - 100, y_offset))
            outline_text_surface = font.render(line_text_str, True, (0,0,0))
            # Use simpler outline
            for dx in [-1, 1]:
                 for dy in [-1, 1]:
                    window.blit(outline_text_surface, (line_rect.x + dx, line_rect.y + dy))
            window.blit(line_text_surface, line_rect)
            y_offset += 100 
        
        # --- NEW: Draw final chat history ---
        # Note: This won't have a player ID, so 'my_player_id' is 0 (all messages will be 'left')
        if active_panel_tab == "chat":
             draw_chat_ui(0, chat_input_rect.top - 10) # <-- USE GLOBAL RECT
             # --- MODIFIED: Must also draw the input box ---
             input_color = (100, 100, 100) # Disabled
             pygame.draw.rect(window, input_color, chat_input_rect, 2, border_radius=20) # <-- USE GLOBAL RECT
             pygame.draw.circle(window, input_color, chat_send_rect.center, 20, 2) # <-- USE GLOBAL RECT
             if chat_send_img:
                window.blit(chat_send_img, chat_send_img.get_rect(center=chat_send_rect.center)) # <-- USE GLOBAL RECT

        pygame.display.flip()
        clock.tick(FRAME_RATE)

# --- MODIFIED: Main function (clears all caches) ---
async def main():
    global LOBBY_VISUALS, LOBBY_SPRITE_CACHE, GAME_SPRITE_CACHE_L, GAME_SPRITE_CACHE_R
    # --- NEW: Clear chat history on start ---
    global chat_history, is_chatting, current_chat_message
    
    player_name = input("Please enter your name: ")
    lobby_password = input("Enter lobby password: ") 

    #uri = "ws://localhost:8765" # Localhost for testing
    uri = "wss://v3-production-5d5a.up.railway.app" # Deployed server
    
    print(f"Connecting to {uri}...")
    final_players = None
    my_player_id = 0 # Default

    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "join", "name": player_name, "password": lobby_password}))
            response_str = await websocket.recv()
            response = json.loads(response_str)

            if response.get("type") == "join_success":
                my_player_id = response.get("player_id") # Get the real player ID
                print(f"Successfully joined lobby! You are Player {my_player_id}.")
                KNOWN_PLAYER_COUNT = 1
                
                # --- NEW: Add welcome message to chat ---
                chat_history.append({"type": "system", "msg": f"Welcome, {player_name}!"})

                initial_game_data = await lobby_loop(websocket, my_player_id)
                
                if initial_game_data: 
                    print("Lobby finished, starting game...")
                    
                    LOBBY_VISUALS.clear()
                    LOBBY_SPRITE_CACHE.clear()
                    GAME_SPRITE_CACHE_L.clear() 
                    GAME_SPRITE_CACHE_R.clear()
                    # --- NEW: Clear chat state variables for game ---
                    is_chatting = False
                    current_chat_message = ""
                    chat_history.append({"type": "system", "msg": "Game started! GO!"})
                    
                    final_players = await game_loop(websocket, my_player_id, initial_game_data)
                else:
                    print("Left lobby, not starting game.")
                
            else:
                print(f"Failed to join lobby: {response.get('reason', 'Unknown error')}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed (Game Over or Left): {e.code} {e.reason}")
    except ConnectionRefusedError:
        print(f"Connection failed. Is the server running at {uri}?")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback 
        traceback.print_exc()
    
    finally:
        if final_players is not None:
            print("Game over, showing leaderboard...")
            chat_history.append({"type": "system", "msg": "Round over!"})
            show_leaderboard_screen(final_players)
        
        print("Game has ended. Please restart to play again.")
        pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
