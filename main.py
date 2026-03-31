import discord
from discord import app_commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = "/home/ubuntu/JungleVipTracker/balances.json"
CONFIG_FILE = "/home/ubuntu/JungleVipTracker/config.json"

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
    except Exception as e:
        print(f"Error loading data: {e}")
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_balance(data, guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data:
        data[guild_id] = {}

    if user_id not in data[guild_id]:
        data[guild_id][user_id] = 0

    return data[guild_id][user_id]

def set_balance(data, guild_id, user_id, amount):
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in data:
        data[guild_id] = {}

    data[guild_id][user_id] = amount

# ======================
# CONFIG HANDLING
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
# HELPERS
# ======================

def extract_vrc_user(link):
    if not link:
        return None
    try:
        return link.strip("/").split("/")[-1]
    except:
        return None

# ======================
# LOGGING
# ======================

async def send_log(interaction, embed):
    guild_config = get_guild_config(interaction.guild.id)
    channel_id = guild_config.get("log_channel")

    if not channel_id:
        return

    channel = interaction.guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except:
            return

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
async def balance(interaction: discord.Interaction, member: discord.User = None):
    member = member or interaction.user

    data = load_data()
    bal = get_balance(data, interaction.guild.id, member.id)

    embed = discord.Embed(
        description=f"💰 **{member.name}**'s balance: **{bal} coins**",
        color=discord.Color.gold()
    )

    embed.set_author(
        name=f"{member.name}'s Account",
        icon_url=member.display_avatar.url
    )

    embed.set_footer(text="VIP Economy System")

    await interaction.response.send_message(embed=embed)

# ➕ ADD
@tree.command(name="add")
async def add(interaction: discord.Interaction, member: discord.User, amount: int):
    await interaction.response.defer()

    if not has_permission(interaction):
        await interaction.followup.send("❌ No permission", ephemeral=True)
        return

    data = load_data()
    new_balance = get_balance(data, interaction.guild.id, member.id) + amount
    set_balance(data, interaction.guild.id, member.id, new_balance)
    save_data(data)

    embed = discord.Embed(
        title="➕ Coins Added",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Amount", value=str(amount))
    embed.add_field(name="New Balance", value=str(new_balance))

    await interaction.followup.send(embed=embed)
    await send_log(interaction, embed)

# ➖ SUBTRACT (FIXED)
@tree.command(name="subtract")
@app_commands.describe(
    vip_user="VIP user spending coins",
    amount="Amount to subtract",
    target_user="Target user (optional)",
    link="Optional VRChat profile link"
)
async def subtract(
    interaction: discord.Interaction,
    vip_user: discord.User,
    amount: int,
    target_user: str = None,
    link: str = None
):
    await interaction.response.defer()

    if not has_permission(interaction):
        await interaction.followup.send("❌ No permission", ephemeral=True)
        return

    if not target_user and not link:
        await interaction.followup.send("❌ Provide target_user or link", ephemeral=True)
        return

    data = load_data()
    new_balance = max(0, get_balance(data, interaction.guild.id, vip_user.id) - amount)
    set_balance(data, interaction.guild.id, vip_user.id, new_balance)
    save_data(data)

    vrc_user = extract_vrc_user(link)
    final_target = vrc_user if vrc_user else target_user

    embed = discord.Embed(
        title="🚫 Ban Token Used",
        description=f"🎯 Target: `{final_target}`",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="VIP User", value=vip_user.mention)
    embed.add_field(name="Coins Used", value=str(amount))
    embed.add_field(name="New Balance", value=str(new_balance))
    embed.add_field(name="Handled By", value=interaction.user.mention)

    if link:
        embed.add_field(name="Profile", value=link, inline=False)

    await interaction.followup.send(embed=embed)
    await send_log(interaction, embed)

# 🔁 TRANSFER
@tree.command(name="transfer")
async def transfer(
    interaction: discord.Interaction,
    from_user: discord.User,
    to_user: discord.User,
    amount: int
):
    await interaction.response.defer()

    if not has_permission(interaction):
        await interaction.followup.send("❌ No permission", ephemeral=True)
        return

    data = load_data()

    if get_balance(data, interaction.guild.id, from_user.id) < amount:
        await interaction.followup.send("❌ Not enough balance", ephemeral=True)
        return

    set_balance(data, interaction.guild.id, from_user.id,
                get_balance(data, interaction.guild.id, from_user.id) - amount)

    set_balance(data, interaction.guild.id, to_user.id,
                get_balance(data, interaction.guild.id, to_user.id) + amount)

    save_data(data)

    embed = discord.Embed(
        title="🔁 Transfer",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="From", value=from_user.mention)
    embed.add_field(name="To", value=to_user.mention)
    embed.add_field(name="Amount", value=str(amount))

    await interaction.followup.send(embed=embed)
    await send_log(interaction, embed)

# ======================
# ADMIN
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

    config[guild_id]["log_channel"] = int(channel.id)
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

    await interaction.response.send_message(f"✅ Added {role.mention}")

# ======================
# RUN
# ======================

print("🚀 Starting bot...")
client.run(os.getenv("TOKEN"))