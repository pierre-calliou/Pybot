import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime, timezone
import aiohttp

# Configuration
TOKEN = "MTM0NjQyMjU1Mjc2Njk3MTk0NA.GpUEiX.dltwkoCgUA_FNuhQ5KvyskXUp0q5hik6M_v1Ck"
OPENROUTER_API_KEY = "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"
MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
WEBHOOK_URL = "https://discord.com/api/webhooks/1396830542539919485/BPOKblFAWPZk72Qf7LtIlyojSsKvDHzo26QjyyMSE8cyQnHEWkTU0zcZCm_0JDH8EXJT"
GUILD_ID = 1339652496284586055  # Ton serveur de test pour synchronisation

# Initialisation
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
data_file = "data.json"

# Chargement ou création des données
if not os.path.exists(data_file):
    with open(data_file, "w") as f:
        json.dump({}, f)

with open(data_file, "r") as f:
    data = json.load(f)

# Sauvegarde
async def save_data():
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)

# Vérifie que la commande est utilisée dans un serveur (pas en DM)
def is_guild_context(interaction: discord.Interaction):
    return interaction.guild is not None

# Log uniquement certaines commandes (admin et achat)
async def log_command(interaction: discord.Interaction):
    embed = {
        "title": "📌 Commande exécutée",
        "fields": [
            {"name": "Utilisateur", "value": f"{interaction.user} (ID: {interaction.user.id})", "inline": True},
            {"name": "Commande", "value": f"/{interaction.command.name}", "inline": True},
            {"name": "Serveur", "value": f"{interaction.guild.name} (ID: {interaction.guild.id})", "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "color": 0x00FF00
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"[LOGGING ERROR] Impossible d’envoyer au webhook : {e}")

# Utilitaires
def get_user_data(user_id):
    if str(user_id) not in data:
        data[str(user_id)] = {"credits": 10, "money": 0, "history": [], "last_reset": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    return data[str(user_id)]

# Événement ready + sync commands
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print("✅ Commandes synchronisées sur le serveur", GUILD_ID)

# Commandes

@bot.tree.command(name="ask", description="Pose une question à l’IA")
@app_commands.describe(question="Ta question à l'IA")
async def ask(interaction: discord.Interaction, question: str):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return

    user_data = get_user_data(interaction.user.id)
    if user_data["credits"] <= 0:
        await interaction.response.send_message("❌ Tu n’as plus de crédits.", ephemeral=True)
        return

    user_data["credits"] -= 1
    user_data["history"].append({"role": "user", "content": question})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "Referer": "https://openrouter.ai/",
        "User-Agent": "DiscordBot/1.0"
    }

    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": "Tu es un assistant IA sur Discord."}] + user_data["history"][-10:]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body) as resp:
            text = await resp.text()
            print(f"Status {resp.status}, Response: {text}")
            try:
                res = await resp.json()
                reply = res["choices"][0]["message"]["content"]
            except Exception as e:
                print("Erreur JSON:", e)
                reply = "❌ Erreur IA ou modèle indisponible."
                user_data["credits"] += 1
    user_data["history"].append({"role": "assistant", "content": reply})
    await save_data()
    await interaction.response.send_message(f"🤖 Réponse IA : {reply}", ephemeral=True)

@bot.tree.command(name="stats", description="Afficher tes crédits et ton argent")
async def stats(interaction: discord.Interaction):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return
    user_data = get_user_data(interaction.user.id)
    await interaction.response.send_message(
        f"💰 Argent : {user_data['money']}\n🔋 Crédits : {user_data['credits']}", ephemeral=True)

@bot.tree.command(name="daily", description="Recevoir 100€ par jour")
async def daily(interaction: discord.Interaction):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return
    user_data = get_user_data(interaction.user.id)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user_data.get("last_daily") == today:
        await interaction.response.send_message("🕐 Tu as déjà récupéré ta récompense aujourd’hui !", ephemeral=True)
        return
    user_data["money"] += 100
    user_data["last_daily"] = today
    await save_data()
    await interaction.response.send_message("🎉 Tu as reçu 100€ !", ephemeral=True)

@bot.tree.command(name="buycredits", description="Acheter plusieurs crédits IA pour 50€ chacun")
@app_commands.describe(amount="Nombre de crédits à acheter")
async def buycredits(interaction: discord.Interaction, amount: int):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    user_data = get_user_data(interaction.user.id)
    prix_total = 50 * amount

    if amount <= 0:
        await interaction.followup.send("❌ Le nombre de crédits doit être supérieur à zéro.")
        return

    if user_data["money"] < prix_total:
        await interaction.followup.send(f"❌ Pas assez d’argent. Il faut {prix_total}€.")
        return

    user_data["money"] -= prix_total
    user_data["credits"] += amount
    await save_data()
    await interaction.followup.send(f"✅ Tu as acheté {amount} crédit(s) IA pour {prix_total}€ !")

    # Log achat
    await log_command(interaction)

@bot.tree.command(name="addmoney", description="[ADMIN] Donner de l’argent à un utilisateur")
@app_commands.describe(user="Utilisateur à créditer", amount="Montant à ajouter")
async def addmoney(interaction: discord.Interaction, user: discord.User, amount: int):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Tu n’es pas admin.", ephemeral=True)
        return
    user_data = get_user_data(user.id)
    user_data["money"] += amount
    await save_data()
    await interaction.response.send_message(f"✅ {amount}€ ajoutés à {user.name}.", ephemeral=True)

    # Log admin
    await log_command(interaction)

@bot.tree.command(name="removemoney", description="[ADMIN] Retirer de l’argent à un utilisateur")
@app_commands.describe(user="Utilisateur à débiter", amount="Montant à retirer")
async def removemoney(interaction: discord.Interaction, user: discord.User, amount: int):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Tu n’es pas admin.", ephemeral=True)
        return
    user_data = get_user_data(user.id)
    user_data["money"] = max(0, user_data["money"] - amount)
    await save_data()
    await interaction.response.send_message(f"✅ {amount}€ retirés à {user.name}.", ephemeral=True)

    # Log admin
    await log_command(interaction)

@bot.tree.command(name="clearhistory", description="Supprimer l'historique de ta discussion avec l'IA")
async def clearhistory(interaction: discord.Interaction):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return
    user_data = get_user_data(interaction.user.id)
    user_data["history"] = []
    await save_data()
    await interaction.response.send_message("🗑️ Ton historique a été supprimé.", ephemeral=True)

@bot.tree.command(name="help", description="Afficher l’aide du bot")
async def help(interaction: discord.Interaction):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return
    message = """
📖 **Commandes disponibles :**

/ask [question] - Pose une question à l’IA
/stats - Voir tes crédits et ton argent
/daily - Gagner 100€ par jour
/buycredits - Acheter crédits IA pour 50€ chacun
/clearhistory - Supprimer ton historique IA
/addmoney - [ADMIN] Donner de l’argent à un membre
/removemoney - [ADMIN] Retirer de l’argent à un membre
/help - Voir cette aide
"""
    await interaction.response.send_message(message, ephemeral=True)

bot.run(TOKEN)
