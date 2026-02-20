from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = TU_API_ID
api_hash = "TU_API_HASH"

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("SESSION STRING:")
    print(client.session.save())
