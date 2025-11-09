"""
=============================================================================
COIN CHAOS - MULTIPLAYER GAME SERVER
=============================================================================
This server manages all game logic for the multiplayer coin collection game.
It handles player connections, game state, coin spawning, and chat messages.

ARCHITECTURE:
- Uses WebSockets for real-time bidirectional communication
- Asynchronous programming with asyncio for handling multiple clients
- Centralized server authority (server controls all game logic)
- Lock-based synchronization to prevent race conditions
=============================================================================
"""

import asyncio  # For asynchronous programming (handling multiple clients at once)
import json     # For converting Python objects to/from JSON format
import random   # For random number generation (spawn positions, colors)
import websockets  # For WebSocket server functionality
import os       # For reading environment variables (password, port)
import time     # For timestamps and game timer

# =============================================================================
# GAME CONSTANTS
# These define the game world dimensions and gameplay parameters
# =============================================================================
WIDTH, HEIGHT = 800, 600           # Game world size in pixels
RESOURCE_SPAWN_TIME = 5            # Seconds between coin spawns
PLAYER_SIZE = 64                   # Player hitbox size in pixels
RESOURCE_SIZE = 32                 # Coin hitbox size in pixels

# =============================================================================
# SERVER STATE VARIABLES
# These variables store all information about the current game session
# =============================================================================

# --- Player and Game Object Storage ---
players = {}          # Dictionary: {player_id: {x, y, score, name, color}}
resources = []        # List of coins: [{id, x, y}, {id, x, y}, ...]
next_player_id = 1    # Counter for assigning unique player IDs
next_resource_id = 1  # Counter for assigning unique coin IDs

# --- Connection Management ---
clients = {}  # Dictionary: {player_id: websocket_connection}
              # Maps each player to their WebSocket connection

# --- Security ---
LOBBY_PASSWORD = ""  # Server password (loaded from environment variable)

# --- Game State Management ---
game_state = "lobby"      # Current game phase: "lobby", "playing", or "leaderboard"
host_player_id = 0        # ID of the player who can start the game
game_start_time = 0       # Unix timestamp when game started
game_end_time = 0         # Unix timestamp when game will end

# --- Thread Safety ---
STATE_LOCK = asyncio.Lock()  # Prevents multiple clients from modifying 
                             # game state simultaneously (race conditions)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_chat_timestamp():
    """
    Creates a formatted timestamp for chat messages.
    
    Returns:
        str: Time in 24-hour format, e.g., "14:32"
    
    Example:
        If current time is 2:30 PM → returns "14:30"
    """
    return time.strftime("%H:%M", time.localtime())


async def broadcast_message(message_payload, skip_player_id=None):
    """
    Sends a message to all connected clients (or all except one).
    
    This is the core communication function for sending updates to players.
    
    Args:
        message_payload (dict): The data to send (will be converted to JSON)
        skip_player_id (int, optional): If provided, don't send to this player
                                       (useful for not echoing messages back)
    
    Example:
        # Send a system message to everyone
        await broadcast_message({"type": "system", "msg": "Game starting!"})
        
        # Send to everyone except player 3
        await broadcast_message({"type": "chat", "msg": "Hi!"}, skip_player_id=3)
    """
    # If no clients are connected, do nothing
    if not clients:
        return
    
    # Convert the Python dictionary to a JSON string
    message_json = json.dumps(message_payload)
    
    # Loop through all connected clients
    for client_id, client_websocket in list(clients.items()):
        # Skip the specified player (if any)
        if client_id == skip_player_id:
            continue
        
        try:
            # Send the JSON message through the WebSocket
            await client_websocket.send(message_json)
        except websockets.exceptions.ConnectionClosed:
            # If connection is closed, we'll handle it in the disconnect logic
            pass


async def broadcast_updates():
    """
    Sends the current game state to all players.
    
    This is called whenever the game state changes (player moves, coin spawns, etc.)
    It packages all relevant game data and sends it to every connected client.
    
    The clients use this data to render the game on their screens.
    """
    # Package all game data into a single dictionary
    update_payload = {
        "type": "update",              # Message type identifier
        "players": players,             # All player positions, scores, names, colors
        "resources": resources,         # All coin positions
        "game_state": game_state,       # Current phase: "lobby", "playing", "leaderboard"
        "host_player_id": host_player_id,  # Who can start the game
        "game_end_time": game_end_time     # When the game will end
    }
    
    # Send to all clients
    await broadcast_message(update_payload)


# =============================================================================
# GAME TIMER SYSTEM
# =============================================================================

