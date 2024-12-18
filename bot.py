import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import sqlite3

# Load environment variables from .env file
load_dotenv()

# Get the token from the environment variable
TOKEN = os.getenv('DISCORD_TOKEN')
# Sync the commands with Discord
bot = commands.Bot(command_prefix="!", intents = discord.Intents.all())

# Database connection
def get_db_connection():
    conn = sqlite3.connect('db/warnings.db')
    return conn

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)
    
@bot.tree.command(name="test")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"yes cunt {interaction.user.mention} what you want bruv", ephemeral=True)
    
@bot.tree.command(name="say")
@app_commands.describe(say_something = "what cunt")
async def say(interaction: discord.Interaction, say_something: str):
    await interaction.response.send_message(f"{say_something}")
    
## Verification System
@bot.tree.command(name="verify")
@app_commands.describe(user="The user to verify")
async def verify(interaction: discord.Interaction, user: discord.Member):
    # Define the roles that are allowed to use this command
    allowed_roles = {"Moderator", "Admin"}
    
    # Check if the user has one of the allowed roles
    if any(role.name in allowed_roles for role in interaction.user.roles):
        role = discord.utils.get(interaction.guild.roles, name="18+ Verified")
        if role:
            if role in user.roles:
                await interaction.response.send_message(f"{user.mention} already has the {role.name} role.", ephemeral=True)
            else:
                await user.add_roles(role)
                await interaction.response.send_message(f"{user.mention} has been verified and given the {role.name} role.")
        else:
            await interaction.response.send_message("Verification role not found.", ephemeral=True)
    else:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    
@bot.tree.command(name="warn")
@app_commands.describe(user="The user to warn", reason="The reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warnings (user_id, reason) VALUES (?, ?)', (user.id, reason))
    conn.commit()
    conn.close()
    
    # Get the server (guild) name
    server_name = interaction.guild.name
    
    # Send a DM to the user with the warning and server name
    try:
        await user.send(f"You have been warned in {server_name} for: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message(f"Could not DM {user.mention}. They might have DMs disabled.", ephemeral=True)
    
    # Log the warning in the specified channel using its ID
    channel_id = 1318962030815875123
    mod_actions_channel = bot.get_channel(channel_id)
    if mod_actions_channel:
        await mod_actions_channel.send(f"{user.mention} was warned in {server_name} for: {reason}")
    
    await interaction.response.send_message(f"{user.mention} has been warned for: {reason}")

@bot.tree.command(name="infractions")
@app_commands.describe(user="The user to check warnings for")
async def show_warnings(interaction: discord.Interaction, user: discord.Member):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT reason, timestamp FROM warnings WHERE user_id = ?', (user.id,))
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        warnings_list = "\n".join([f"{timestamp}: {reason}" for reason, timestamp in rows])
        await interaction.response.send_message(f"{user.mention} has the following warnings:\n{warnings_list}")
    else:
        await interaction.response.send_message(f"{user.mention} has no warnings.")

# Run the bot
bot.run(TOKEN)