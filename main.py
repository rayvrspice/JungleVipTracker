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

# balance 
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

    # 💰 USER VIEW (BANK STYLE)
    embed = discord.Embed(
        title="💰 Deposit Successful",
        description=f"**{amount} coins** were added to {member.mention}’s bag.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="📊 New Balance",
        value=f"**{new_balance} coins**",
        inline=False
    )

    embed.set_footer(text="Jungle VIP Banking System")
    embed.set_thumbnail(url=member.display_avatar.url)

    await interaction.followup.send(embed=embed)

    # 📊 LOG VIEW (CLEAN + GREEN)
    log_embed = discord.Embed(
        title="📊 Balance Update",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    log_embed.add_field(name="Action", value="ADD")
    log_embed.add_field(name="User", value=member.mention)
    log_embed.add_field(name="Amount", value=str(amount))
    log_embed.add_field(name="New Balance", value=str(new_balance))
    log_embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)

    await send_log(interaction, log_embed)

# SUBTRACT (FINAL CLEAN VERSION)
@tree.command(name="subtract")
@app_commands.describe(
    vip_user="VIP using coins",
    amount="Amount",
    target_user="Target name (recommended)",
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
        return await interaction.followup.send("❌ No permission", ephemeral=True)

    if not target_user and not link:
        return await interaction.followup.send("❌ Provide a target name or link", ephemeral=True)

    data = load_data()
    new_balance = max(0, get_balance(data, interaction.guild.id, vip_user.id) - amount)
    set_balance(data, interaction.guild.id, vip_user.id, new_balance)
    save_data(data)

    # 🎯 TARGET
    if target_user:
        final_target = target_user
    elif link:
        final_target = "VRChat User"
    else:
        final_target = "Unknown"

    embed = discord.Embed(
        title="🚫 Ban Token Used",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="🎯 Target", value=f"**{final_target}**", inline=False)
    embed.add_field(name="👤 VIP", value=vip_user.mention)
    embed.add_field(name="💰 Used", value=f"{amount} coins")
    embed.add_field(name="📊 Balance", value=str(new_balance))
    embed.add_field(name="🛠 Handled By", value=interaction.user.mention, inline=False)

    if link:
        embed.add_field(name="🔗 Profile", value=link, inline=False)

    embed.set_footer(text="Jungle VIP System")

    # Send embed FIRST
    await interaction.followup.send(embed=embed)

# Send link separately to force preview
    if link:
        await interaction.followup.send(link)

    await send_log(interaction, embed)

   

# TRANSFER

@tree.command(name="transfer")
async def transfer(
    interaction: discord.Interaction,
    from_user: discord.User,
    to_user: discord.User,
    amount: int
):
    await interaction.response.defer()

    if not has_permission(interaction):
        return await interaction.followup.send("❌ No permission", ephemeral=True)

    data = load_data()

    from_balance = get_balance(data, interaction.guild.id, from_user.id)

    if from_balance < amount:
        return await interaction.followup.send("❌ Not enough balance", ephemeral=True)

    # 💸 UPDATE BALANCES
    new_from_balance = from_balance - amount
    new_to_balance = get_balance(data, interaction.guild.id, to_user.id) + amount

    set_balance(data, interaction.guild.id, from_user.id, new_from_balance)
    set_balance(data, interaction.guild.id, to_user.id, new_to_balance)
    save_data(data)

    # 💰 USER VIEW (BANK STYLE)
    embed = discord.Embed(
        title="🔁 Transfer Complete",
        description=f"**{amount} coins** transferred from {from_user.mention} to {to_user.mention}.",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📉 Sender Balance",
        value=f"{from_user.mention}: **{new_from_balance} coins**",
        inline=False
    )

    embed.add_field(
        name="📈 Receiver Balance",
        value=f"{to_user.mention}: **{new_to_balance} coins**",
        inline=False
    )

    embed.add_field(
        name="🛠 Handled By",
        value=interaction.user.mention,
        inline=False
    )

    embed.set_footer(text="Jungle VIP Banking System")

    await interaction.followup.send(embed=embed)

    # 📊 LOG VIEW
    log_embed = discord.Embed(
        title="📊 Balance Transfer",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    log_embed.add_field(name="From", value=from_user.mention)
    log_embed.add_field(name="To", value=to_user.mention)
    log_embed.add_field(name="Amount", value=str(amount))
    log_embed.add_field(name="Sender Balance", value=str(new_from_balance))
    log_embed.add_field(name="Receiver Balance", value=str(new_to_balance))
    log_embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)

    await send_log(interaction, log_embed)


# Monthly VIP Coin Reward

@tree.command(name="monthlyvip")
async def monthlyvip(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()

    # Uses the same permission system as /add, /subtract, /transfer
    if not has_permission(interaction):
        return await interaction.followup.send(
            "❌ No permission",
            ephemeral=True
        )

    data = load_data()

    rewarded = 0
    total_distributed = 0
    coins_per_member = 5

    rewarded_members = []
    previous_total = 0
    new_total = 0

    for member in role.members:

        # Skip bots
        if member.bot:
            continue

        current_balance = get_balance(
            data,
            interaction.guild.id,
            member.id
        )

        updated_balance = current_balance + coins_per_member

        set_balance(
            data,
            interaction.guild.id,
            member.id,
            updated_balance
        )

        rewarded_members.append(
            f"{member.mention}: {current_balance} → {updated_balance}"
        )

        previous_total += current_balance
        new_total += updated_balance

        rewarded += 1
        total_distributed += coins_per_member

    save_data(data)

    # USER-FACING EMBED
    embed = discord.Embed(
        title="🎁 Monthly VIP Coins Distributed",
        description=(
            f"Added **{coins_per_member} coins** to every member with "
            f"{role.mention}"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="Members Rewarded",
        value=str(rewarded),
        inline=False
    )

    embed.add_field(
        name="Total Coins Distributed",
        value=str(total_distributed),
        inline=False
    )

    embed.set_footer(text="Jungle VIP Banking System")

    await interaction.followup.send(embed=embed)

    # DETAILED LOG EMBED
    log_embed = discord.Embed(
        title=f"📊 Monthly VIP Distribution - {datetime.utcnow().strftime('%B %Y')}",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )

    log_embed.add_field(
        name="VIP Role",
        value=role.mention,
        inline=False
    )

    log_embed.add_field(
        name="Coins Per Member",
        value=str(coins_per_member),
        inline=True
    )

    log_embed.add_field(
        name="Members Rewarded",
        value=str(rewarded),
        inline=True
    )

    log_embed.add_field(
        name="Total Coins Distributed",
        value=str(total_distributed),
        inline=True
    )

    log_embed.add_field(
        name="Handled By",
        value=interaction.user.mention,
        inline=False
    )

    # Split recipient list across multiple fields if needed
    recipient_chunks = []
    current_chunk = ""

    for entry in rewarded_members:
        line = entry + "\n"

        if len(current_chunk) + len(line) > 1000:
            recipient_chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += line

    if current_chunk:
        recipient_chunks.append(current_chunk)

    for i, chunk in enumerate(recipient_chunks):
        log_embed.add_field(
            name="Recipients" if i == 0 else f"Recipients (Continued {i})",
            value=chunk,
            inline=False
        )

    log_embed.add_field(
        name="Distribution Summary",
        value=(
            f"Previous Total: {previous_total}\n"
            f"Coins Added: {total_distributed}\n"
            f"New Total: {new_total}"
        ),
        inline=False
    )

    await send_log(interaction, log_embed)

# Shows leadership Board

@tree.command(
    name="leaderboard",
    description="View the server coin leaderboard."
)
async def leaderboard(interaction: discord.Interaction):

    data = load_data()

    guild_id = str(interaction.guild.id)

    if guild_id not in data:
        return await interaction.response.send_message(
            "No balances found.",
            ephemeral=True
        )

    leaderboard_data = []

    for member in interaction.guild.members:

        if member.bot:
            continue

        balance = get_balance(
            data,
            interaction.guild.id,
            member.id
        )

        if balance <= 0:
            continue

        leaderboard_data.append((member, balance))

    leaderboard_data.sort(
        key=lambda x: x[1],
        reverse=True
    )

    if not leaderboard_data:
        return await interaction.response.send_message(
            "No members currently have any coins.",
            ephemeral=True
        )

    lines = []

    for position, (member, balance) in enumerate(
        leaderboard_data[:10],
        start=1
    ):

        if position == 1:
            prefix = "🥇"
        elif position == 2:
            prefix = "🥈"
        elif position == 3:
            prefix = "🥉"
        else:
            prefix = f"#{position}"

        lines.append(
            f"{prefix} {member.mention} — **{balance}** Coins"
        )

    total_coins = sum(balance for _, balance in leaderboard_data)

    embed = discord.Embed(
        title="🏆 Coin Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Total Coins In Circulation",
        value=str(total_coins),
        inline=False
    )

    embed.set_footer(
        text=f"Showing Top {min(10, len(leaderboard_data))} of {len(leaderboard_data)} members • Zero balances hidden"
    )

    await interaction.response.send_message(
        embed=embed
    )


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