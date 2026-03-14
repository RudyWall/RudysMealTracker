import discord
from discord import app_commands
from datetime import datetime
import os
from dotenv import load_dotenv
import re
import json


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
    "photo_message_id": None,
    "meals": {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    },
    "photos": {              
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    },
    "water": 0
}

# ------------ SAVE STATE ------------
SAVE_FILE = "tracker_state.json"

def save_state():
    with open(SAVE_FILE, "w") as f:
        json.dump({
            "date": data["date"],
            "message_id": data["message_id"],
            "photo_message_id": data["photo_message_id"]
        }, f)

def load_state():
    if not os.path.exists(SAVE_FILE):
        return

    with open(SAVE_FILE, "r") as f:
        saved = json.load(f)

    data["date"] = saved.get("date", "")
    data["message_id"] = saved.get("message_id")
    data["photo_message_id"] = saved.get("photo_message_id")

# ---------- FORMAT MESSAGE ----------
def format_message():
    liters = data["water"] * GLASS_LITERS

    def section(name, items):

        text = f"**{name}**\n"

        if not items:
            text += "-\n"
        else:
            text += "\n".join(f"• {i}" for i in items) + "\n"


        return text

    return f"""```Date: {data['date']}```

    {section("Breakfast", data["meals"]["breakfast"])}

    {section("Lunch", data["meals"]["lunch"])}

    {section("Dinner", data["meals"]["dinner"])}

    {section("Snacks", data["meals"]["snacks"])}

    **Water:** {data['water']} bottles 💧 ({liters:.2f} L)
    """

def format_photo_message():

    lines = []

    for meal, photos in data["photos"].items():
        for url in photos:
            lines.append(f"[{meal.capitalize()}]({url})")

    if not lines:
        return "No photos yet."

    return "\n".join(lines)


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

        # only process bullet lines
        if line.startswith("•") and current:

            item = line.replace("• ", "").strip()

            # ignore links (photos)
            if re.search(r"https?://", item):
                continue

            # ignore placeholder
            if item == "-" or item == "":
                continue

            meals[current].append(item)

    return meals

# --------- PARSE PHOTOS ----------
def parse_photo_message(content):

    photos = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    }

    for line in content.split("\n"):

        match = re.match(r'(https?://\S+)\s+"(\w+)"', line)

        if match:
            url = match.group(1)
            meal = match.group(2).lower()

            if meal in photos:
                photos[meal].append(url)

    return photos

# ---------- PARSE WATER ----------
def parse_water_count(content):

    match = re.search(r"\*\*Water:\*\*\s*(\d+)", content)

    if match:
        return int(match.group(1))

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

    async for msg in channel.history(limit=100):

        if msg.author != client.user:
            continue

        if "Date:" not in msg.content:
            continue

        # Check if message is within 24 hours
        age = (datetime.now(msg.created_at.tzinfo) - msg.created_at).total_seconds()

        if age > 86400:
            continue

        if today in msg.content:

            data["date"] = today
            data["message_id"] = msg.id
            data["meals"] = parse_existing_message(msg.content)
            data["water"] = parse_water_count(msg.content)

            await add_water_reactions(msg)
            save_state()
            return

    # If no valid message found, create new one
    data["date"] = today
    data["meals"] = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": []
    }
    data["water"] = 0

    msg = await channel.send(format_message())
    data["message_id"] = msg.id

    photo_msg = await channel.send(format_photo_message())
    data["photo_message_id"] = photo_msg.id

    save_state()

    await add_water_reactions(msg)


# ---------- UPDATE TRACKER ----------
async def update_tracker():
    channel = client.get_channel(CHANNEL_ID)
    msg = await channel.fetch_message(data["message_id"])

    await msg.edit(content=format_message())

async def update_photos():
    channel = client.get_channel(CHANNEL_ID)

    # If photo message doesn't exist yet, create it
    if not data["photo_message_id"]:
        msg = await channel.send(format_photo_message())
        data["photo_message_id"] = msg.id
        save_state()
        return

    try:
        msg = await channel.fetch_message(data["photo_message_id"])
        await msg.edit(content=format_photo_message())

    except discord.NotFound:
        msg = await channel.send(format_photo_message())
        data["photo_message_id"] = msg.id
        save_state()

# ---------- ADD MEAL ----------
async def add_meal(meal_type, food):
    await ensure_daily_message()
    data["meals"][meal_type].append(food)
    await update_tracker()


