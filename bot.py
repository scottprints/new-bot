import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import sqlite3
from discord import Embed
import time
from config import *

# Load environment variables bruv
load_dotenv()

# Grab the token from the environment, because I'm not leaking the token like I leaked 1000s of usernames/emails back in 2018, it was me DJ!!
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize the bot with a command prefix and all intents enabled
# Apparently we need this shit?
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Global variable for the server name, initialized when the bot is ready
SERVER_NAME = None

# Global database connection, initialized when needed
DB_CONNECTION = None
def get_db_connection():
    global DB_CONNECTION
    if DB_CONNECTION is None or DB_CONNECTION.closed:
        DB_CONNECTION = sqlite3.connect('db/warnings.db')
    return DB_CONNECTION

# Function to check if a user has the required role level, sometimes works, change one line of unrelated code and it'll break.
# Abstracting role-checking logic
async def has_required_role(interaction: discord.Interaction, required_level: int) -> bool:
    user_roles = {role.name for role in interaction.user.roles}
    required_roles = ROLE_LEVELS.get(required_level, set())
    return any(role in user_roles for role in required_roles)

## On Ready 
@bot.event
async def on_ready():
    global SERVER_NAME
    # When our shit VPS finally loads
    # Syncs the command tree with Discord and logs the bot's status, we don't fuck with cogs yet.
    SERVER_NAME = bot.guilds[0].name
    print(f'Logged in as {bot.user.name} in {SERVER_NAME}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

## Test Command
@bot.tree.command(name="test")
async def hello(interaction: discord.Interaction):
    # A test command to say hello - REMOVE LATER
    await interaction.response.send_message(f"yes cunt {interaction.user.mention} what you want bruv", ephemeral=True)

## Say Command
@bot.tree.command(name="say")
@app_commands.describe(say_something="what cunt")
async def say(interaction: discord.Interaction, say_something: str):
    # Echo command that repeats whatever nonsense you type - REMOVE LATER
    await interaction.response.send_message(f"{say_something}")

## Verify Command
@bot.tree.command(name="verify")
@app_commands.describe(user="The user to verify")
async def verify(interaction: discord.Interaction, user: discord.Member):
    # Verify a user, grants 18+ role
    if not await has_required_role(interaction, 1):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name="18+ Verified")
    if role:
        if role in user.roles:
            await interaction.response.send_message(f"{user.mention} already has the {role.name} role.")
        else:
            await user.add_roles(role)
            await interaction.response.send_message(f"{user.mention} has been verified and given the {role.name} role.")
            # Log the verification in the mod-actions channel with error handling
            mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
            if mod_actions_channel:
                try:
                    await mod_actions_channel.send(f"{user.mention} was verified and given the {role.name} role by {interaction.user.mention}.")
                except Exception as e:
                    print(f"Failed to send message to mod-actions channel: {e}")
            else:
                print("Mod-actions channel not found.")
            # Log the verification in the database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO verifications (user_id, moderator_id) VALUES (?, ?)', (user.id, interaction.user.id))
            conn.commit()
            conn.close()
    else:
        await interaction.response.send_message("Verification role not found.", ephemeral=True)

