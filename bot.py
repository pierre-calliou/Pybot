import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import aiohttp
from datetime import datetime, timezone, timedelta
from keep_alive import keep_alive



# Configuration
TOKEN = "MTM0NjQyMjU1Mjc2Njk3MTk0NA.GpUEiX.dltwkoCgUA_FNuhQ5KvyskXUp0q5hik6M_v1Ck"
OPENROUTER_API_KEY = "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"
MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
WEBHOOK_URL = "https://discord.com/api/webhooks/1396830542539919485/BPOKblFAWPZk72Qf7LtIlyojSsKvDHzo26QjyyMSE8cyQnHEWkTU0zcZCm_0JDH8EXJT"
GUILD_ID = 1339652496284586055  # Serveur de test

# Intents et bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
data_file = "data.json"

# Chargement ou création des données
if not os.path.exists(data_file):
    with open(data_file, "w") as f:
        json.dump({}, f)

with open(data_file, "r") as f:
    data = json.load(f)

# Sauvegarde des données
async def save_data():
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)

# Vérifie contexte serveur (pas en DM)
def is_guild_context(interaction: discord.Interaction):
    return interaction.guild is not None

# Récupère ou initialise les données utilisateur
def get_user_data(user_id):
    if str(user_id) not in data:
        data[str(user_id)] = {
            "credits": 10,
            "money": 0,
            "history": [],
            "last_reset": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "has_pass": False,
            "pass_expiry": None,
            "last_daily": None,
        }
    return data[str(user_id)]

# Fonction de log améliorée
async def log_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_name = str(interaction.user)
    guild_id = interaction.guild.id if interaction.guild else "DM"
    guild_name = interaction.guild.name if interaction.guild else "DM"
    command_name = interaction.command.name if interaction.command else "inconnu"

    # Récupération des arguments
    args = []
    if interaction.data and "options" in interaction.data:
        for opt in interaction.data["options"]:
            args.append(f"{opt['name']}={opt.get('value', '')}")
    args_str = ", ".join(args) if args else "aucun"

    user_data = get_user_data(user_id)
    credits = user_data.get("credits", "inconnu")
    money = user_data.get("money", "inconnu")
    has_pass = user_data.get("has_pass", False)
    pass_expiry = user_data.get("pass_expiry", "aucun")
    if pass_expiry is not None:
        pass_expiry = str(pass_expiry)

    embed = {
        "title": "📌 Commande exécutée",
        "fields": [
            {"name": "Utilisateur", "value": f"{user_name} (ID: {user_id})", "inline": True},
            {"name": "Serveur", "value": f"{guild_name} (ID: {guild_id})", "inline": True},
            {"name": "Commande", "value": f"/{command_name} ({args_str})", "inline": False},
            {"name": "Crédits", "value": str(credits), "inline": True},
            {"name": "Argent", "value": f"{money}€", "inline": True},
            {"name": "Pass actif", "value": "Oui" if has_pass else "Non", "inline": True},
            {"name": "Expiration pass", "value": pass_expiry, "inline": False},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "color": 0x00FF00
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"[LOGGING ERROR] Impossible d’envoyer au webhook : {e}")

# Ready + sync commandes
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

    # Si pass actif et valide, pas besoin de crédits
    if user_data["has_pass"]:
        expiry = user_data.get("pass_expiry")
        if expiry is not None:
            expiry_dt = datetime.fromisoformat(expiry)
            if expiry_dt < datetime.now(timezone.utc):
                # Pass expiré
                user_data["has_pass"] = False
                user_data["pass_expiry"] = None
            else:
                # Pass valide, on n'enlève pas de crédit
                pass
        else:
            # Pas d'expiry valide, on désactive pass
            user_data["has_pass"] = False

    if not user_data["has_pass"]:
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
                if not user_data["has_pass"]:
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
    has_pass = user_data.get("has_pass", False)
    pass_expiry = user_data.get("pass_expiry", "aucun")
    await interaction.response.send_message(
        f"💰 Argent : {user_data['money']}\n🔋 Crédits : {user_data['credits']}\n🎫 Pass mensuel actif : {'Oui' if has_pass else 'Non'} (exp: {pass_expiry})",
        ephemeral=True)

@bot.tree.command(name="daily", description="Recevoir 10€ par jour")
async def daily(interaction: discord.Interaction):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return
    user_data = get_user_data(interaction.user.id)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user_data.get("last_daily") == today:
        await interaction.response.send_message("🕐 Tu as déjà récupéré ta récompense aujourd’hui !", ephemeral=True)
        return
    user_data["money"] += 10
    user_data["last_daily"] = today
    await save_data()
    await interaction.response.send_message("🎉 Tu as reçu 10€ !", ephemeral=True)

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

@bot.tree.command(name="buypass", description="Acheter un pass mensuel à 10 000€ pour discuter sans crédits")
async def buypass(interaction: discord.Interaction):
    if not is_guild_context(interaction):
        await interaction.response.send_message("❌ Cette commande n’est pas disponible en message privé.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    user_data = get_user_data(interaction.user.id)
    prix_pass = 10000

    if user_data["money"] < prix_pass:
        await interaction.followup.send(f"❌ Pas assez d’argent. Il faut {prix_pass}€ pour acheter le pass.")
        return

    # Active le pass pour 30 jours à partir de maintenant
    user_data["money"] -= prix_pass
    user_data["has_pass"] = True
    user_data["pass_expiry"] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await save_data()

    await interaction.followup.send(f"✅ Pass mensuel activé ! Tu peux maintenant discuter sans utiliser de crédits pendant 30 jours.")

    # Log achat pass
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
/stats - Voir tes crédits, argent, et pass mensuel
/daily - Gagner 10€ par jour
/buycredits - Acheter crédits IA pour 50€ chacun
/buypass - Acheter un pass mensuel à 10 000€ pour discuter sans crédits
/clearhistory - Supprimer ton historique IA
/addmoney - [ADMIN] Donner de l’argent à un membre
/removemoney - [ADMIN] Retirer de l’argent à un membre
/help - Voir cette aide
"""
    await interaction.response.send_message(message, ephemeral=True)
    
bot.run(TOKEN)
