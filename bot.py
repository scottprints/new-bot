import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import sqlite3
from discord import Embed
import time
from config import *
import asyncio
import logging
from discord.ui import Button, View

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    return sqlite3.connect('db/warnings.db')

# Function to check if a user has the required role level, sometimes works, change one line of unrelated code and it'll break.
# Abstracting role-checking logic
async def has_required_role(context, required_level: int) -> bool:
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

# Run bot
bot.run(TOKEN)