## Warn Command
@bot.tree.command(name="warn")
@app_commands.describe(user="The user to warn", reason="The reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    # Issue a warning to a user
    # Logs the warning in the database and harasses them via DM
    if not await has_required_role(interaction, 1):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    print(f"Warn command triggered by {interaction.user.mention} for {user.mention} with reason: {reason}")

    conn = get_db_connection()
    cursor = conn.cursor()
    print("Inserting warning into database...")
    cursor.execute('INSERT INTO warnings (user_id, reason, moderator_id) VALUES (?, ?, ?)', (user.id, reason, interaction.user.id))
    conn.commit()
    conn.close()
    print("Warning inserted into database.")

    # Defer the response to keep the interaction alive
    await interaction.response.defer()

    # Try to send a DM to the user with the warning details
    try:
        await user.send(f"You have been warned in **{SERVER_NAME}** for: {reason}")
    except discord.Forbidden:
        await interaction.followup.send(f"Could not DM {user.mention}. They might have DMs disabled.")

    # Log the warning in the mod-actions channel
    mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
    if mod_actions_channel:
        await mod_actions_channel.send(f"{user.mention} was warned in {SERVER_NAME} for: {reason}")

    # Send the final response
    await interaction.followup.send(f"{user.mention} has been warned for: {reason}")


## Show Warnings / Notes
@bot.tree.command(name="infractions")
@app_commands.describe(user="The user to check warnings for")
async def show_warnings(interaction: discord.Interaction, user: discord.Member):
    # Show a user's warnings
    # Retrieves and formats warning data from the database
    if not await has_required_role(interaction, 1):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, reason, timestamp, moderator_id FROM warnings WHERE user_id = ?', (user.id,))
    rows = cursor.fetchall()
    conn.close()

    if rows:
        warnings_list = "\n".join([f"**{warn_id}**: {timestamp}: {reason} (by <@{moderator_id}>)" for warn_id, reason, timestamp, moderator_id in rows])
        await interaction.response.send_message(f"{user.mention} has the following warnings:\n{warnings_list}")
    else:
        await interaction.response.send_message(f"{user.mention} has no warnings.")


## Delete Warnings
@bot.tree.command(name="delete_warn")
@app_commands.describe(user="The user whose warning to delete", warning_id="The ID of the warning to delete")
async def delete_warn(interaction: discord.Interaction, user: discord.Member, warning_id: int):
    # Delete a specific warning from the database
    # Only users with the required role level can perform this action
    if not await has_required_role(interaction, 2):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM warnings WHERE user_id = ? AND id = ?', (user.id, warning_id))
    conn.commit()
    conn.close()

    # Log the deletion in the mod-actions channel
    mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
    if mod_actions_channel:
        await mod_actions_channel.send(f"Warning with ID {warning_id} for {user.mention} has been deleted by {interaction.user.mention}.")

    await interaction.response.send_message(f"Warning with ID {warning_id} for {user.mention} has been deleted.")


## Error Handling
@bot.event
async def on_command_error(interaction: discord.Interaction, error):
    # Global error handler
    # Tells user to fuck off, or myself to fuck off and die
    if isinstance(error, commands.CheckFailure):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

## Check Verification Command
@bot.tree.command(name="check-verification")
@app_commands.describe(user="The user to check verification for")
async def check_verification(interaction: discord.Interaction, user: discord.Member):
    # Check if a user is verified
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM verifications WHERE user_id = ?', (user.id,))
    verification = cursor.fetchone()
    conn.close()

    if verification:
        role = discord.utils.get(interaction.guild.roles, name="18+ Verified")
        if role and role not in user.roles:
            await user.add_roles(role)
            await interaction.response.send_message(f"{user.mention} is verified already and the role has been added back.")
        else:
            await interaction.response.send_message(f"{user.mention} is verified.")
    else:
        await interaction.response.send_message(f"{user.mention} is not verified.")

## Delete Verification Command
@bot.tree.command(name="delete-verification")
@app_commands.describe(user="The user whose verification to delete")
async def delete_verification(interaction: discord.Interaction, user: discord.Member):
    # Delete a user's verification
    if not await has_required_role(interaction, 2):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM verifications WHERE user_id = ?', (user.id,))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"Verification for {user.mention} has been deleted.")

# Track the last message time for each channel
last_message_time = {}

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check if the message is in a channel with a preset message
    if message.channel.id in PRESET_MESSAGES:
        current_time = time.time()
        last_time = last_message_time.get(message.channel.id, 0)
        # Check if cooldown time has passed since the last message
        if current_time - last_time > COOLDOWN_TIME:
            await message.channel.send(embed=PRESET_MESSAGES[message.channel.id])
            last_message_time[message.channel.id] = current_time
    
    # Process commands if any
    await bot.process_commands(message)

## Create Tag Command
@bot.tree.command(name="create-tag")
@app_commands.describe(channel_id="Channel ID for the tag", title="Title of the tag", message="Message content")
async def create_tag(interaction: discord.Interaction, channel_id: int, title: str, message: str):
    # Check for required role level
    if not await has_required_role(interaction, 2):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    # Create a new tag
    PRESET_MESSAGES[channel_id] = Embed(title=title, color=0x3498db).add_field(name=title, value=message, inline=False)
    await interaction.response.send_message(f"Tag created for channel {channel_id}.")

## Read Tags Command
@bot.tree.command(name="list-tags")
async def list_tags(interaction: discord.Interaction):
    # Check for required role level
    if not await has_required_role(interaction, 1):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    # List all tags
    if PRESET_MESSAGES:
        tags_list = "\n".join([f"Channel {channel_id}: {embed.title}" for channel_id, embed in PRESET_MESSAGES.items()])
        await interaction.response.send_message(f"Current tags:\n{tags_list}")
    else:
        await interaction.response.send_message("No tags available.")

## Update Tag Command
@bot.tree.command(name="update-tag")
@app_commands.describe(channel_id="Channel ID for the tag", title="New title of the tag", message="New message content")
async def update_tag(interaction: discord.Interaction, channel_id: int, title: str, message: str):
    # Check for required role level
    if not await has_required_role(interaction, 2):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    # Update an existing tag
    if channel_id in PRESET_MESSAGES:
        PRESET_MESSAGES[channel_id] = Embed(title=title, color=0x3498db).add_field(name=title, value=message, inline=False)
        await interaction.response.send_message(f"Tag updated for channel {channel_id}.")
    else:
        await interaction.response.send_message("Tag not found.")

## Delete Tag Command
@bot.tree.command(name="delete-tag")
@app_commands.describe(channel_id="Channel ID for the tag")
async def delete_tag(interaction: discord.Interaction, channel_id: int):
    # Check for required role level
    if not await has_required_role(interaction, 2):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    # Delete a tag
    if channel_id in PRESET_MESSAGES:
        del PRESET_MESSAGES[channel_id]
        await interaction.response.send_message(f"Tag deleted for channel {channel_id}.")
    else:
        await interaction.response.send_message("Tag not found.")

# Run bot
bot.run(TOKEN)