async def end_game_timer(seconds_to_wait):
    """
    Manages the game's lifecycle after it starts.
    
    This function runs in the background and handles:
    1. Waiting for the game duration
    2. Transitioning to the leaderboard
    3. Disconnecting all players after viewing results
    4. Resetting the server for a new game
    
    Args:
        seconds_to_wait (int): How long the game should last
    
    Flow:
        START → Wait (game duration) → Show Leaderboard (10s) → Disconnect All → Reset
    """
    global game_state, host_player_id, next_player_id
    
    # -------------------------------------------------------------------------
    # PHASE 1: Wait for game to complete
    # -------------------------------------------------------------------------
    print(f"[TIMER] Game will last {seconds_to_wait} seconds")
    await asyncio.sleep(seconds_to_wait)
    
    # -------------------------------------------------------------------------
    # PHASE 2: Transition to leaderboard
    # -------------------------------------------------------------------------
    # Acquire the lock to safely modify game state
    await STATE_LOCK.acquire()
    try:
        # Only transition if we're still playing (game wasn't manually stopped)
        if game_state == "playing":
            print("[TIMER] Time's up! Moving to leaderboard...")
            game_state = "leaderboard"
            resources.clear()  # Remove all coins from the map
    finally:
        # Always release the lock, even if an error occurs
        STATE_LOCK.release()
    
    # Notify all clients to show the leaderboard
    await broadcast_updates()
    
    # -------------------------------------------------------------------------
    # PHASE 3: Display leaderboard for 10 seconds
    # -------------------------------------------------------------------------
    print("[TIMER] Showing leaderboard for 10 seconds...")
    await asyncio.sleep(10)
    
    # -------------------------------------------------------------------------
    # PHASE 4: Disconnect all players and reset server
    # -------------------------------------------------------------------------
    await STATE_LOCK.acquire()
    try:
        print("[TIMER] Leaderboard time over. Resetting server...")
        
        # Close all client connections
        for client_id, client_websocket in list(clients.items()):
            try:
                # Code 1000 = Normal Closure (clean disconnect)
                await client_websocket.close(code=1000, reason="Game Over")
            except websockets.exceptions.ConnectionClosed:
                # Client already disconnected
                pass
        
        # Reset all server state for the next game
        players.clear()           # Remove all player data
        clients.clear()           # Clear connection tracking
        resources.clear()         # Remove all coins
        game_state = "lobby"      # Return to lobby phase
        host_player_id = 0        # Clear host
        next_player_id = 1        # Reset player ID counter
        
        print("[TIMER] Server reset complete. Ready for new game.")
        
    finally:
        STATE_LOCK.release()


# =============================================================================
# CLIENT CONNECTION HANDLER
# This is the main function that manages each player's connection
# =============================================================================