# -------- MEAL COMMANDS --------
@tree.command(name="breakfast", description="Add breakfast entry")
async def breakfast(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("breakfast", food)
    await interaction.followup.send("Breakfast added!", ephemeral=True)


@tree.command(name="lunch", description="Add lunch entry")
async def lunch(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("lunch", food)
    await interaction.followup.send("Lunch added!", ephemeral=True)


@tree.command(name="dinner", description="Add dinner entry")
async def dinner(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("dinner", food)
    await interaction.followup.send("Dinner added!", ephemeral=True)


@tree.command(name="snack", description="Add snack entry")
async def snack(interaction: discord.Interaction, food: str):
    await interaction.response.defer(ephemeral=True)
    await add_meal("snacks", food)
    await interaction.followup.send("Snack added!", ephemeral=True)

# -------- UPDATE COMMAND --------
@tree.command(name="update", description="Sync or create today's tracker")
async def update(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    await ensure_daily_message()

    channel = client.get_channel(CHANNEL_ID)
    msg = await channel.fetch_message(data["message_id"])

    # re-parse photo message to sync memory
    if data["photo_message_id"]:

        try:
            photo_msg = await channel.fetch_message(data["photo_message_id"])
            data["photos"] = parse_photo_message(photo_msg.content)

        except discord.NotFound:
            print("Photo message missing, recreating...")
            await update_photos()

    else:
        # create photo message if missing
        await update_photos()
    

    await add_water_reactions(msg)

    await interaction.followup.send(
        f"Tracker synced for **{data['date']}**",
        ephemeral=True
    )

# ------- PHOTO COMMAND ---------
@tree.command(name="addphoto", description="Upload a photo for a meal")
@app_commands.choices(meal=[
    app_commands.Choice(name="Breakfast", value="breakfast"),
    app_commands.Choice(name="Lunch", value="lunch"),
    app_commands.Choice(name="Dinner", value="dinner"),
    app_commands.Choice(name="Snack", value="snacks")
])
async def addphoto(
    interaction: discord.Interaction,
    meal: app_commands.Choice[str],
    image: discord.Attachment
):

    await interaction.response.defer(ephemeral=True)

    # make sure today's tracker exists
    await ensure_daily_message()

    # store the image URL
    data["photos"][meal.value].append(image.url)

    # update the photo message
    await update_photos()

    await interaction.followup.send(
        f"Photo added to **{meal.name}** 📷",
        ephemeral=True
    )

# -------- REMOVE SYSTEM --------
@tree.command(name="remove", description="Remove meal entry or photo")
async def remove(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    await ensure_daily_message()

    await interaction.followup.send(
        "Choose category",
        view=MealSelectView(),
        ephemeral=True
    )


# ---------- CATEGORY SELECT ----------
class MealSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(label="Breakfast", value="breakfast"),
            discord.SelectOption(label="Lunch", value="lunch"),
            discord.SelectOption(label="Dinner", value="dinner"),
            discord.SelectOption(label="Snacks", value="snacks")
        ]

        super().__init__(placeholder="Select category", options=options)

    async def callback(self, interaction: discord.Interaction):

        meal_type = self.values[0]

        if not data["meals"][meal_type] and not data["photos"][meal_type]:

            await interaction.response.edit_message(
                content="Nothing to remove in this category.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Select item to remove",
            view=ItemSelectView(meal_type)
        )


# ---------- ITEM SELECT ----------
class ItemSelect(discord.ui.Select):

    def __init__(self, meal_type):

        self.meal_type = meal_type

        options = []

        # meals
        for i, meal in enumerate(data["meals"][meal_type]):
            options.append(
                discord.SelectOption(
                    label=f"{i+1}. {meal}",
                    value=f"meal_{i}"
                )
            )

        # photos
        for i, photo in enumerate(data["photos"][meal_type]):

            filename = photo.split("/")[-1][:50]

            options.append(
                discord.SelectOption(
                    label=f"📷 {filename}",
                    value=f"photo_{i}"
                )
            )

        super().__init__(placeholder="Select item", options=options)

    async def callback(self, interaction: discord.Interaction):

        selected = self.values[0]

        type_, index = selected.split("_")
        index = int(index)

        if type_ == "meal":

            removed = data["meals"][self.meal_type].pop(index)

            await update_tracker()

            message = f"Removed meal **{removed}**"

        else:

            data["photos"][self.meal_type].pop(index)

            await update_photos()

            message = "Removed 📷 photo"

        await interaction.response.edit_message(
            content=message,
            view=None
        )


# ---------- VIEWS ----------
class MealSelectView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(MealSelect())


class ItemSelectView(discord.ui.View):

    def __init__(self, meal_type):
        super().__init__(timeout=60)
        self.add_item(ItemSelect(meal_type))


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
    load_state()

    channel = client.get_channel(CHANNEL_ID)

    if data["message_id"]:
        try:
            msg = await channel.fetch_message(data["message_id"])

            data["meals"] = parse_existing_message(msg.content)
            data["water"] = parse_water_count(msg.content)

            if data["photo_message_id"]:
                try:
                    photo_msg = await channel.fetch_message(data["photo_message_id"])
                    data["photos"] = parse_photo_message(photo_msg.content)
                except discord.NotFound:
                    print("Photo message missing, recreating...")
                    await update_photos()

            await add_water_reactions(msg)

        except discord.NotFound:
            print("Tracker message missing, creating a new one...")
            data["message_id"] = None
            await ensure_daily_message()

    else:
        await ensure_daily_message()

    await tree.sync()
    print("Logged in as", client.user)

client.run(TOKEN)