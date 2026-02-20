import os
import asyncio
import logging
import time
from dotenv import load_dotenv
from telethon import TelegramClient, events
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
load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
phone = os.getenv("PHONE_NUMBER")

logging.basicConfig(level=logging.INFO)

# ==============================
# CLIENTES
# ==============================
bot = TelegramClient("bot_session", api_id, api_hash)
user_client = TelegramClient("user_session", api_id, api_hash)

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
# REPORTAR GRUPO
# ==============================
@bot.on(events.NewMessage(pattern=r"^/reportgroup (.+)"))
async def report_group_start(event):
    sender_id = event.sender_id

    if not can_report(sender_id):
        await event.reply("⛔ Has alcanzado el máximo de 10 reportes hoy.")
        return

    target_input = event.pattern_match.group(1)

    try:
        entity = await user_client.get_entity(target_input)
        user_states[sender_id] = {
            "target": entity,
            "type": "group",
            "step": "confirm"
        }
        await event.reply(
            f"🔎 Grupo/Canal encontrado:\n\n"
            f"ID: {entity.id}\n"
            f"Nombre: {getattr(entity, 'title', 'Sin nombre')}\n\n"
            "¿Deseas denunciar?",
            buttons=[
                [Button.inline("✅ SI", data="confirm_yes"),
                 Button.inline("❌ NO", data="confirm_no")]
            ]
        )
    except Exception:
        await event.reply("❌ No se pudo encontrar ese grupo.")

# ==============================
# CALLBACK - CONFIRMACION SI/NO
# ==============================
@bot.on(events.CallbackQuery(data=b"confirm_yes"))
async def callback_confirm_yes(event):
    sender_id = event.sender_id

    if sender_id not in user_states:
        await event.answer("⚠ Sesión expirada.", alert=True)
        return

    user_states[sender_id]["step"] = "times"
    await event.edit(
        "¿Cuántas denuncias quieres enviar?",
        buttons=[
            [
                Button.inline("1", data="times_1"),
                Button.inline("2", data="times_2"),
                Button.inline("3", data="times_3"),
                Button.inline("4", data="times_4"),
                Button.inline("5", data="times_5"),
            ]
        ]
    )

@bot.on(events.CallbackQuery(data=b"confirm_no"))
async def callback_confirm_no(event):
    sender_id = event.sender_id
    user_states.pop(sender_id, None)
    await event.edit("❌ Denuncia cancelada.")

# ==============================
# CALLBACK - CANTIDAD
# ==============================
@bot.on(events.CallbackQuery(pattern=b"times_"))
async def callback_times(event):
    sender_id = event.sender_id

    if sender_id not in user_states:
        await event.answer("⚠ Sesión expirada.", alert=True)
        return

    cantidad = int(event.data.decode().split("_")[1])
    user_states[sender_id]["times"] = cantidad
    user_states[sender_id]["step"] = "reason"

    await event.edit(
        f"Selecciona el motivo de la denuncia:",
        buttons=[
            [Button.inline("1️⃣ Spam", data="reason_1")],
            [Button.inline("2️⃣ Pornografía", data="reason_2")],
            [Button.inline("3️⃣ Violencia", data="reason_3")],
            [Button.inline("4️⃣ Abuso infantil", data="reason_4")],
            [Button.inline("5️⃣ Otro", data="reason_5")],
        ]
    )

# ==============================
# CALLBACK - MOTIVO Y ENVIO
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

    reason_names = {
        "1": "Spam",
        "2": "Pornografía",
        "3": "Violencia",
        "4": "Abuso infantil",
        "5": "Otro"
    }

    total = state["times"]
    await event.edit(f"⏳ Enviando {total} denuncia(s) por {reason_names[reason_key]}, espera...")

    success = 0
    failed = 0

    for i in range(total):
        try:
            await user_client(ReportPeerRequest(
                peer=state["target"],
                reason=reason_map[reason_key],
                message="Reporte generado automáticamente"
            ))
            success += 1
            logging.info(f"Denuncia {i+1}/{total} enviada correctamente.")
            await asyncio.sleep(1.5)
        except Exception as e:
            failed += 1
            logging.warning(f"Denuncia {i+1}/{total} fallida: {e}")
            await asyncio.sleep(1.5)

    add_report(sender_id)
    user_states.pop(sender_id)

    await event.edit(
        f"🚨 Denuncias completadas.\n\n"
        f"📋 Motivo: {reason_names[reason_key]}\n"
        f"✅ Exitosas: {success}/{total}\n"
        f"❌ Fallidas: {failed}/{total}\n\n"
        f"📊 Reportes usados hoy: {daily_reports[sender_id]['count']}/{MAX_DAILY_REPORTS}"
    )

# ==============================
# MAIN
# ==============================
async def main():
    await user_client.connect()

    if not await user_client.is_user_authorized():
        await user_client.start(phone=phone)

    await bot.start(bot_token=bot_token)

    me = await bot.get_me()
    print("🤖 Bot activo como:", me.username)
    print("✅ Sistema listo.")

    await bot.run_until_disconnected()

asyncio.run(main())