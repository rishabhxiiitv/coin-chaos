# Coin Chaos 

A real-time multiplayer coin collection game built with Python, Pygame, and WebSockets. Players compete to collect the most coins within a time limit while chatting with each other in-game.


---

## ✨ Features

### 🎮 Gameplay
- **Real-time multiplayer** - Play with multiple players simultaneously
- **Coin collection mechanics** - Compete to collect spawning coins
- **Player collision system** - Push other players around the map
- **Customizable game duration** - Host sets timer from 1-99 minutes
- **Live leaderboard** - Track scores in real-time during gameplay

### 💬 Communication
- **In-game chat system** - Message other players during the game
- **Chat bubbles** - Visual message display with player avatars
- **System notifications** - Join/leave announcements
- **Timestamp tracking** - See when messages were sent

### 🎨 Visual & Audio
- **Custom pixel art sprites** - Unique player character designs
- **Color-coded players** - Each player has a distinct color
- **Sound effects** - Coin collection, connect/disconnect, chat notifications
- **Animated UI** - Bouncing lobby avatars, smooth transitions
- **Custom font support** - Jacquard24 pixel font for titles

### 🏗️ Technical
- **WebSocket architecture** - Low-latency real-time communication
- **Server state management** - Centralized game logic with async locking
- **Auto-reconnect handling** - Graceful disconnect management
- **Password-protected lobbies** - Secure game sessions

---

## 🎥 Demo

*(Add screenshots or GIF recordings here once available)*

**Lobby Screen:**
- Player list with avatars
- Host controls for starting game
- Chat tab for pre-game communication

**Game Screen:**
- Live gameplay with coin spawning
- Player movement and collision
- Real-time score tracking
- In-game chat panel

**Leaderboard Screen:**
- Final scores displayed
- Winner announcement
- 10-second view before disconnect

---

## 🚀 Installation

### Prerequisites
- **Python 3.8+** installed on your system
- **pip** package manager
- All asset files in the `assets/` directory

### Client Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/coin-chaos.git
cd coin-chaos
```

2. **Create a virtual environment** (recommended)
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Ensure all assets are present**
```
coin-chaos/
├── main.py
├── server.py
├── requirements.txt
├── Player.png
├── Player without shadow.png
├── Coin.png
├── ground.png
├── Send logo.png
├── Jacquard24-Regular.ttf
├── click.wav
├── coin.wav
├── connect.wav
├── disconnect.wav
├── game_over.wav
└── chat_message.wav
```

---

## 🌐 Deployment

### Deploy Server on Railway

1. **Create a Railway account**
   - Go to [Railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create new project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `coin-chaos` repository

3. **Configure environment variables**
   - In Railway dashboard, go to your project
   - Click on "Variables" tab
   - Add the following variables:
   
   ```env
   LOBBY_PASSWORD=your_secure_password_here
   PORT=8765
   ```

4. **Deploy the server**
   - Railway will automatically detect `server.py`
   - Server will deploy and provide you with a URL like:
     ```
     v3-production-5d5a.up.railway.app
     ```

5. **Get your WebSocket URI**
   - Your final WebSocket URI will be:
     ```
     wss://your-app-name.up.railway.app
     ```
   - Note this down for the next step

### Alternative Deployment Options

<details>
<summary><b>Heroku</b></summary>

1. Create `Procfile`:
```
web: python server.py
```

2. Deploy:
```bash
heroku create your-app-name
heroku config:set LOBBY_PASSWORD=your_password
git push heroku main
```

3. Your URI: `wss://your-app-name.herokuapp.com`
</details>

<details>
<summary><b>Local Server (Testing)</b></summary>

Run server locally:
```bash
python server.py
```

Use URI: `ws://localhost:8765`
</details>

---

## ⚙️ Configuration

### Update Client with Server URI

After deploying your server, you **must** update the client code:

1. **Open `main.py`**

2. **Find the `main()` function** (near the bottom of the file)

3. **Locate these lines:**
```python
#uri = "ws://localhost:8765" # Localhost for testing
uri = "wss://v3-production-5d5a.up.railway.app" # Deployed server
```

4. **Replace with your Railway URI:**
```python
#uri = "ws://localhost:8765" # Localhost for testing
uri = "wss://your-app-name.up.railway.app" # Your deployed server
```

