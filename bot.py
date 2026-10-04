import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import sqlite3
from discord import Embed
import time
from config import *
import asyncio
import logging
from datetime import datetime, timedelta
import calendar
from discord.ui import Button, View
import pytz
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables bruv
load_dotenv()

# Grab the token from the environment, because I'm not leaking the token like I leaked 1000s of usernames/emails back in 2018, it was me DJ!!
TOKEN = os.getenv('DISCORD_TOKEN')

# Google Sheets API credentials
SHEETS_CREDS = os.getenv('GOOGLE_SHEETS_CREDS')
BUDGET_SHEET_ID = os.getenv('BUDGET_SHEET_ID')

# Relationship Website details
WEBSITE_URL = os.getenv('WEBSITE_URL')
ANNIVERSARY_DATE = os.getenv('ANNIVERSARY_DATE')  # Format: YYYY-MM-DD
PHOTOS_DIR = os.getenv('PHOTOS_DIR')  # Directory containing relationship photos

# Initialize the bot with a command prefix and all intents enabled
# Apparently we need this shit?
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Global variable for the server name, initialized when the bot is ready
SERVER_NAME = None

# Global database connection, initialized when needed
DB_CONNECTION = None
def get_db_connection():
    return sqlite3.connect('db/warnings.db')

# Function to check if a user has the required role level, sometimes works, change one line of unrelated code and it'll break.
# Abstracting role-checking logic
async def has_required_role(context, required_level: int) -> bool:
    # Always allow all commands in the watchlist server
    if context.guild and context.guild.id == WATCHLIST_SERVER_ID:
        return context.command.name == "watchlist"
        
    user_roles = {role.name for role in context.user.roles}
    required_roles = ROLE_LEVELS.get(required_level, set())
    return any(role in user_roles for role in required_roles)

# Utility function to send permission denial message
async def send_permission_denied_message(interaction: discord.Interaction):
    await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

# ================================
# ========== ON READY ===========
# ================================

@bot.event
async def on_ready():
    logging.debug("Entering on_ready event")
    global SERVER_NAME
    SERVER_NAME = bot.guilds[0].name
    logging.info(f'Logged in as {bot.user.name} in {SERVER_NAME}')
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"Error syncing commands: {e}")
    logging.debug("Exiting on_ready event")
    
    # Start the countdown update task
    bot.loop.create_task(update_countdown_status())
    
    # Start the watchlist cache update task
    bot.loop.create_task(update_watchlist_cache())

# ================================
# ======= COUNTDOWN TASK =========
# ================================

