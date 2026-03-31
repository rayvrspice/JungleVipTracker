import discord
from discord import app_commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

load_dotenv()

DATA_FILE = "/home/ubuntu/JungleVipTracker/balances.json"
CONFIG_FILE = "/home/ubuntu/JungleVipTracker/config.json"

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ======================
# DATA
# ======================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

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
# CONFIG
# ======================

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def get_guild_config(guild_id):
    config = load_config()
    guild_id = str(guild_id)

    if guild_id not in config:
        config[guild_id] = {"allowed_roles": [], "log_channel": None}
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
# VRCHAT NAME SCRAPER
# ======================

def get_vrc_username(link):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(link, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.find("title")

        if title:
            return title.text.replace("VRChat - ", "").strip()

        return "VRChat User"
    except:
        return "VRChat User"

# ======================
# LOGGING
# ======================

async def send_log(interaction, embed):
    guild_config = get_guild_config(interaction.guild.id)
    channel_id = guild_config.get("log_channel")

    if not channel_id:
        return

    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        channel = await client.fetch_channel(channel_id)

    await channel.send(embed=embed)

# ======================
# READY
# ======================

@client.event
async def on_ready():
    if not hasattr(client, "synced"):
        await tree.sync()
        client.synced = True
    print(f"Logged in as {client.user}")

# ======================
# COMMANDS
# ======================

@tree.command(name="balance")
async def balance(interaction: discord.Interaction, member: discord.User = None):
    member = member or interaction.user

    data = load_data()
    bal = get_balance(data, interaction.guild.id, member.id)

    embed = discord.Embed(
        description=f"💰 **{member.name}**: {bal} coins",
        color=discord.Color.gold()
    )

    embed.set_author(name="Bank Account", icon_url=member.display_avatar.url)

    await interaction.response.send_message(embed=embed)

# ADD
@tree.command(name="add")
async def add(interaction: discord.Interaction, member: discord.User, amount: int):
    await interaction.response.defer()

    if not has_permission(interaction):
        return await interaction.followup.send("❌ No permission", ephemeral=True)

    data = load_data()
    new_balance = get_balance(data, interaction.guild.id, member.id) + amount
    set_balance(data, interaction.guild.id, member.id, new_balance)
    save_data(data)

    embed = discord.Embed(title="➕ Added", color=discord.Color.green())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Amount", value=amount)
    embed.add_field(name="Balance", value=new_balance)

    await interaction.followup.send(embed=embed)
    await send_log(interaction, embed)

# SUBTRACT (FINAL FIXED)
@tree.command(name="subtract")
@app_commands.describe(
    vip_user="VIP using coins",
    amount="Amount",
    target_user="Name if no link",
    link="VRChat profile link"
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
        return await interaction.followup.send("❌ No permission", ephemeral=True)

    if not target_user and not link:
        return await interaction.followup.send("❌ Provide name or link", ephemeral=True)

    data = load_data()
    new_balance = max(0, get_balance(data, interaction.guild.id, vip_user.id) - amount)
    set_balance(data, interaction.guild.id, vip_user.id, new_balance)
    save_data(data)

    # 🔥 GET REAL NAME
    if link:
        final_target = get_vrc_username(link)
    else:
        final_target = target_user

    embed = discord.Embed(
        title="🚫 Ban Token Used",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="🎯 Target", value=final_target, inline=False)
    embed.add_field(name="👤 VIP", value=vip_user.mention)
    embed.add_field(name="💰 Used", value=amount)
    embed.add_field(name="📊 Balance", value=new_balance)
    embed.add_field(name="🛠 Staff", value=interaction.user.mention)

    if link:
        embed.add_field(name="🔗 Profile", value=link, inline=False)

    await interaction.followup.send(embed=embed)
    await send_log(interaction, embed)

# TRANSFER
@tree.command(name="transfer")
async def transfer(interaction: discord.Interaction, from_user: discord.User, to_user: discord.User, amount: int):
    await interaction.response.defer()

    if not has_permission(interaction):
        return await interaction.followup.send("❌ No permission", ephemeral=True)

    data = load_data()

    if get_balance(data, interaction.guild.id, from_user.id) < amount:
        return await interaction.followup.send("❌ Not enough balance", ephemeral=True)

    set_balance(data, interaction.guild.id, from_user.id,
                get_balance(data, interaction.guild.id, from_user.id) - amount)

    set_balance(data, interaction.guild.id, to_user.id,
                get_balance(data, interaction.guild.id, to_user.id) + amount)

    save_data(data)

    embed = discord.Embed(title="🔁 Transfer", color=discord.Color.blue())
    embed.add_field(name="From", value=from_user.mention)
    embed.add_field(name="To", value=to_user.mention)
    embed.add_field(name="Amount", value=amount)

    await interaction.followup.send(embed=embed)
    await send_log(interaction, embed)

# ADMIN
@tree.command(name="setlogchannel")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)

    config = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id not in config:
        config[guild_id] = {"allowed_roles": [], "log_channel": None}

    config[guild_id]["log_channel"] = channel.id
    save_config(config)

    await interaction.response.send_message("✅ Log channel set")

@tree.command(name="setrole")
async def setrole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)

    config = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id not in config:
        config[guild_id] = {"allowed_roles": [], "log_channel": None}

    roles = config[guild_id]["allowed_roles"]

    if role.id not in roles:
        roles.append(role.id)

    save_config(config)

    await interaction.response.send_message("✅ Role added")

# RUN
print("Starting bot...")
client.run(os.getenv("TOKEN"))