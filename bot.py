import os
import asyncio
import logging
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonPornography,
    InputReportReasonViolence,
    InputReportReasonChildAbuse,
    InputReportReasonOther
)
from telethon.tl.custom import Button

# ==============================
# CONFIG
# ==============================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
session_string = os.getenv("SESSION_STRING")

logging.basicConfig(level=logging.INFO)

# ==============================
# CLIENTES
# ==============================
bot = TelegramClient("bot_session", api_id, api_hash)

# 🔥 Aquí usamos StringSession
user_client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)

# ==============================
# CONTROL DE ESTADOS
# ==============================
user_states = {}
daily_reports = {}

MAX_DAILY_REPORTS = 10
RESET_TIME = 86400

# ==============================
# FUNCIONES CONTROL DIARIO
# ==============================
def can_report(user_id):
    now = time.time()
    if user_id not in daily_reports:
        daily_reports[user_id] = {"count": 0, "reset": now + RESET_TIME}

    if now > daily_reports[user_id]["reset"]:
        daily_reports[user_id] = {"count": 0, "reset": now + RESET_TIME}

    if daily_reports[user_id]["count"] >= MAX_DAILY_REPORTS:
        return False
    return True

def add_report(user_id):
    daily_reports[user_id]["count"] += 1

# ==============================
# START
# ==============================
@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    await event.reply(
        "🚨 Sistema de Denuncias\n\n"
        "Comandos disponibles:\n"
        "/report @usuario\n"
        "/reportgroup @grupo\n\n"
        "Puedes elegir entre 1 y 5 denuncias por reporte.\n"
        "Máximo 10 reportes por día."
    )

# ==============================
# REPORTAR USUARIO
# ==============================
@bot.on(events.NewMessage(pattern=r"^/report (.+)"))
async def report_user_start(event):
    sender_id = event.sender_id

    if not can_report(sender_id):
        await event.reply("⛔ Has alcanzado el máximo de 10 reportes hoy.")
        return

    target_input = event.pattern_match.group(1)

    try:
        entity = await user_client.get_entity(target_input)

        user_states[sender_id] = {
            "target": entity,
            "type": "user",
            "step": "confirm"
        }

        await event.reply(
            f"🔎 Usuario encontrado:\n\n"
            f"ID: {entity.id}\n"
            f"Username: @{entity.username if entity.username else 'No tiene'}\n\n"
            "¿Deseas denunciar?",
            buttons=[
                [Button.inline("✅ SI", data="confirm_yes"),
                 Button.inline("❌ NO", data="confirm_no")]
            ]
        )

    except Exception:
        await event.reply("❌ No se pudo encontrar ese usuario.")

# ==============================
# CALLBACK CONFIRMACION
# ==============================
@bot.on(events.CallbackQuery(data=b"confirm_yes"))
async def callback_confirm_yes(event):
    sender_id = event.sender_id

    if sender_id not in user_states:
        await event.answer("⚠ Sesión expirada.", alert=True)
        return

    user_states[sender_id]["step"] = "reason"

    await event.edit(
        "Selecciona motivo:",
        buttons=[
            [Button.inline("1️⃣ Spam", data="reason_1")],
            [Button.inline("2️⃣ Pornografía", data="reason_2")],
            [Button.inline("3️⃣ Violencia", data="reason_3")],
            [Button.inline("4️⃣ Abuso infantil", data="reason_4")],
            [Button.inline("5️⃣ Otro", data="reason_5")]
        ]
    )

@bot.on(events.CallbackQuery(data=b"confirm_no"))
async def callback_confirm_no(event):
    sender_id = event.sender_id
    user_states.pop(sender_id, None)
    await event.edit("❌ Denuncia cancelada.")

# ==============================
# CALLBACK MOTIVO
# ==============================
@bot.on(events.CallbackQuery(pattern=b"reason_"))
async def callback_reason(event):

    sender_id = event.sender_id

    if sender_id not in user_states:
        await event.answer("⚠ Sesión expirada.", alert=True)
        return

    state = user_states[sender_id]
    reason_key = event.data.decode().split("_")[1]

    reason_map = {
        "1": InputReportReasonSpam(),
        "2": InputReportReasonPornography(),
        "3": InputReportReasonViolence(),
        "4": InputReportReasonChildAbuse(),
        "5": InputReportReasonOther()
    }

    try:
        await user_client(ReportPeerRequest(
            peer=state["target"],
            reason=reason_map[reason_key],
            message="Reporte generado automáticamente"
        ))

        add_report(sender_id)

        await event.edit(
            f"🚨 Denuncia enviada correctamente.\n\n"
            f"📊 Reportes usados hoy: {daily_reports[sender_id]['count']}/{MAX_DAILY_REPORTS}"
        )

    except Exception as e:
        logging.warning(f"Error al reportar: {e}")
        await event.edit("⚠ Telegram puede haber limitado la acción.")

    user_states.pop(sender_id)

# ==============================
# MAIN
# ==============================
async def main():

    # 🔥 Ya no pide código porque usa StringSession
    await user_client.start()

    await bot.start(bot_token=bot_token)

    me = await bot.get_me()
    print("🤖 Bot activo como:", me.username)
    print("✅ Sistema listo.")

    await bot.run_until_disconnected()

asyncio.run(main())
