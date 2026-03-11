import discord
from discord import app_commands
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1473154411583901746

intents = discord.Intents.default()
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
    }
}


# ---------- FORMAT MESSAGE ----------
def format_message():
    liters = data['water'] * 0.85
    return f"""```Date: {data['date']}```

**Breakfast**
{chr(10).join('• ' + m for m in data['meals']['breakfast'])}

**Lunch**
{chr(10).join('• ' + m for m in data['meals']['lunch'])}

**Dinner**
{chr(10).join('• ' + m for m in data['meals']['dinner'])}

**Snacks**
{chr(10).join('• ' + m for m in data['meals']['snacks'])}

**Water:** {data['water']} glasses 💧 ({liters:.2f} L)
"""


# ---------- PARSE EXISTING MESSAGE ----------
def parse_existing_message(content):
    meals = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    }

    current = None
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("**Breakfast**"):
            current = "breakfast"
            continue
        elif line.startswith("**Lunch**"):
            current = "lunch"
            continue
        elif line.startswith("**Dinner**"):
            current = "dinner"
            continue
        elif line.startswith("**Snacks**"):
            current = "snacks"
            continue

        if line.startswith("•") and current:
            meals[current].append(line.replace("• ", ""))

    return meals


# ---------- ENSURE DAILY MESSAGE ----------
async def ensure_daily_message():
    today = datetime.now().strftime("%m-%d")
    channel = client.get_channel(CHANNEL_ID)

    # If we already know today's message, use it
    if data["date"] == today and data["message_id"]:
        try:
            await channel.fetch_message(data["message_id"])
            return
        except:
            pass

    # Search recent channel history for today's tracker
    async for msg in channel.history(limit=50):
        if msg.author == client.user and f"Date: {today}" in msg.content:
            data["date"] = today
            data["message_id"] = msg.id
            # Rebuild meal lists from existing message
            data["meals"] = parse_existing_message(msg.content)
            return

    # If not found, create new tracker
    data["date"] = today
    data["meals"] = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    }

    msg = await channel.send(format_message())
    data["message_id"] = msg.id


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


# -------- ADD MEAL COMMANDS --------
@tree.command(name="breakfast", description="Add a breakfast item")
async def breakfast(interaction: discord.Interaction, food: str):
    await add_meal("breakfast", food)
    await interaction.response.send_message("Breakfast added!", ephemeral=True)


@tree.command(name="lunch", description="Add a lunch item")
async def lunch(interaction: discord.Interaction, food: str):
    await add_meal("lunch", food)
    await interaction.response.send_message("Lunch added!", ephemeral=True)


@tree.command(name="dinner", description="Add a dinner item")
async def dinner(interaction: discord.Interaction, food: str):
    await add_meal("dinner", food)
    await interaction.response.send_message("Dinner added!", ephemeral=True)


@tree.command(name="snack", description="Add a snack")
async def snack(interaction: discord.Interaction, food: str):
    await add_meal("snacks", food)
    await interaction.response.send_message("Snack added!", ephemeral=True)

# -------- REMOVE SYSTEM --------
class MealSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Breakfast", value="breakfast"),
            discord.SelectOption(label="Lunch", value="lunch"),
            discord.SelectOption(label="Dinner", value="dinner"),
            discord.SelectOption(label="Snacks", value="snacks")
        ]
        super().__init__(placeholder="Select meal type...", options=options)

    async def callback(self, interaction: discord.Interaction):
        meal_type = self.values[0]

        if len(data["meals"][meal_type]) == 0:
            await interaction.response.edit_message(
                content="No items in that category.",
                view=None
            )
            return

        view = ItemSelectView(meal_type)
        await interaction.response.edit_message(
            content="Select which entry to remove:",
            view=view
        )


class ItemSelect(discord.ui.Select):
    def __init__(self, meal_type):
        self.meal_type = meal_type
        # Number each entry so duplicates are separate
        options = [
            discord.SelectOption(label=f"{i+1}. {item}", value=str(i))
            for i, item in enumerate(data["meals"][meal_type])
        ]
        super().__init__(placeholder="Select item to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        removed_item = data["meals"][self.meal_type].pop(index)
        await update_tracker()
        await interaction.response.edit_message(
            content=f"Removed **{removed_item}** from {self.meal_type}.",
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


@tree.command(name="remove", description="Remove a meal item")
async def remove(interaction: discord.Interaction):
    view = MealSelectView()
    await interaction.response.send_message(
        "Choose which meal category:",
        view=view,
        ephemeral=True
    )

# -------- REACTION HANDLERS FOR WATER TRACKER --------
@client.event
async def on_raw_reaction_add(payload):
    if payload.message_id != data["message_id"]:
        return
    if payload.user_id == client.user.id:
        return  # Ignore bot's own reactions

    if str(payload.emoji) == "➕":
        data["water"] += 1
        await update_tracker()
    elif str(payload.emoji) == "➖":
        data["water"] = max(0, data["water"] - 1)
        await update_tracker()


@client.event
async def on_raw_reaction_remove(payload):
    if payload.message_id != data["message_id"]:
        return
    if payload.user_id == client.user.id:
        return  # Ignore bot's own reactions

    if str(payload.emoji) == "➕":
        data["water"] = max(0, data["water"] - 1)
        await update_tracker()
    elif str(payload.emoji) == "➖":
        data["water"] += 1
        await update_tracker()



# -------- BOT READY --------
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")


client.run(TOKEN)