5. **Save the file**

### Environment Variables (Server)

Create a `.env` file or set these in your deployment platform:

```env
# Required
LOBBY_PASSWORD=your_secure_password

# Optional (defaults shown)
PORT=8765
```

---

## 🎮 How to Play

### Starting the Game

1. **Run the client**
```bash
python main.py
```

2. **Enter your details**
```
Please enter your name: YourName
Enter lobby password: your_secure_password
```

3. **Wait in lobby**
   - First player to join becomes the **host**
   - Host can start the game by clicking **"Play"**
   - Other players see "Waiting for host to start..."

### Lobby Controls

| Action | Description |
|--------|-------------|
| **Play Button** | (Host only) Opens timer selection screen |
| **Leave Button** | Exit to desktop |
| **Lobby Tab** | View connected players |
| **Chat Tab** | Send messages to other players |

### Setting Game Duration

1. Host clicks **"Play"** button
2. Timer selection screen appears
3. Use **up/down arrows** to adjust minutes (1-99)
4. Click **"Start Game"** to begin countdown
5. Click **back arrow** to return to lobby

### In-Game Controls

| Key | Action |
|-----|--------|
| **Arrow Keys** or **WASD** | Move your player |
| **Enter** | Open/send chat message |
| **Mouse Click** | Switch between Lobby/Chat tabs |
| **Scroll Wheel** | (In chat) Scroll through message history |

### Gameplay Rules

1. **Objective:** Collect the most coins before time runs out
2. **Coin Spawning:** New coins appear every 5 seconds
3. **Collisions:** Players can push each other
4. **Scoring:** +1 point per coin collected
5. **Time Limit:** Set by host (1-99 minutes)

### End Game

- Timer reaches 0:00
- Leaderboard displays for 10 seconds
- All players disconnected automatically
- Server resets for next game

---


## 🛠️ Troubleshooting

### Common Issues

<details>
<summary><b>❌ "Connection failed. Is the server running?"</b></summary>

**Cause:** Can't reach server URI

**Solutions:**
- Verify server is deployed and running on Railway
- Check URI in `main.py` matches your Railway URL
- Ensure URI uses `wss://` (not `ws://`) for deployed servers
- Test server URL in browser (should show "Upgrade Required")
</details>

<details>
<summary><b>❌ "Failed to join lobby: Wrong password"</b></summary>

**Cause:** Password mismatch

**Solutions:**
- Check `LOBBY_PASSWORD` environment variable on server
- Ensure you're entering the correct password in client
- Passwords are case-sensitive
</details>

<details>
<summary><b>❌ Missing Assets Error</b></summary>

**Cause:** Required files not in directory

**Solutions:**
- Verify all `.png`, `.wav`, and `.ttf` files are present
- Check file names match exactly (case-sensitive)
- Re-download assets from repository
</details>

<details>
<summary><b>❌ Pygame Window Won't Open</b></summary>

**Cause:** Graphics driver or Pygame installation issue

**Solutions:**
```bash
# Reinstall Pygame
pip uninstall pygame
pip install pygame

# On Linux, install SDL dependencies
sudo apt-get install python3-dev libsdl-image1.2-dev libsdl-mixer1.2-dev libsdl-ttf2.0-dev
```
</details>

<details>
<summary><b>❌ "No module named 'websockets'"</b></summary>

**Cause:** Missing dependency

**Solution:**
```bash
pip install websockets
# Or
pip install -r requirements.txt
```
</details>

### Server Logs

Check Railway logs for server errors:
1. Go to Railway dashboard
2. Click on your deployment
3. Open "Deployments" tab
4. Click "View Logs"

Look for:
- `Server started at ws://0.0.0.0:8765` (startup success)
- `Player X has joined.` (connections working)
- Any Python exceptions (errors to fix)

---

## 📦 Dependencies

### requirements.txt
```txt
pygame==2.5.2
websockets==12.0
```

### System Requirements
- **OS:** Windows 10/11, macOS 10.14+, or Linux (Ubuntu 20.04+)
- **Python:** 3.8 or higher
- **RAM:** 2GB minimum
- **Network:** Stable internet connection for multiplayer

---

<div align="center">

**Made with ❤️ and Python**

⭐ Star this repo if you enjoyed the game!

</div>
