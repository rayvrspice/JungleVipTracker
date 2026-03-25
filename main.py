import discord
from discord import app_commands
import json
import os
from datetime import datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "alive"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

DATA_FILE = "balances.json"
CONFIG_FILE = "config.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_balance(data, user_id):
    return data.get(str(user_id), 0)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"allowed_roles": [], "log_channel": None}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def has_permission(interaction: discord.Interaction):
    config = load_config()
    allowed_roles = config.get("allowed_roles", [])
    user_roles = [role.id for role in interaction.user.roles]
    return any(role_id in allowed_roles for role_id in user_roles)

async def send_log(interaction, action, member, amount, new_balance):
    config = load_config()
    channel_id = config.get("log_channel")
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

@client.event
async def on_ready():
    if not hasattr(client, "synced"):
        await tree.sync()
        client.synced = True
    print(f"Logged in as {client.user}")

@tree.command(name="balance")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    data = load_data()
    await interaction.response.send_message(f"{member.mention} has {get_balance(data, member.id)} coins.")

@tree.command(name="add")
async def add(interaction: discord.Interaction, member: discord.Member, amount: int):
    await interaction.response.defer()
    if not has_permission(interaction):
        await interaction.followup.send("No permission", ephemeral=True)
        return
    data = load_data()
    new_balance = get_balance(data, member.id) + amount
    data[str(member.id)] = new_balance
    save_data(data)
    await interaction.followup.send(f"Added {amount}")
    await send_log(interaction, "ADD", member, amount, new_balance)

@tree.command(name="subtract")
async def subtract(interaction: discord.Interaction, member: discord.Member, amount: int):
    await interaction.response.defer()
    if not has_permission(interaction):
        await interaction.followup.send("No permission", ephemeral=True)
        return
    data = load_data()
    new_balance = get_balance(data, member.id) - amount
    data[str(member.id)] = new_balance
    save_data(data)
    await interaction.followup.send(f"Subtracted {amount}")
    await send_log(interaction, "SUBTRACT", member, amount, new_balance)



print("🚀 Starting bot...")
client.run(os.getenv("TOKEN"))
