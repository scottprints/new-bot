from discord import Embed

# Define preset messages for specific channels
PRESET_MESSAGES = {
    1319069218230243359: Embed(title="📜 Looking for Sleep Call Etiquette", color=0x3498db)
        .add_field(name="Etiquette and Rules", value="- Do not respond to looking posts in this channel.\n- Check if the poster has an 'Ask to DM' role.\n- If they do, go to the 'Ask To DM' channel to ask if you can DM.", inline=False),
    1319069228598562846: Embed(title="📜 Ask to DM Etiquette", color=0x3498db)
        .add_field(name="Respect the 'Ask to DM' Role", value="- Always respect the 'Ask to DM' role.\n- Follow general etiquette and rules.", inline=False)
} 

# Define global configuration variables
MOD_ACTIONS_CHANNEL_ID = 1318962030815875123 ## Mod Actions Channel ID
COOLDOWN_TIME = 30  ## Cooldown time for tag messages

## Role levels definitions
ROLE_LEVELS = {
    1: {"Moderator", "Admin"},  # Level 1: Gang
    2: {"Admin"}                # Level 2: Kool Kids Klub
}

# Define message limit and time window for spam detection
MESSAGE_LIMIT = 5  # Number of messages allowed
TIME_WINDOW = 10  # Time window in seconds

MUTED_ROLE_ID = 1319116489554399273

# Configuration variables
MUTE_DURATION = 60  # Default mute duration in seconds
SLOWMODE_DELAY = 10  # Slow mode delay in seconds
SPAM_THRESHOLD = 3  # Number of users spamming to trigger slow mode