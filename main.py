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
# VRCHAT HELPER
# ======================

def extract_vrc_user(link: str):
    try:
        if link and "vrchat.com" in link and "/user/" in link:
            return link.split("/user/")[1]
    except:
        pass
    return None

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

# 💰 BALANCE
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

    if amount <= 0:
        await interaction.followup.send("❌ Amount must be positive", ephemeral=True)
        return

    data = load_data()
    current = get_balance(data, interaction.guild.id, member.id)
    new_balance = current + amount

    set_balance(data, interaction.guild.id, member.id, new_balance)
    save_data(data)

    await interaction.followup.send(f"✅ Added {amount} coins to <@{member.id}>")

# ➖ SUBTRACT (UPDATED 🔥)
@tree.command(name="subtract")
@app_commands.describe(
    vip_user="VIP user spending coins",
    amount="Amount to subtract",
    target_user="Target user (optional if link provided)",
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

    if amount <= 0:
        await interaction.followup.send("❌ Amount must be positive", ephemeral=True)
        return

    # ❗ Require at least one
    if not target_user and not link:
        await interaction.followup.send(
            "❌ You must provide a target_user or a VRChat link",
            ephemeral=True
        )
        return

    data = load_data()
    current = get_balance(data, interaction.guild.id, vip_user.id)
    new_balance = max(0, current - amount)

    set_balance(data, interaction.guild.id, vip_user.id, new_balance)
    save_data(data)

    # 🎯 Extract or fallback
    vrc_user = extract_vrc_user(link) if link else None
    final_target = vrc_user if vrc_user else target_user

    # 🔥 CLEAN EMBED
    embed = discord.Embed(
        title="🚫 Ban Token Used",
        description=f"**🎯 Target User:** `{final_target}`",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="👤 VIP User", value=vip_user.mention, inline=True)
    embed.add_field(name="🛠 Processed By", value=interaction.user.mention, inline=True)
    embed.add_field(name="💰 Coins Used", value=str(amount), inline=True)

    if link:
        embed.add_field(
            name="🌐 VRChat Profile",
            value=f"[Click to View Profile]({link})",
            inline=False
        )

    embed.set_footer(text="Jungle VIP System • Ban Record")

    await interaction.followup.send(embed=embed)

    # 📜 LOG CHANNEL
    guild_config = get_guild_config(interaction.guild.id)
    channel_id = guild_config.get("log_channel")

    if channel_id:
        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except:
                return

        await channel.send(embed=embed)
    # SEND TO LOG CHANNEL
    guild_config = get_guild_config(interaction.guild.id)
    channel_id = guild_config.get("log_channel")

    if channel_id:
        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except:
                return

        await channel.send(embed=embed)

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

    if amount <= 0:
        await interaction.followup.send("❌ Amount must be positive", ephemeral=True)
        return

    if from_user.id == to_user.id:
        await interaction.followup.send("❌ Cannot transfer to yourself", ephemeral=True)
        return

    data = load_data()

    from_balance = get_balance(data, interaction.guild.id, from_user.id)

    if from_balance < amount:
        await interaction.followup.send("❌ Not enough balance", ephemeral=True)
        return

    to_balance = get_balance(data, interaction.guild.id, to_user.id)

    new_from_balance = from_balance - amount
    new_to_balance = to_balance + amount

    set_balance(data, interaction.guild.id, from_user.id, new_from_balance)
    set_balance(data, interaction.guild.id, to_user.id, new_to_balance)

    save_data(data)

    await interaction.followup.send(
        f"🔁 Transferred **{amount} coins** from <@{from_user.id}> to <@{to_user.id}>"
    )

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