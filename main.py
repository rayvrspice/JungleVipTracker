import discord
from discord import app_commands
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# ======================
# FILES
# ======================

DATA_FILE = "balances.json"
CONFIG_FILE = "config.json"

# ======================
# DISCORD SETUP
# ======================

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ======================
# DATA HANDLING
# ======================

def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_balance(data, guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data:
        data[guild_id] = {}

    return data[guild_id].get(user_id, 0)

def set_balance(data, guild_id, user_id, amount):
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data:
        data[guild_id] = {}

    data[guild_id][user_id] = amount

# ======================
# CONFIG HANDLING (PER GUILD)
# ======================

def load_config():
    try:
        if not os.path.exists(CONFIG_FILE):
            return {}
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def get_guild_config(guild_id):
    config = load_config()
    guild_id = str(guild_id)

    if guild_id not in config:
        config[guild_id] = {
            "allowed_roles": [],
            "log_channel": None
        }
        save_config(config)

    return config[guild_id]

# ======================
# PERMISSIONS
# ======================

def has_permission(interaction: discord.Interaction):
    guild_config = get_guild_config(interaction.guild.id)
    allowed_roles = guild_config.get("allowed_roles", [])
    user_roles = [role.id for role in interaction.user.roles]

    return any(role_id in allowed_roles for role_id in user_roles)

# ======================
# LOGGING
# ======================

async def send_log(interaction, action, member, amount, new_balance):
    guild_config = get_guild_config(interaction.guild.id)
    channel_id = guild_config.get("log_channel")

    if not channel_id:
        return

    channel = client.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title="📊 Balance Update",
        color=discord.Color.green() if action == "ADD" else discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Action", value=action)
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Amount", value=str(amount))
    embed.add_field(name="New Balance", value=str(new_balance))
    embed.add_field(name="Handled By", value=interaction.user.mention)

    await channel.send(embed=embed)

# ======================
# EVENTS
# ======================

@client.event
async def on_ready():
    if not hasattr(client, "synced"):
        await tree.sync()
        client.synced = True
    print(f"✅ Logged in as {client.user}")

# ======================
# COMMANDS
# ======================

@tree.command(name="balance")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    data = load_data()
    bal = get_balance(data, interaction.guild.id, member.id)

    await interaction.response.send_message(
        f"{member.mention} has {bal} coins."
    )

@tree.command(name="add")
async def add(interaction: discord.Interaction, member: discord.Member, amount: int):
    await interaction.response.defer()

    if not has_permission(interaction):
        await interaction.followup.send("❌ No permission", ephemeral=True)
        return

    data = load_data()
    new_balance = get_balance(data, interaction.guild.id, member.id) + amount
    set_balance(data, interaction.guild.id, member.id, new_balance)
    save_data(data)

    await interaction.followup.send(f"✅ Added {amount} coins to {member.mention}")
    await send_log(interaction, "ADD", member, amount, new_balance)

@tree.command(name="subtract")
async def subtract(interaction: discord.Interaction, member: discord.Member, amount: int):
    await interaction.response.defer()

    if not has_permission(interaction):
        await interaction.followup.send("❌ No permission", ephemeral=True)
        return

    data = load_data()
    new_balance = get_balance(data, interaction.guild.id, member.id) - amount
    set_balance(data, interaction.guild.id, member.id, new_balance)
    save_data(data)

    await interaction.followup.send(f"➖ Subtracted {amount} coins from {member.mention}")
    await send_log(interaction, "SUBTRACT", member, amount, new_balance)

# ======================
# ADMIN COMMANDS
# ======================

@tree.command(name="setlogchannel")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only", ephemeral=True)
        return

    config = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id not in config:
        config[guild_id] = {"allowed_roles": [], "log_channel": None}

    config[guild_id]["log_channel"] = channel.id
    save_config(config)

    await interaction.response.send_message(f"✅ Log channel set to {channel.mention}")

@tree.command(name="setrole")
async def setrole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only", ephemeral=True)
        return

    config = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id not in config:
        config[guild_id] = {"allowed_roles": [], "log_channel": None}

    roles = config[guild_id].get("allowed_roles", [])

    if role.id not in roles:
        roles.append(role.id)

    config[guild_id]["allowed_roles"] = roles
    save_config(config)

    await interaction.response.send_message(f"✅ Added {role.mention} to allowed roles")

@tree.command(name="removerole")
async def removerole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only", ephemeral=True)
        return

    config = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id not in config:
        config[guild_id] = {"allowed_roles": [], "log_channel": None}

    roles = config[guild_id].get("allowed_roles", [])

    if role.id in roles:
        roles.remove(role.id)

    config[guild_id]["allowed_roles"] = roles
    save_config(config)

    await interaction.response.send_message(f"🗑️ Removed {role.mention} from allowed roles")
    
@tree.command(name="viewconfig")
async def viewconfig(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only", ephemeral=True)
        return

    guild_config = get_guild_config(interaction.guild.id)

    log_channel_id = guild_config.get("log_channel")
    allowed_roles = guild_config.get("allowed_roles", [])

    log_channel = (
        f"<#{log_channel_id}>" if log_channel_id else "Not set"
    )

    if allowed_roles:
        roles_formatted = " ".join([f"<@&{role_id}>" for role_id in allowed_roles])
    else:
        roles_formatted = "None"

    embed = discord.Embed(
        title="⚙️ Server Configuration",
        color=discord.Color.blue()
    )

    embed.add_field(name="🆔 Server ID", value=str(interaction.guild.id), inline=False)
    embed.add_field(name="📊 Log Channel", value=log_channel, inline=False)
    embed.add_field(name="🔐 Allowed Roles", value=roles_formatted, inline=False)

    await interaction.response.send_message(embed=embed)

# ======================
# RUN BOT (AUTO-RESTART)
# ======================

print("🚀 Starting bot...")
client.run(os.getenv("TOKEN"))