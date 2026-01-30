import discord
from discord.ext import commands
import re
import os
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio
import sqlite3

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

smtp_server = os.getenv("SMTP_SERVER") or "smtp.mailgun.org"
smtp_port = os.getenv("SMTP_PORT") or 465
smtp_username = os.getenv("SMTP_USERNAME") or "noreply@taqneeqfest.com"
smtp_password = os.getenv("SMTP_PASSWORD") or "password"

help_role = 1464898721501413537

rule_channel = 1464898722541342772
bot_channel = 1464898722541342779
webhook_channel_id = 1464898722541342780

category_a1 = 1466872692505575434
category_a2 = 1466872860059373628
category_a3 = 1466872926761652224

category_b1 = 1466872963180794056
category_b2 = 1466872998366806026
category_b3 = 1466873071917863065

EMOJIS = ["🤺", "🦾", "🦿"]
DB_PATH = "team_invites.db"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------- INVITE CACHE --------
invite_cache = {}  # {guild_id: {invite_code: uses}}


# ---------- DATABASE ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        invite_link TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        team_number TEXT NOT NULL,
        email TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS invite_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        name TEXT NOT NULL,
        team_number TEXT NOT NULL,
        invite_link TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def db_execute(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()


def db_fetchone(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row


# ---------- HELPERS ----------

def is_valid_email(email):
    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email)


async def generate_invite_link(channel):
    invite = await channel.create_invite(max_uses=2, unique=True)
    invite_cache.setdefault(channel.guild.id, {})[invite.code] = 0
    return invite.url


def send_email(to_email, name, team_no, invite_link):
    try:
        # Read HTML template
        with open("email.html", "r", encoding="utf-8") as file:
            html = (
                file.read()
                .replace("{{name}}", name)
                .replace("{{team_no}}", team_no)
                .replace("{{invite_link}}", invite_link)
            )

        # Create email
        msg = MIMEMultipart()
        msg["From"] = smtp_username
        msg["To"] = to_email
        msg["Subject"] = "Cyber Cypher 5.0 Invitation"
        msg.attach(MIMEText(html, "html"))

        # Connect using SSL
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, to_email, msg.as_string())
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Email error: {e}")


# ---------- COMMANDS ----------

@bot.command()
async def register(ctx, name="", email="", team_number=""):
    if ctx.channel.id != bot_channel:
        return

    if not name or not email or not team_number:
        await ctx.send("Usage: `!register <name> <email> <team_id>`")
        return

    name = name.title()

    if not is_valid_email(email):
        await ctx.send("Invalid email.")
        return

    invite_channel = ctx.guild.get_channel(rule_channel)
    invite_link = await generate_invite_link(invite_channel)

    loop = asyncio.get_running_loop()

    loop.run_in_executor(
        None,
        db_execute,
        "INSERT INTO participants VALUES (?, ?, ?, ?)",
        (invite_link, name, team_number, email)
    )

    loop.run_in_executor(
        None,
        db_execute,
        "INSERT INTO invite_logs (email, name, team_number, invite_link) VALUES (?, ?, ?, ?)",
        (email, name, team_number, invite_link)
    )

    loop.run_in_executor(
        None,
        send_email,
        email,
        name,
        team_number,
        invite_link
    )
    
    await ctx.send(f"{name} - {team_number} - `{invite_link}`.")

@bot.command()
async def ping(ctx):
    if ctx.channel.id != bot_channel:
        await ctx.send("You can only use this command in the bot channel.", delete_after=5)
        return

    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 `{latency}ms`")

@bot.command()
async def verbose(ctx, *, message: str = ""):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You do not have permission to use this command.", delete_after=5)
        return

    if not message:
        await ctx.send("Usage: `!verbose <message>`", delete_after=5)
        return

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Bot might not have delete perms, fail silently

    await ctx.send(message)

@bot.command()
async def purge(ctx, amount: int = 20):
    """Delete messages in the current channel. Default: 20, Max: 100"""
    
    # Check permissions
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("You do not have permission to use this command.", delete_after=5)
        return
    
    # Clamp the amount
    if amount < 1:
        await ctx.send("Please specify a positive number of messages to delete.", delete_after=5)
        return
    if amount > 100:
        await ctx.send("You can delete a maximum of 100 messages at once.", delete_after=5)
        return

    try:
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"✅ Successfully deleted {len(deleted)} messages.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Failed to delete messages: {e}", delete_after=5)


