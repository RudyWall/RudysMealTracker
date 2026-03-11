import discord
from discord import app_commands
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1473154411583901746

GLASS_LITERS = 0.85

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

data = {
    "date": "",
    "message_id": None,
    "meals": {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    },
    "water": 0
}

# ---------- FORMAT MESSAGE ----------
def format_message():
    liters = data["water"] * GLASS_LITERS

    def section(name, items):
        if not items:
            return f"**{name}**\n-"
        return f"**{name}**\n" + "\n".join(f"• {i}" for i in items)

    return f"""```Date: {data['date']}```

{section("Breakfast", data["meals"]["breakfast"])}

{section("Lunch", data["meals"]["lunch"])}

{section("Dinner", data["meals"]["dinner"])}

{section("Snacks", data["meals"]["snacks"])}

**Water:** {data['water']} bottles 💧 ({liters:.2f} L)
"""

# ---------- PARSE EXISTING MESSAGE ----------
def parse_existing_message(content):
    meals = {"breakfast": [], "lunch": [], "dinner": [], "snacks": []}
    current = None

    for line in content.split("\n"):
        line = line.strip()

        if line.startswith("**Breakfast**"):
            current = "breakfast"
            continue
        if line.startswith("**Lunch**"):
            current = "lunch"
            continue
        if line.startswith("**Dinner**"):
            current = "dinner"
            continue
        if line.startswith("**Snacks**"):
            current = "snacks"
            continue

        if line.startswith("•") and current:
            meals[current].append(line.replace("• ", ""))

    return meals


# ---------- PARSE WATER ----------
def parse_water_count(content):
    for line in content.split("\n"):
        if line.startswith("**Water:**"):
            try:
                return int(line.split("**Water:**")[1].split("glasses")[0].strip())
            except:
                return 0
    return 0


# ---------- ADD WATER REACTIONS ----------
async def add_water_reactions(msg):
    emojis = [str(r.emoji) for r in msg.reactions]

    try:
        if "💧" not in emojis:
            await msg.add_reaction("💧")

        if "➖" not in emojis:
            await msg.add_reaction("➖")
    except Exception as e:
        print("Reaction add failed:", e)


# ---------- ENSURE DAILY MESSAGE ----------
async def ensure_daily_message():
    today = datetime.now().strftime("%B %d")
    channel = client.get_channel(CHANNEL_ID)

    if data["date"] == today and data["message_id"]:
        try:
            await channel.fetch_message(data["message_id"])
            return
        except:
            pass

    async for msg in channel.history(limit=50):
        if msg.author == client.user and f"Date: {today}" in msg.content:

            data["date"] = today
            data["message_id"] = msg.id
            data["meals"] = parse_existing_message(msg.content)
            data["water"] = parse_water_count(msg.content)

            await add_water_reactions(msg)
            return

    data["date"] = today
    data["meals"] = {"breakfast": [], "lunch": [], "dinner": [], "snacks": []}
    data["water"] = 0

    msg = await channel.send(format_message())
    data["message_id"] = msg.id

    await add_water_reactions(msg)


# ---------- UPDATE TRACKER ----------
async def update_tracker():
    channel = client.get_channel(CHANNEL_ID)
    msg = await channel.fetch_message(data["message_id"])

    await msg.edit(content=format_message())


# ---------- ADD MEAL ----------
async def add_meal(meal_type, food):
    await ensure_daily_message()
    data["meals"][meal_type].append(food)
    await update_tracker()


# -------- MEAL COMMANDS --------
@tree.command(name="breakfast")
async def breakfast(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("breakfast", food)
    await interaction.followup.send("Breakfast added!", ephemeral=True)


@tree.command(name="lunch")
async def lunch(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("lunch", food)
    await interaction.followup.send("Lunch added!", ephemeral=True)


@tree.command(name="dinner")
async def dinner(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("dinner", food)
    await interaction.followup.send("Dinner added!", ephemeral=True)


@tree.command(name="snack")
async def snack(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("snacks", food)
    await interaction.followup.send("Snack added!", ephemeral=True)


# -------- REMOVE SYSTEM --------
class MealSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(label="Breakfast", value="breakfast"),
            discord.SelectOption(label="Lunch", value="lunch"),
            discord.SelectOption(label="Dinner", value="dinner"),
            discord.SelectOption(label="Snacks", value="snacks")
        ]
        super().__init__(placeholder="Select meal type", options=options)

    async def callback(self, interaction: discord.Interaction):
        meal_type = self.values[0]

        if not data["meals"][meal_type]:
            await interaction.response.edit_message(
                content="No items in that category",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Select item to remove",
            view=ItemSelectView(meal_type)
        )


class ItemSelect(discord.ui.Select):

    def __init__(self, meal_type):
        self.meal_type = meal_type

        options = [
            discord.SelectOption(
                label=f"{i+1}. {item}",
                value=str(i)
            )
            for i, item in enumerate(data["meals"][meal_type])
        ]

        super().__init__(placeholder="Select item", options=options)

    async def callback(self, interaction: discord.Interaction):

        index = int(self.values[0])
        removed = data["meals"][self.meal_type].pop(index)

        await update_tracker()

        await interaction.response.edit_message(
            content=f"Removed **{removed}**",
            view=None
        )


class MealSelectView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(MealSelect())


class ItemSelectView(discord.ui.View):

    def __init__(self, meal_type):
        super().__init__(timeout=60)
        self.add_item(ItemSelect(meal_type))


@tree.command(name="remove")
async def remove(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Choose category",
        view=MealSelectView(),
        ephemeral=True
    )


# -------- WATER REACTIONS --------
@client.event
async def on_raw_reaction_add(payload):

    if payload.message_id != data["message_id"]:
        return

    if payload.user_id == client.user.id:
        return

    channel = client.get_channel(payload.channel_id)
    msg = await channel.fetch_message(payload.message_id)
    user = await client.fetch_user(payload.user_id)

    emoji = str(payload.emoji)

    if emoji == "💧":
        data["water"] += 1
        await update_tracker()

    elif emoji == "➖":
        data["water"] = max(0, data["water"] - 1)
        await update_tracker()

    try:
        await msg.remove_reaction(payload.emoji, user)
    except:
        pass


# -------- BOT READY --------
@client.event
async def on_ready():
    await tree.sync()
    print("Logged in as", client.user)

client.run(TOKEN)