def calculate_countdown():
    """Calculate time remaining until October 21st, 2026 at 5:53PM US/Eastern"""
    eastern = pytz.timezone('US/Eastern')
    trip_date = eastern.localize(datetime(2026, 10, 21, 17, 53, 0))
    current_time = datetime.now(eastern)
    
    time_diff = trip_date - current_time
    
    if time_diff.total_seconds() <= 0:
        return "🎉 Trip time!"
    
    days = time_diff.days
    hours = (time_diff.seconds // 3600)
    
    return f"{days} days {hours} hours ❤️❤️❤️"

async def update_countdown_status():
    """Update bot status with countdown at the top of each hour"""
    await bot.wait_until_ready()
    logging.info("Countdown task started, will update at the top of each hour")
    
    # Update status immediately on startup
    try:
        countdown_text = calculate_countdown()
        activity = discord.Activity(type=discord.ActivityType.watching, name=countdown_text)
        await bot.change_presence(activity=activity)
        logging.info(f"Initial status update: {countdown_text}")
    except Exception as e:
        logging.error(f"Error updating initial status: {e}")
    
    while not bot.is_closed():
        try:
            now = datetime.now()
            # Calculate seconds until the top of the next hour
            seconds_until_next_hour = (3600 - (now.minute * 60 + now.second))
            
            logging.debug(f"Countdown task waiting {seconds_until_next_hour}s until next hour")
            # Wait until the top of the next hour
            await asyncio.sleep(seconds_until_next_hour)
            
            # Update the status
            countdown_text = calculate_countdown()
            activity = discord.Activity(type=discord.ActivityType.watching, name=countdown_text)
            await bot.change_presence(activity=activity)
            logging.info(f"Updated status to: {countdown_text}")
        except Exception as e:
            logging.error(f"Error updating countdown status: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying on error

# ================================
# ======== TEST COMMAND =========
# ================================


@bot.tree.command(name="test")
async def hello(interaction: discord.Interaction):
    # A test command to say hello - REMOVE LATER
    await interaction.response.send_message(f"yes cunt {interaction.user.mention} what you want bruv", ephemeral=True)

# ================================
# ========= SAY COMMAND =========
# ================================

@bot.tree.command(name="say")
@app_commands.describe(say_something="what cunt")
async def say(interaction: discord.Interaction, say_something: str):
    # Echo command that repeats whatever nonsense you type - REMOVE LATER
    await interaction.response.send_message(f"{say_something}")

# ================================
# ======== VERIFY COMMAND ========
# ================================

@bot.tree.command(name="verify")
@app_commands.describe(user="The user to verify")
async def verify(interaction: discord.Interaction, user: discord.Member):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return
    # Verify a user, grants 18+ role
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
                    logging.error(f"Failed to send message to mod-actions channel: {e}")
            else:
                logging.warning("Mod-actions channel not found.")
            # Log the verification in the database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO verifications (user_id, moderator_id) VALUES (?, ?)', (user.id, interaction.user.id))
            conn.commit()
            conn.close()
    else:
        await interaction.response.send_message("Verification role not found.", ephemeral=True)

# ================================
# ========= WARN COMMAND =========
# ================================

@bot.tree.command(name="warn")
@app_commands.describe(user="The user to warn", reason="The reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return
    # Issue a warning to a user
    # Logs the warning in the database and harasses them via DM
    logging.info(f"Warn command triggered by {interaction.user.mention} for {user.mention} with reason: {reason}")

    conn = get_db_connection()
    cursor = conn.cursor()
    logging.info("Inserting warning into database...")
    cursor.execute('INSERT INTO warnings (user_id, reason, moderator_id) VALUES (?, ?, ?)', (user.id, reason, interaction.user.id))
    conn.commit()
    conn.close()
    logging.info("Warning inserted into database.")

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

# ================================
# ====== SHOW WARNINGS/NOTES =====
# ================================

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
        embed = Embed(title=f"{user.name}'s Warnings", description=warnings_list, color=0x3498db)

        view = View()
        notes_button = Button(label="View Notes", style=discord.ButtonStyle.primary)

        async def notes_callback(interaction):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, reason, timestamp, author_id FROM notes WHERE user_id = ?', (user.id,))
            rows = cursor.fetchall()
            conn.close()

            if rows:
                notes_list = "\n".join([f"**ID**: {note_id}\n**Reason**: {reason}\n**Date**: {timestamp}\n**Author**: <@{author_id}>" for note_id, reason, timestamp, author_id in rows])
                embed = Embed(title=f"{user.name}'s Notes", description=notes_list, color=0x3498db)
            else:
                embed = Embed(title=f"{user.name}'s Notes", description="No notes found.", color=0x3498db)

            back_button = Button(label="Back to Warnings", style=discord.ButtonStyle.secondary)

            async def back_callback(interaction):
                await show_warnings.callback(interaction, user=user)

            back_button.callback = back_callback
            view = View()
            view.add_item(back_button)

            await interaction.response.edit_message(embed=embed, view=view)

        notes_button.callback = notes_callback
        view.add_item(notes_button)

        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(f"{user.mention} has no warnings.")

# ================================
# ======== DELETE WARNINGS =======
# ================================

@bot.tree.command(name="delete_warn")
@app_commands.describe(user="The user whose warning to delete", warning_id="The ID of the warning to delete")
async def delete_warn(interaction: discord.Interaction, user: discord.Member, warning_id: int):
    if not await has_required_role(interaction, 2):
        await send_permission_denied_message(interaction)
        return
    # Delete a specific warning from the database
    # Only users with the required role level can perform this action
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

# ================================
# ======== ERROR HANDLING ========
# ================================

@bot.event
async def on_command_error(interaction: discord.Interaction, error):
    # Global error handler
    # Tells user to fuck off, or myself to fuck off and die
    if isinstance(error, commands.CheckFailure):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)

# ================================
# ===== CHECK VERIFICATION =======
# ================================

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

# ================================
# ===== DELETE VERIFICATION ======
# ================================

@bot.tree.command(name="delete-verification")
@app_commands.describe(user="The user whose verification to delete")
async def delete_verification(interaction: discord.Interaction, user: discord.Member):
    if not await has_required_role(interaction, 2):
        await send_permission_denied_message(interaction)
        return
    # Delete a user's verification
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM verifications WHERE user_id = ?', (user.id,))
    conn.commit()
    conn.close()

    # Remove the '18+ Verified' role if the user has it
    role = discord.utils.get(interaction.guild.roles, name="18+ Verified")
    if role and role in user.roles:
        await user.remove_roles(role)

    await interaction.response.send_message(f"Verification for {user.mention} has been deleted and the role removed.")

# ================================
# ======= ANTI-SPAM LOGIC ========
# ================================
# Track the last message time for each channel
last_message_time = {}

# Track user message activity
user_message_count = {}

@bot.event
async def on_message(message):
    logging.debug(f"Received message from {message.author}: {message.content}")
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Skip anti-spam logic for the watchlist server
    if message.guild and message.guild.id == WATCHLIST_SERVER_ID:
        await bot.process_commands(message)
        return

    # Track message count
    user_id = message.author.id
    current_time = time.time()
    if user_id not in user_message_count:
        user_message_count[user_id] = []
    user_message_count[user_id].append(current_time)

    # Remove messages outside the time window
    user_message_count[user_id] = [t for t in user_message_count[user_id] if current_time - t <= TIME_WINDOW]

    # Check if user exceeds message limit
    if len(user_message_count[user_id]) > MESSAGE_LIMIT:
        logging.info(f"User {message.author} exceeded message limit, muting...")
        await perform_mute(message.guild, message.author, message.channel, duration=MUTE_DURATION)

    # Check if multiple users are spamming
    spamming_users = [uid for uid, times in user_message_count.items() if len(times) > MESSAGE_LIMIT]
    if len(spamming_users) > SPAM_THRESHOLD:
        logging.info("Multiple users spamming, enabling slow mode...")
        await message.channel.edit(slowmode_delay=SLOWMODE_DELAY)

    # Check if the message is in a channel with a preset message
    if message.channel.id in PRESET_MESSAGES:
        current_time = time.time()
        last_time = last_message_time.get(message.channel.id, 0)
        # Check if cooldown time has passed since the last message
        if current_time - last_time > COOLDOWN_TIME:
            logging.info(f"Sending preset message in channel {message.channel.id}")
            await message.channel.send(embed=PRESET_MESSAGES[message.channel.id])
            last_message_time[message.channel.id] = current_time

    # Process commands if any
    await bot.process_commands(message)
    logging.debug(f"Processed message from {message.author}")

# ================================
# ====== SCUFFED AUTO MUTE =======
# ================================

async def perform_mute(guild, user, channel, duration, moderator, is_automatic=False):
    logging.debug(f"Attempting to mute {user.mention} for {duration} seconds by {moderator.mention}")
    # Ensure the bot has a higher role than the user
    bot_member = guild.get_member(bot.user.id)
    if bot_member.top_role <= user.top_role:
        await channel.send("I cannot mute a user with an equal or higher role than mine.")
        logging.warning(f"Cannot mute {user.mention} due to role hierarchy")
        return

    # Check if the user already has the MUTED role
    muted_role = discord.utils.get(guild.roles, id=MUTED_ROLE_ID)
    if muted_role and muted_role.id in [role.id for role in user.roles]:
        logging.info(f"{user.mention} is already muted")
        return

    # Save current roles and assign MUTED role
    roles = [role.id for role in user.roles if role != guild.default_role]
    logging.debug(f"Saving roles for {user.mention}: {roles}")
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert or update roles in the backup database
    cursor.execute('INSERT INTO roles_backup (user_id, roles) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET roles=excluded.roles', (user.id, ','.join(map(str, roles))))
    conn.commit()
    conn.close()

    if muted_role:
        await user.edit(roles=[muted_role])
        logging.info(f"{user.mention} has been muted for {duration} seconds")
        # Send a DM to the user
        try:
            await user.send(f"You have been muted in **{SERVER_NAME}** for {duration} seconds.")
        except discord.Forbidden:
            logging.warning(f"Could not send DM to {user.mention}. They might have DMs disabled.")
        # Log the mute action in the mod-actions channel
        mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
        if mod_actions_channel:
            await mod_actions_channel.send(f"{user.mention} was muted for {duration} seconds by {moderator.mention}.")
        # Send the mute message only if it's an automatic mute
        if is_automatic:
            await channel.send(f"{user.mention} has been muted for {duration} seconds.")
        # Run the unmute operation in the background
        asyncio.create_task(unmute_after_delay(guild, user, channel, duration))
    else:
        await channel.send("MUTED role not found.")
        logging.error("MUTED role not found")

async def unmute_after_delay(guild, user, channel, duration):
    await asyncio.sleep(duration)
    refreshed_user = guild.get_member(user.id)
    if refreshed_user:
        await unmute_user(guild, refreshed_user, channel)
    else:
        logging.warning(f"Failed to refresh user context for {user.mention}")

# ============================================
# ========== SCUFFED AUTO UNMUTE =============
# ============================================
async def unmute_user(guild, user, channel):
    logging.debug(f"Attempting to unmute {user.mention}")
    # Remove the MUTED role if the user has it
    muted_role = discord.utils.get(guild.roles, id=MUTED_ROLE_ID)
    if muted_role:
        logging.debug(f"Checking MUTED role for {user.mention}: {muted_role.name}")
        if muted_role.id in [role.id for role in user.roles]:
            await user.remove_roles(muted_role)
            logging.info(f"MUTED role removed from {user.mention}")
        else:
            logging.info(f"{user.mention} does not have the MUTED role")
    else:
        logging.error("MUTED role not found in guild roles")

    # Retrieve and restore previous roles
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT roles FROM roles_backup WHERE user_id = ?', (user.id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:  # Check if roles are not empty
        logging.debug(f"Restoring roles for {user.mention}: {row[0]}")
        role_ids = map(int, filter(None, row[0].split(',')))  # Filter out empty strings
        roles = [discord.utils.get(guild.roles, id=role_id) for role_id in role_ids if role_id]
        await user.edit(roles=roles)
        await channel.send(f"{user.mention} has been unmuted and previous roles restored.")
        logging.info(f"{user.mention} has been unmuted and previous roles restored")
    else:
        await channel.send(f"{user.mention} has been unmuted.")
        logging.info(f"{user.mention} has been unmuted without previous roles")

    # Send a DM to the user
    try:
        await user.send(f"You have been unmuted in **{SERVER_NAME}**.")
    except discord.Forbidden:
        logging.warning(f"Could not send DM to {user.mention}. They might have DMs disabled.")

    # Log the unmute action in the mod-actions channel
    mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
    if mod_actions_channel:
        await mod_actions_channel.send(f"{user.mention} was unmuted by {bot.user.mention}.")

# ================================
# ========== MUTE COMMAND ========
# ================================

def parse_duration(duration_str: str) -> int:
    """Convert a duration string like '10s', '10m', '10h' into seconds."""
    unit = duration_str[-1]
    if unit not in 'smh':
        raise ValueError("Invalid duration unit. Use 's', 'm', or 'h'.")
    try:
        value = int(duration_str[:-1])
    except ValueError:
        raise ValueError("Invalid duration value.")
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600

@bot.tree.command(name="mute")
@app_commands.describe(user="The user to mute", duration="Duration (e.g., '10s (10 seconds)', '10m (10 minutes)', '10h (10 hours)')")
async def mute(interaction: discord.Interaction, user: discord.Member, duration: str):
    if not await has_required_role(interaction, 1):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    try:
        duration_seconds = parse_duration(duration)
    except ValueError as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return
    await interaction.response.defer()
    await perform_mute(interaction.guild, user, interaction.channel, duration_seconds, interaction.user, is_automatic=False)
    await interaction.followup.send(f"{user.mention} has been muted for {duration}.")

# ================================
# ========= UNMUTE COMMAND =======
# ================================

@bot.tree.command(name="unmute")
@app_commands.describe(user="The user to unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not await has_required_role(interaction, 2):
        await send_permission_denied_message(interaction)
        return
    await interaction.response.defer()
    await unmute_user(interaction.guild, user, interaction.channel)
    await interaction.followup.send(f"{user.mention} has been unmuted.")

# ================================
# ========= ROLE BACKUP ==========
# ================================

@bot.event
async def on_member_remove(member):
    # Save current roles when a user leaves
    roles = [role.id for role in member.roles if role != member.guild.default_role]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO roles_backup (user_id, roles) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET roles=excluded.roles', (member.id, ','.join(map(str, roles))))
    conn.commit()
    conn.close()

# ================================
# ========= ROLE RESTORE =========
# ================================

@bot.event
async def on_member_join(member):
    # Restore roles when a user rejoins
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT roles FROM roles_backup WHERE user_id = ?', (member.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        role_ids = map(int, filter(None, row[0].split(',')))  # Filter out empty strings
        roles = [discord.utils.get(member.guild.roles, id=role_id) for role_id in role_ids]
        await member.add_roles(*roles)

# ================================
# ======= NEW USER LOGIC =========
# ================================
    account_age = (discord.utils.utcnow() - member.created_at).days
    logging.debug(f"Account age for {member.mention}: {account_age} days")
    if account_age < 365:
        # Check if the user has the '18+ Verified' role stored
        if not any(role.name == "18+ Verified" for role in roles):
            logging.debug(f"{member.mention} does not have '18+ Verified' role stored")
            # Assign the muted role
            muted_role = discord.utils.get(member.guild.roles, id=MUTED_ROLE_ID)
            if muted_role:
                await member.add_roles(muted_role)
                logging.info(f"Assigned MUTED role to {member.mention} due to account age ({account_age} days)")
                # Log the action in the mod-actions channel
                mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
                if mod_actions_channel:
                    await mod_actions_channel.send(f"{member.mention} was automatically assigned the MUTED role due to account age ({account_age} days).")
            else:
                logging.error("MUTED role not found in guild roles")

# ================================
# ======== BOT DETAILS ===========
# ================================

@bot.tree.command(name="botinfo")
async def bot_info(interaction: discord.Interaction):
    # Calculate ping
    ping = round(bot.latency * 1000)  # Convert to milliseconds
    # Create an embed with bot details
    embed = Embed(title="Bot Details", color=0x3498db)
    embed.add_field(name="Bot Name", value=bot.user.name, inline=False)
    embed.add_field(name="Bot ID", value=bot.user.id, inline=False)
    embed.add_field(name="Ping", value=f"{ping} ms", inline=False)
    embed.add_field(name="Server Name", value=SERVER_NAME, inline=False)
    # Send the embed as a response
    await interaction.response.send_message(embed=embed)

# ================================
# ========== BAN COMMAND =========
# ================================

@bot.tree.command(name="ban")
@app_commands.describe(user="The user to ban", reason="The reason for the ban")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return
    # Ensure the executor has a higher role than the user
    if interaction.user.top_role <= user.top_role:
        await interaction.response.send_message("You cannot ban a user with an equal or higher role than yours.")
        return

    # Send a DM to the user before banning
    try:
        await user.send(f"You have been banned from **{SERVER_NAME}** for: {reason}\n\nFeel your ban was unfair? Appeal ban on our unban server: <cringe link>")
    except discord.Forbidden:
        logging.warning(f"Could not send DM to {user.mention}. They might have DMs disabled.")

    # Proceed to ban the user
    await user.ban(reason=reason)
    await interaction.response.send_message(f"{user.mention} has been banned for: {reason}")

    # Log the ban action in the mod-actions channel
    mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
    if mod_actions_channel:
        await mod_actions_channel.send(f"{user.mention} was banned for: {reason} by {interaction.user.mention}.")

# ================================
# ======== UNBAN COMMAND =========
# ================================

@bot.tree.command(name="unban")
@app_commands.describe(user_id="The ID of the user to unban")
async def unban(interaction: discord.Interaction, user_id: str):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return
    try:
        user_id = int(user_id.strip())  # Strip any whitespace and convert to int
    except ValueError:
        await interaction.response.send_message("Please provide a valid integer for the user ID.", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(user_id)
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"{user.mention} has been unbanned.")

        # Log the unban action in the mod-actions channel
        mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
        if mod_actions_channel:
            await mod_actions_channel.send(f"{user.mention} was unbanned by {interaction.user.mention}.")
    except discord.NotFound:
        await interaction.response.send_message("User not found.", ephemeral=True)

# ================================
# ====== BAN BY ID COMMAND =======
# ================================

@bot.tree.command(name="ban_id")
@app_commands.describe(user_id="The ID of the user to ban", reason="The reason for the ban")
async def ban_id(interaction: discord.Interaction, user_id: str, reason: str):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return
    try:
        user_id = int(user_id.strip())  # Strip any whitespace and convert to int
    except ValueError:
        await interaction.response.send_message("Please provide a valid integer for the user ID.", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(user_id)
        member = interaction.guild.get_member(user.id)  # Check if the user is a member

        # Send a DM to the user before banning if they are a member
        if member:
            try:
                await user.send(f"You have been banned from **{SERVER_NAME}** for: {reason}\n\nFeel your ban was unfair? Appeal ban on our unban server: <cringe link>")
            except discord.Forbidden:
                logging.warning(f"Could not send DM to {user.mention}. They might have DMs disabled.")

        # Proceed to ban the user
        await interaction.guild.ban(user, reason=reason)
        await interaction.response.send_message(f"{user.mention} has been banned for: {reason}")

        # Log the ban action in the mod-actions channel
        mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
        if mod_actions_channel:
            await mod_actions_channel.send(f"{user.mention} was banned for: {reason} by {interaction.user.mention}.")
    except discord.NotFound:
        await interaction.response.send_message("User not found.", ephemeral=True)

# ================================
# ====== NOTE SYSTEM =============
# ================================

@bot.tree.command(name="note")
@app_commands.describe(user="The user to add a note to", reason="The reason for the note")
async def add_note(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO notes (user_id, author_id, reason) VALUES (?, ?, ?)', (user.id, interaction.user.id, reason))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"Note added for {user.mention}.", ephemeral=True)

# View Notes Command
@bot.tree.command(name="view_notes")
@app_commands.describe(user="The user to view notes for")
async def view_notes(interaction: discord.Interaction, user: discord.Member):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, reason, timestamp, author_id FROM notes WHERE user_id = ?', (user.id,))
    rows = cursor.fetchall()
    conn.close()

    if rows:
        notes_list = "\n".join([f"**ID**: {note_id}\n**Reason**: {reason}\n**Date**: {timestamp}\n**Author**: <@{author_id}>" for note_id, reason, timestamp, author_id in rows])
        embed = Embed(title=f"{user.name}'s Notes", description=notes_list, color=0x3498db)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(f"No notes found for {user.mention}.")

# Set Slowmode Command
@bot.tree.command(name="slowmode")
@app_commands.describe(duration="Duration in seconds")
async def slowmode(interaction: discord.Interaction, duration: int):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return

    await interaction.channel.edit(slowmode_delay=duration)
    await interaction.response.send_message(f"Slow mode set to {duration} seconds in {interaction.channel.mention}.")

    # Log the action in the mod-actions channel
    mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
    if mod_actions_channel:
        await mod_actions_channel.send(f"Slow mode set to {duration} seconds in {interaction.channel.mention} by {interaction.user.mention}.")

# Disable Slowmode Command
@bot.tree.command(name="unslowmode")
async def unslowmode(interaction: discord.Interaction):
    if not await has_required_role(interaction, 1):
        await send_permission_denied_message(interaction)
        return

    await interaction.channel.edit(slowmode_delay=0)
    await interaction.response.send_message(f"Slow mode disabled in {interaction.channel.mention}.")

    # Log the action in the mod-actions channel
    mod_actions_channel = bot.get_channel(MOD_ACTIONS_CHANNEL_ID)
    if mod_actions_channel:
        await mod_actions_channel.send(f"Slow mode disabled in {interaction.channel.mention} by {interaction.user.mention}.")

# ================================
# ===== WATCHLIST API CACHE =====
# ================================

async def update_watchlist_cache():
    """Periodically cache the watchlist data to a JSON file for the API to read"""
    while True:
        try:
            channel = bot.get_channel(WATCHLIST_CHANNEL_ID)
            if channel:
                watchlist_items = []
                async for message in channel.history(limit=None):
                    status = "Not Started"
                    status_emoji = "📝"
                    
                    # Check reactions on the message
                    for reaction in message.reactions:
                        if str(reaction.emoji) == WATCHED_EMOJI:
                            status = "Watched"
                            status_emoji = "✅"
                            break
                        elif str(reaction.emoji) == IN_PROGRESS_EMOJI:
                            status = "In Progress"
                            status_emoji = "🟨"
                            break
                        elif str(reaction.emoji) == NO_EMOJI:
                            status = "No"
                            status_emoji = "❌"
                            break
                    
                    watchlist_items.append({
                        "title": message.content,
                        "status": status,
                        "status_emoji": status_emoji,
                        "message_id": message.id
                    })
                
                # Save to cache file
                with open('watchlist_cache.json', 'w') as f:
                    json.dump({
                        "success": True,
                        "count": len(watchlist_items),
                        "items": watchlist_items,
                        "last_updated": datetime.now().isoformat()
                    }, f)
                
                logging.debug(f"Watchlist cache updated: {len(watchlist_items)} items")
        except Exception as e:
            logging.error(f"Error updating watchlist cache: {e}")
        
        # Update cache every 60 seconds
        await asyncio.sleep(60)

# ================================
# ======= WATCHLIST TRACKING ======
# ================================

WATCHLIST_SERVER_ID = 1335847249061740656
WATCHLIST_CHANNEL_ID = 1401396706884587540
WATCHED_EMOJI = "✅"  # :agree_check:
IN_PROGRESS_EMOJI = "🟨"  # :yellow_square:
NO_EMOJI = "❌"  # :x:

@bot.event
async def on_raw_reaction_add(payload):
    # Only track reactions in the watchlist channel and server
    if payload.guild_id != WATCHLIST_SERVER_ID or payload.channel_id != WATCHLIST_CHANNEL_ID:
        return

    # Get the channel and message objects
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    # Check if the reaction is one we're tracking
    if str(payload.emoji) not in [WATCHED_EMOJI, IN_PROGRESS_EMOJI, NO_EMOJI]:
        return

    # If this is a watched reaction, remove any in-progress or no reaction
    if str(payload.emoji) == WATCHED_EMOJI:
        for reaction in message.reactions:
            if str(reaction.emoji) in [IN_PROGRESS_EMOJI, NO_EMOJI]:
                await message.clear_reaction(str(reaction.emoji))

    # If this is an in-progress reaction, remove any watched or no reaction
    elif str(payload.emoji) == IN_PROGRESS_EMOJI:
        for reaction in message.reactions:
            if str(reaction.emoji) in [WATCHED_EMOJI, NO_EMOJI]:
                await message.clear_reaction(str(reaction.emoji))

    # If this is a no reaction, remove any watched or in-progress reaction
    elif str(payload.emoji) == NO_EMOJI:
        for reaction in message.reactions:
            if str(reaction.emoji) in [WATCHED_EMOJI, IN_PROGRESS_EMOJI]:
                await message.clear_reaction(str(reaction.emoji))

class WatchlistView(discord.ui.View):
    def __init__(self, watchlist_items: list, page: int = 1, items_per_page: int = 25):
        super().__init__(timeout=None)  # No timeout
        self.watchlist_items = watchlist_items
        self.current_page = page
        self.items_per_page = items_per_page
        self.message = None
        
        # Calculate total pages based on non-empty categories
        self.total_pages = self.calculate_total_pages()
        
        # Update button states
        self.update_buttons()
        
    def calculate_total_pages(self):
        # Group items by status
        watched = []
        in_progress = []
        not_started = []
        no_items = []
        
        for title, status in self.watchlist_items:
            if status == "✅ Watched":
                watched.append(title)
            elif status == "🟨 In Progress":
                in_progress.append(title)
            elif status == "❌ No":
                no_items.append(title)
            else:
                not_started.append(title)
                
        # Create list of non-empty categories
        categories = []
        if watched:
            categories.append(("✅ WATCHED", watched))
        if in_progress:
            categories.append(("🟨 IN PROGRESS", in_progress))
        if not_started:
            categories.append(("📝 NOT STARTED", not_started))
            
        return max(1, (len(categories) + self.items_per_page - 1) // self.items_per_page)

    def update_buttons(self):
        # Update first/prev buttons
        self.first_page.disabled = self.current_page == 1
        self.prev_page.disabled = self.current_page == 1
        # Update next/last buttons
        self.next_page.disabled = self.current_page == self.total_pages
        self.last_page.disabled = self.current_page == self.total_pages

    def get_current_page_embed(self):
        embed = Embed(title="Watchlist", color=0x3498db)
        
        # Separate items by status
        watched = []
        in_progress = []
        not_started = []
        no_items = []
        
        for title, status in self.watchlist_items:
            if status == "✅ Watched":
                watched.append(title)
            elif status == "🟨 In Progress":
                in_progress.append(title)
            elif status == "❌ No":
                no_items.append(title)
            else:
                not_started.append(title)

        # Get total count for embed title
        total_items = len(watched) + len(in_progress) + len(not_started) + len(no_items)
        
        # Sort each category alphabetically
        watched.sort(key=str.casefold)  # Case-insensitive sort
        in_progress.sort(key=str.casefold)
        not_started.sort(key=str.casefold)
        no_items.sort(key=str.casefold)
        
        # Create list of non-empty categories with counts
        all_items = []
        if watched:
            all_items.append((f"✅ WATCHED ({len(watched)})", "\n".join(f"• {item}" for item in watched)))
        if in_progress:
            all_items.append((f"🟨 IN PROGRESS ({len(in_progress)})", "\n".join(f"• {item}" for item in in_progress)))
        if not_started:
            all_items.append((f"📝 NOT STARTED ({len(not_started)})", "\n".join(f"• {item}" for item in not_started)))
        if no_items:
            all_items.append((f"❌ NO ({len(no_items)})", "\n".join(f"• {item}" for item in no_items)))
            
        # Update embed title to include total count
        embed.title = f"Watchlist - {total_items} Total Items"
            
        # Only show page numbers if there are multiple pages with content
        if self.total_pages > 1:
            embed.title = f"Watchlist (Page {self.current_page}/{self.total_pages})"

        # Calculate which items to show on current page
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        # Add categorized items as fields
        current_items = all_items[start_idx:end_idx]
        for category, items in current_items:
            # Split items into chunks of 1024 characters or less
            chunks = []
            current_chunk = []
            current_length = 0
            
            for item in items.split('\n'):
                # Add 1 for the newline character
                if current_length + len(item) + 1 > 1000:  # Leave some margin for safety
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [item]
                    current_length = len(item) + 1
                else:
                    current_chunk.append(item)
                    current_length += len(item) + 1
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            
            # Add first chunk with original category name
            if chunks:
                embed.add_field(name=category, value=chunks[0], inline=False)
                
                # Add any additional chunks with continued category name
                for i, chunk in enumerate(chunks[1:], 1):
                    embed.add_field(name=f"{category} (Continued {i})", value=chunk, inline=False)

        return embed

    @discord.ui.button(label="⏮️ First", style=discord.ButtonStyle.grey)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(1, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

    @discord.ui.button(label="Last ⏭️", style=discord.ButtonStyle.grey)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.total_pages
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

    async def on_timeout(self):
        # Remove buttons when the view times out
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

def format_title(title: str) -> str:
    """Format a title to look nicer with proper capitalization."""
    # Words that should not be capitalized (unless they're at the start)
    small_words = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'of', 'on', 
                  'or', 'the', 'to', 'with', 'yet'}
    
    words = title.strip().split()
    if not words:
        return title
    
    # Capitalize the first word regardless of what it is
    formatted_words = [words[0].capitalize()]
    
    # Process the rest of the words
    for word in words[1:]:
        # Check if it's a small word
        if word.lower() in small_words:
            formatted_words.append(word.lower())
        # If it contains periods (like "S.H.I.E.L.D."), keep it as is
        elif '.' in word:
            formatted_words.append(word.upper())
        # Special case for "and" in "TV" strings
        elif word.lower() == 'tv':
            formatted_words.append('TV')
        else:
            formatted_words.append(word.capitalize())
    
    return ' '.join(formatted_words)

@bot.tree.command(name="watchlist")
@app_commands.describe(page="Page number to view (default: 1)")
async def show_watchlist(interaction: discord.Interaction, page: int = 1):
    """Shows the current watchlist with status indicators"""
    # Check if command is used in the correct server
    if interaction.guild_id != WATCHLIST_SERVER_ID:
        await interaction.response.send_message("This command can only be used in the designated server.", ephemeral=True)
        return

    channel = bot.get_channel(WATCHLIST_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("Watchlist channel not found.", ephemeral=True)
        return

    # Collect all watchlist items
    watchlist_items = []
    async for message in channel.history(limit=None):
        status = "📝 Not Started"  # Default status
        
        # Check reactions on the message
        for reaction in message.reactions:
            if str(reaction.emoji) == WATCHED_EMOJI:
                status = "✅ Watched"
                break
            elif str(reaction.emoji) == IN_PROGRESS_EMOJI:
                status = "🟨 In Progress"
                break
            elif str(reaction.emoji) == NO_EMOJI:
                status = "❌ No"
                break
        
        # Format the title before adding to the list
        formatted_title = format_title(message.content)
        watchlist_items.append((formatted_title, status))

    # Sort items by status (Watched -> In Progress -> Not Started)
    watchlist_items.sort(key=lambda x: (
        "0" if x[1] == "✅ Watched" else
        "1" if x[1] == "🟨 In Progress" else
        "2"
    ))

    if not watchlist_items:
        await interaction.response.send_message("No items in the watchlist yet!", ephemeral=True)
        return

    # Create view with navigation buttons
    view = WatchlistView(watchlist_items, page)
    
    # Send initial embed with view
    initial_message = await interaction.response.send_message(embed=view.get_current_page_embed(), view=view)
    # Store the message for timeout handling
    view.message = await interaction.original_response()


# ================================
# ========= COUNTUP TIMER ========
# ================================

# Store active timers to manage cleanup
active_timers = {}

# Our anniversary datetime
ANNIVERSARY_START = datetime(2025, 8, 2, 7, 40, 0)  # 2025-08-02 07:40:00

def compute_time_together(start_date: datetime):
    """Return a dict with years, months, days, hours, minutes, seconds between start_date and now."""
    now = datetime.now()

    years = now.year - start_date.year
    months = now.month - start_date.month
    days = now.day - start_date.day
    hours = now.hour - start_date.hour
    minutes = now.minute - start_date.minute
    seconds = now.second - start_date.second

    # Adjust negatives by borrowing
    if seconds < 0:
        seconds += 60
        minutes -= 1
    if minutes < 0:
        minutes += 60
        hours -= 1
    if hours < 0:
        hours += 24
        days -= 1
    if days < 0:
        # borrow days from previous month
        prev_month = now.month - 1 or 12
        prev_year = now.year if now.month != 1 else now.year - 1
        days_in_prev = calendar.monthrange(prev_year, prev_month)[1]
        days += days_in_prev
        months -= 1
    if months < 0:
        months += 12
        years -= 1

    return {
        "years": years,
        "months": months,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }

def make_countup_embed(start_date: datetime):
    vals = compute_time_together(start_date)
    embed = Embed(title="💝 Time Together 💝", color=0xFF1493)  # Hot pink color like your website
    
    # Create a layout that mimics your website's timeBox design
    time_display = [
        "```",
        "╭──────────────────────────────────────╮",
        "│                                      │",
        "│     Years   Months   Days   Hours    │",
        "│    ╭────╮  ╭────╮  ╭────╮  ╭────╮   │",
        f"│    │ {str(vals['years']).zfill(2)} │  │ {str(vals['months']).zfill(2)} │  │ {str(vals['days']).zfill(2)} │  │ {str(vals['hours']).zfill(2)} │   │",
        "│    ╰────╯  ╰────╯  ╰────╯  ╰────╯   │",
        "│                                      │",
        "│         Minutes    Seconds           │",
        "│         ╭────╮    ╭────╮           │",
        f"│         │ {str(vals['minutes']).zfill(2)} │    │ {str(vals['seconds']).zfill(2)} │           │",
        "│         ╰────╯    ╰────╯           │",
        "│                                      │",
        "╰──────────────────────────────────────╯",
        "```"
    ]
    
    embed.description = "\n".join(time_display)
    if WEBSITE_URL:
        embed.set_footer(text=f"Website: {WEBSITE_URL}")
    return embed


class LiveCountupView(View):
    def __init__(self, start_date: datetime):
        super().__init__(timeout=None)
        self.start_date = start_date
        self.message = None
        self.update_task = None

    async def start_timer(self):
        """Start the automatic update task"""
        self.update_task = asyncio.create_task(self.update_timer())

    async def update_timer(self):
        """Updates the timer every second"""
        try:
            while True:
                if self.message:
                    await self.message.edit(embed=make_countup_embed(self.start_date))
                await asyncio.sleep(1)  # Update every second
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error in timer update: {e}")

    def stop_timer(self):
        """Stop the automatic updates"""
        if self.update_task:
            self.update_task.cancel()

    async def on_timeout(self):
        """Handles cleanup when the view times out"""
        self.stop_timer()
        try:
            if self.message:
                await self.message.edit(view=None)  # Remove the view from the message
        except:
            pass


@bot.event
async def on_message_delete(message):
    """Handle cleanup when a timer message is deleted"""
    if message.id in active_timers:
        view = active_timers[message.id]
        view.stop_timer()
        del active_timers[message.id]

@bot.event
async def on_close():
    """Clean up all active timers when the bot shuts down"""
    for view in active_timers.values():
        view.stop_timer()
    active_timers.clear()

@bot.tree.command(name="together")
async def together(interaction: discord.Interaction):
    """See how long we been goosin around"""
    if interaction.guild_id != WATCHLIST_SERVER_ID:
        await interaction.response.send_message("This command can only be used in the designated server.", ephemeral=True)
        return

    view = LiveCountupView(ANNIVERSARY_START)
    await interaction.response.send_message(embed=make_countup_embed(ANNIVERSARY_START), view=view)
    # Store the message reference and start the timer
    view.message = await interaction.original_response()
    await view.start_timer()
    # Store the timer for cleanup
    active_timers[view.message.id] = view
# Test function to check time calculation
def test_time_together():
    start_date = datetime(2025, 8, 2, 7, 40, 0)
    time_vals = compute_time_together(start_date)
    print("\n💖 Time Together Test 💖")
    print("=" * 40)
    print(f"Start Date: 2025-08-02 07:40:00")
    print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40)
    print(f"✨ Years: {time_vals['years']}")
    print(f"💫 Months: {time_vals['months']}")
    print(f"🌸 Days: {time_vals['days']}")
    print(f"💖 Hours: {time_vals['hours']}")
    print(f"💕 Minutes: {time_vals['minutes']}")
    print(f"💗 Seconds: {time_vals['seconds']}")
    print("=" * 40)

if __name__ == "__main__":
    # Run the test if run directly
    if os.getenv('TEST_MODE') == 'true':
        test_time_together()
    else:
        # Initialize watchlist cache file
        if not os.path.exists('watchlist_cache.json'):
            with open('watchlist_cache.json', 'w') as f:
                json.dump({"success": True, "count": 0, "items": []}, f)

        # Start Flask API server in a background thread
        app = Flask(__name__)
        CORS(app)

        @app.route('/api/watchlist', methods=['GET'])
        def get_watchlist():
            """Returns the cached watchlist data"""
            try:
                if os.path.exists('watchlist_cache.json'):
                    with open('watchlist_cache.json', 'r') as f:
                        return jsonify(json.load(f))
                else:
                    return jsonify({"success": False, "error": "Cache file not found"}), 404
            except Exception as e:
                logging.error(f"Error reading watchlist cache: {e}")
                return jsonify({"error": str(e)}), 500

        def run_flask():
            """Run Flask app on port 5000"""
            app.run(host='0.0.0.0', port=5000, debug=False)

        # Start Flask in a background thread
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Run the Discord bot
        bot.run(TOKEN)