# ---------- EVENTS ----------

@bot.event
async def on_ready():
    init_db()
    print(f"Logged in as {bot.user}")

    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}

    bot.loop.create_task(delete_used_invites())


@bot.event
async def on_invite_create(invite):
    invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses


@bot.event
async def on_member_join(member):
    guild = member.guild
    invites = await guild.invites()

    before = invite_cache.get(guild.id, {})
    used_invite = None

    for invite in invites:
        if invite.code in before and invite.uses > before[invite.code]:
            used_invite = invite
            break

    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}

    if not used_invite:
        print("No matching invite found.")
        return

    row = db_fetchone(
        "SELECT name, team_number FROM participants WHERE invite_link = ?",
        (used_invite.url,)
    )

    if not row:
        print("Invite not in DB.")
        return

    name, team_number = row

    try:
        await used_invite.delete()
    except:
        pass

    role = discord.utils.get(guild.roles, name="Participants 💻")
    if role:
        await member.add_roles(role)

    await member.edit(nick=f"[🧠] {team_number} - {name}")
    await member_handler(member, team_number)

    db_execute(
        "DELETE FROM participants WHERE invite_link = ?",
        (used_invite.url,)
    )


# ---------- CHANNEL LOGIC ----------

async def member_handler(member, team_id):
    channel = await get_or_make_channel(team_id, member.guild)
    await channel.set_permissions(member, view_channel=True, connect=True)


async def get_or_make_channel(team_id, guild):
    team_type = team_id[0]
    team_no = int(team_id[1:])
    if team_type == "A":
        category_id = (
            category_a1 if team_no <= 50 else
            category_a2 if team_no <= 100 else
            category_a3 if team_no <= 150 else
            None
        )
    elif team_type == "B":
        category_id = (
            category_b1 if team_no <= 50 else
            category_b2 if team_no <= 100 else
            category_b3 if team_no <= 150 else
            None
        )
    else:
        category_id = None

    if not category_id:
        raise ValueError("Invalid team type or number")

    category = guild.get_channel(category_id)

    channel_name = f"Team {team_type}{str(team_no).zfill(3)} {EMOJIS[team_no % 3]}"
    for ch in category.channels:
        if ch.name == channel_name:
            return ch

    helper_role = guild.get_role(help_role)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        helper_role: discord.PermissionOverwrite(view_channel=True, connect=True)
    }

    return await guild.create_voice_channel(channel_name, category=category, overwrites=overwrites)


# ---------- WEBHOOK ----------

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id == webhook_channel_id and message.webhook_id:
        if message.content.startswith("!register"):
            parts = message.content.split()
            if len(parts) != 4:
                await message.channel.send("Invalid format.")
                return

            name, email, team_number = parts[1], parts[2], parts[3]
            name = name.title()

            if not is_valid_email(email):
                await message.channel.send("Invalid email.")
                return

            invite_channel = message.guild.get_channel(rule_channel)
            invite_link = await generate_invite_link(invite_channel)

            loop = asyncio.get_running_loop()

            await loop.run_in_executor(
                None,
                db_execute,
                "INSERT INTO participants VALUES (?, ?, ?, ?)",
                (invite_link, name, team_number, email)
            )

            await loop.run_in_executor(
                None,
                db_execute,
                "INSERT INTO invite_logs (email, name, team_number, invite_link) VALUES (?, ?, ?, ?)",
                (email, name, team_number, invite_link)
            )

            await loop.run_in_executor(
                None,
                send_email,
                email,
                name,
                team_number,
                invite_link
            )

            await message.channel.send(f"{name} - {team_number} - `{invite_link}`.")

    await bot.process_commands(message)


# ---------- INVITE CLEANUP ----------

async def delete_used_invites():
    await bot.wait_until_ready()
    while True:
        try:
            for guild in bot.guilds:
                for invite in await guild.invites():
                    if invite.inviter == bot.user and invite.uses > 1:
                        await invite.delete()
        except Exception as e:
            print(f"Invite cleanup error: {e}")

        await asyncio.sleep(30)

bot.run(BOT_TOKEN)