async def handle_client(websocket):
    """
    Handles a single player's connection from start to finish.
    
    This function is called once for each player that connects.
    It manages three phases:
    1. JOIN: Player authentication and lobby entry
    2. MESSAGE LOOP: Ongoing game communication
    3. DISCONNECT: Cleanup when player leaves
    
    Args:
        websocket: The WebSocket connection for this specific player
    """
    # These variables track this specific player's information
    global next_player_id, host_player_id, game_state, game_end_time, game_start_time
    
    player_id = 0        # Will be assigned during join phase
    player_name = ""     # Player's display name

    try:
        # =====================================================================
        # PHASE 1: PLAYER JOIN
        # =====================================================================
        
        # Wait for the player's join request
        join_message = await websocket.recv()
        join_data = json.loads(join_message)

        # Check if this is a valid join request with correct password
        if join_data.get("type") == "join" and join_data.get("password") == LOBBY_PASSWORD:
            
            # Lock game state to prevent race conditions
            await STATE_LOCK.acquire()
            try:
                # -------------------------------------------------------------
                # Prevent joining games in progress
                # -------------------------------------------------------------
                if game_state != "lobby":
                    # Send failure message to client
                    await websocket.send(json.dumps({
                        "type": "join_fail", 
                        "reason": "Game is already in progress."
                    }))
                    # Close connection
                    await websocket.close()
                    return
                
                # -------------------------------------------------------------
                # Assign player ID and extract join data
                # -------------------------------------------------------------
                player_id = next_player_id
                next_player_id += 1  # Increment for next player
                player_name = join_data.get("name", f"Player{player_id}")
                
                # Generate random color if none provided
                r = random.randint(100, 255)
                g = random.randint(100, 255)
                b = random.randint(100, 255)
                player_color = join_data.get("color", (r, g, b))

                # -------------------------------------------------------------
                # Create player data and add to game
                # -------------------------------------------------------------
                players[player_id] = {
                    "x": random.randint(PLAYER_SIZE, WIDTH - PLAYER_SIZE),  # Random X position
                    "y": random.randint(PLAYER_SIZE, HEIGHT - PLAYER_SIZE),  # Random Y position
                    "score": 0,                   # Starting score
                    "name": player_name,          # Display name
                    "color": player_color         # RGB color tuple
                }
                
                # Store the WebSocket connection for this player
                clients[player_id] = websocket

                # -------------------------------------------------------------
                # Assign host if this is the first player
                # -------------------------------------------------------------
                if len(players) == 1:
                    host_player_id = player_id
                    print(f"[JOIN] Player {player_id} ({player_name}) is the host.")
                
                print(f"[JOIN] Player {player_id} ({player_name}) joined the lobby.")
                
            finally:
                # Always release the lock
                STATE_LOCK.release()
            
            # -----------------------------------------------------------------
            # Send success confirmation to the joining player
            # -----------------------------------------------------------------
            await websocket.send(json.dumps({
                "type": "join_success", 
                "player_id": player_id
            }))
            
            # Notify all players of the new game state
            await broadcast_updates()
            
            # -----------------------------------------------------------------
            # Broadcast join announcement to chat
            # -----------------------------------------------------------------
            join_msg_payload = {
                "type": "system_message",
                "message": f"{player_name} has joined!",
                "timestamp": get_chat_timestamp()
            }
            await broadcast_message(join_msg_payload)
            
        else:
            # Password was incorrect
            await websocket.send(json.dumps({
                "type": "join_fail", 
                "reason": "Wrong password"
            }))
            await websocket.close()
            return

        # =====================================================================
        # PHASE 2: MESSAGE LOOP
        # This loop processes all messages from the player during the game
        # =====================================================================
        
        async for message in websocket:
            # Decode the incoming message
            data = json.loads(message)
            broadcast_needed = False  # Track if we need to update all clients

            # Lock the game state while processing
            await STATE_LOCK.acquire()
            try:
                # =============================================================
                # MESSAGE TYPE: MOVE
                # Player is trying to move their character
                # =============================================================
                if data["type"] == "move":
                    # Only process moves during gameplay
                    if game_state == "playing" and player_id in players:
                        
                        player = players[player_id]
                        old_x, old_y = player["x"], player["y"]
                        
                        # ---------------------------------------------------------
                        # HORIZONTAL MOVEMENT (X-axis)
                        # ---------------------------------------------------------
                        potential_x = old_x + data["dx"]  # New X position
                        collided_player_id_x = None
                        
                        # Check collision with other players on X-axis
                        for other_id, other_player in players.items():
                            if other_id == player_id:
                                continue  # Skip self
                            
                            # Check if hitboxes overlap
                            if (abs(potential_x - other_player["x"]) < PLAYER_SIZE and 
                                abs(old_y - other_player["y"]) < PLAYER_SIZE):
                                collided_player_id_x = other_id
                                break
                        
                        # Handle X-axis collision (push mechanics)
                        if collided_player_id_x is not None:
                            target_player = players[collided_player_id_x]
                            target_potential_x = target_player["x"] + data["dx"]
                            is_target_x_blocked = False
                            
                            # Check if target can be pushed (within bounds)
                            if not (PLAYER_SIZE // 2 <= target_potential_x <= WIDTH - PLAYER_SIZE // 2):
                                is_target_x_blocked = True
                            
                            # Check if target would collide with a third player
                            if not is_target_x_blocked:
                                for p3_id, p3_player in players.items():
                                    if p3_id == player_id or p3_id == collided_player_id_x:
                                        continue
                                    
                                    if (abs(target_potential_x - p3_player["x"]) < PLAYER_SIZE and 
                                        abs(target_player["y"] - p3_player["y"]) < PLAYER_SIZE):
                                        is_target_x_blocked = True
                                        break
                            
                            # Apply push if not blocked
                            if not is_target_x_blocked:
                                target_player["x"] = target_potential_x
                                player["x"] = potential_x
                        else:
                            # No collision, move freely
                            player["x"] = potential_x
                        
                        # ---------------------------------------------------------
                        # VERTICAL MOVEMENT (Y-axis)
                        # Same logic as X-axis, but for vertical movement
                        # ---------------------------------------------------------
                        potential_y = old_y + data["dy"]
                        collided_player_id_y = None
                        
                        for other_id, other_player in players.items():
                            if other_id == player_id:
                                continue
                            
                            if (abs(player["x"] - other_player["x"]) < PLAYER_SIZE and 
                                abs(potential_y - other_player["y"]) < PLAYER_SIZE):
                                collided_player_id_y = other_id
                                break
                        
                        if collided_player_id_y is not None:
                            target_player = players[collided_player_id_y]
                            target_potential_y = target_player["y"] + data["dy"]
                            is_target_y_blocked = False
                            
                            if not (PLAYER_SIZE // 2 <= target_potential_y <= HEIGHT - PLAYER_SIZE // 2):
                                is_target_y_blocked = True
                            
                            if not is_target_y_blocked:
                                for p3_id, p3_player in players.items():
                                    if p3_id == player_id or p3_id == collided_player_id_y:
                                        continue
                                    
                                    if (abs(target_player["x"] - p3_player["x"]) < PLAYER_SIZE and 
                                        abs(target_potential_y - p3_player["y"]) < PLAYER_SIZE):
                                        is_target_y_blocked = True
                                        break
                            
                            if not is_target_y_blocked:
                                target_player["y"] = target_potential_y
                                player["y"] = potential_y
                        else:
                            player["y"] = potential_y
                        
                        # ---------------------------------------------------------
                        # Enforce world boundaries for all players
                        # ---------------------------------------------------------
                        for p in players.values():
                            p["x"] = max(PLAYER_SIZE // 2, min(WIDTH - PLAYER_SIZE // 2, p["x"]))
                            p["y"] = max(PLAYER_SIZE // 2, min(HEIGHT - PLAYER_SIZE // 2, p["y"]))
                        
                        # ---------------------------------------------------------
                        # Check coin collection
                        # ---------------------------------------------------------
                        for resource in resources[:]:  # [:] creates a copy for safe removal
                            # Check if player is close enough to collect coin
                            if (abs(player["x"] - resource["x"]) < PLAYER_SIZE / 2 and 
                                abs(player["y"] - resource["y"]) < PLAYER_SIZE / 2):
                                resources.remove(resource)  # Remove coin
                                player["score"] += 1         # Increase score
                        
                        broadcast_needed = True
                
                # =============================================================
                # MESSAGE TYPE: CHAT
                # Player is sending a chat message
                # =============================================================
                elif data["type"] == "chat":
                    if player_id in players:
                        sender_data = players[player_id]
                        
                        # Create chat broadcast payload
                        chat_payload = {
                            "type": "chat_broadcast",
                            "sender_id": player_id,
                            "sender_name": sender_data.get("name", "Player"),
                            "sender_color": sender_data.get("color", (255, 255, 255)),
                            "message": data.get("message", ""),
                            "timestamp": get_chat_timestamp()
                        }
                        
                        # Send to everyone EXCEPT the sender (they echo locally)
                        await broadcast_message(chat_payload, skip_player_id=player_id)
                
                # =============================================================
                # MESSAGE TYPE: START_GAME
                # Host is starting the game
                # =============================================================
                elif data["type"] == "start_game":
                    # Only host can start, and only from lobby
                    if player_id == host_player_id and game_state == "lobby":
                        duration_minutes = data.get("duration", 2)
                        duration_seconds = duration_minutes * 60
                        
                        print(f"[GAME] Host started game for {duration_minutes} minutes")
                        
                        # Update game state
                        game_state = "playing"
                        game_start_time = time.time()
                        game_end_time = game_start_time + duration_seconds
                        
                        # Start the game timer in the background
                        asyncio.create_task(end_game_timer(duration_seconds))
                        
                        broadcast_needed = True
                        
            finally:
                # Always release the lock
                STATE_LOCK.release()
            
            # Send updates to all clients if game state changed
            if broadcast_needed:
                await broadcast_updates()

    except websockets.exceptions.ConnectionClosed:
        # Connection was closed (player left or connection lost)
        print(f"[DISCONNECT] Connection closed for Player {player_id}")
        
    finally:
        # =====================================================================
        # PHASE 3: DISCONNECT CLEANUP
        # Clean up when player leaves or disconnects
        # =====================================================================
        
        broadcast_updates_needed = False
        disconnect_msg_payload = None
        
        await STATE_LOCK.acquire()
        try:
            if player_id in players:
                print(f"[DISCONNECT] Player {player_id} ({player_name}) left the game")
                
                # Create disconnect announcement
                disconnect_msg_payload = {
                    "type": "system_message",
                    "message": f"{player_name} has disconnected.",
                    "timestamp": get_chat_timestamp()
                }
                
                # Remove player from game
                del players[player_id]
                if player_id in clients:
                    del clients[player_id]
                
                broadcast_updates_needed = True
                
                # -------------------------------------------------------------
                # Handle host promotion
                # -------------------------------------------------------------
                if player_id == host_player_id:
                    if players:
                        # Promote the player with the lowest ID
                        new_host_id = min(players.keys())
                        host_player_id = new_host_id
                        print(f"[HOST] Player {new_host_id} promoted to host")
                    else:
                        # No players left
                        host_player_id = 0
                        print("[HOST] No players left, host cleared")
                
                # -------------------------------------------------------------
                # Reset server if last player leaves
                # -------------------------------------------------------------
                if not players:
                    print("[RESET] All players left. Resetting server...")
                    game_state = "lobby"
                    host_player_id = 0
                    next_player_id = 1
                    resources.clear()
                    broadcast_updates_needed = False  # No one to broadcast to

        finally:
            STATE_LOCK.release()
        
        # Send disconnect announcements after releasing lock
        if disconnect_msg_payload:
            await broadcast_message(disconnect_msg_payload)
        if broadcast_updates_needed:
            await broadcast_updates()


# =============================================================================
# COIN SPAWNER
# Background task that periodically spawns coins during gameplay
# =============================================================================

async def spawn_resources():
    """
    Spawns coins at regular intervals during gameplay.
    
    This runs continuously in the background and:
    1. Waits for the spawn interval (5 seconds)
    2. Checks if game is in "playing" state
    3. Creates a new coin at a random position
    4. Notifies all clients of the new coin
    """
    global next_resource_id
    
    while True:
        # Wait before spawning next coin
        await asyncio.sleep(RESOURCE_SPAWN_TIME)
        
        broadcast_needed = False
        
        # Only spawn if clients are connected
        if clients:
            await STATE_LOCK.acquire()
            try:
                # Only spawn during active gameplay
                if game_state == "playing":
                    # Create new coin at random position
                    resources.append({
                        "id": next_resource_id,
                        "x": random.randint(RESOURCE_SIZE, WIDTH - RESOURCE_SIZE),
                        "y": random.randint(RESOURCE_SIZE, HEIGHT - RESOURCE_SIZE)
                    })
                    next_resource_id += 1
                    broadcast_needed = True
                    print(f"[SPAWN] Coin #{next_resource_id-1} spawned")
                    
            finally:
                STATE_LOCK.release()
        
        # Notify clients if a coin was spawned
        if broadcast_needed:
            await broadcast_updates()


# =============================================================================
# SERVER INITIALIZATION
# =============================================================================

async def server_main():
    """
    Initializes and starts the WebSocket server.
    
    This function:
    1. Loads configuration from environment variables
    2. Starts the WebSocket server on the specified port
    3. Listens for incoming connections indefinitely
    """
    global LOBBY_PASSWORD
    
    # Load password from environment (or use default for testing)
    LOBBY_PASSWORD = os.environ.get("LOBBY_PASSWORD", "default_pass_123")
    print(f"[CONFIG] Lobby password configured")
    
    # Load port from environment (Railway provides this)
    port = int(os.environ.get("PORT", 8765))
    
    # Start the WebSocket server
    # - handle_client: Function called for each new connection
    # - "0.0.0.0": Listen on all network interfaces
    # - port: The port number to listen on
    # - ping_interval/timeout: Keep connections alive with periodic pings
    async with websockets.serve(
        handle_client, 
        "0.0.0.0", 
        port, 
        ping_interval=20,  # Send ping every 20 seconds
        ping_timeout=20    # Wait 20 seconds for pong response
    ):
        print(f"[SERVER] Started at ws://0.0.0.0:{port}")
        print(f"[SERVER] Waiting for connections...")
        
        # Keep server running forever
        await asyncio.Future()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """
    Starts both background tasks concurrently:
    1. Resource spawner (coins)
    2. WebSocket server (player connections)
    """
    # Run both tasks simultaneously
    await asyncio.gather(
        spawn_resources(),  # Background task for coin spawning
        server_main()       # Main server listening for connections
    )


# Run the server when this file is executed
if __name__ == "__main__":
    print("=" * 70)
    print("COIN CHAOS - MULTIPLAYER GAME SERVER")
    print("=" * 70)
    asyncio.run(main())
