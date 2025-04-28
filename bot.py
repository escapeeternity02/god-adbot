import os
import json
import asyncio
import random
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetHistoryRequest
from colorama import Fore, Style, init
import pyfiglet
from aiohttp import web

# === CONFIGURATION ===
CREDENTIALS_FOLDER = "sessions"
SESSION_NAME = "session1"
DELAY_AFTER_ALL_GROUPS = 872  # seconds
MAX_PARALLEL_SENDS = 5
BATCH_SIZE = 100
COOLDOWN_MIN = 180
COOLDOWN_MAX = 300
# Self-tuning settings
DELAY_BETWEEN_MESSAGES_MIN = 7
DELAY_BETWEEN_MESSAGES_MAX = 17
ADAPTIVE_DELAY_INCREMENT = 5
ADAPTIVE_DELAY_DECREMENT = 2
STABLE_SENDS_TO_DECREASE = 10

# === INIT ===
init(autoreset=True)
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

# === HELPERS ===
def display_banner():
    banner = pyfiglet.figlet_format("ESCAPExETERNITY")
    print(Fore.RED + banner)
    print(Fore.GREEN + Style.BRIGHT + "Made by @EscapeEternity\n")

def log(message, color=Fore.WHITE):
    print(color + f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

async def start_web_server():
    async def handle(request):
        return web.Response(text="Service is running!")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    log("Web server started to keep Render service alive.", Fore.YELLOW)

# === SELF-TUNING SYSTEM ===
stable_sends = 0
SEMAPHORE = asyncio.Semaphore(MAX_PARALLEL_SENDS)

async def forward_message_safe(client, group, msg):
    global DELAY_BETWEEN_MESSAGES_MIN, DELAY_BETWEEN_MESSAGES_MAX, stable_sends

    async with SEMAPHORE:
        try:
            delay = random.uniform(DELAY_BETWEEN_MESSAGES_MIN, DELAY_BETWEEN_MESSAGES_MAX)
            await asyncio.sleep(delay)
            await client.forward_messages(group.id, msg.id, "me")
            log(f"✅ Message sent to group: {group.name or group.id}", Fore.GREEN)

            stable_sends += 1
            if stable_sends >= STABLE_SENDS_TO_DECREASE:
                if DELAY_BETWEEN_MESSAGES_MIN > 5:
                    DELAY_BETWEEN_MESSAGES_MIN -= ADAPTIVE_DELAY_DECREMENT
                if DELAY_BETWEEN_MESSAGES_MAX > 10:
                    DELAY_BETWEEN_MESSAGES_MAX -= ADAPTIVE_DELAY_DECREMENT
                stable_sends = 0
                log(f"🔵 Decreased delay to {DELAY_BETWEEN_MESSAGES_MIN}-{DELAY_BETWEEN_MESSAGES_MAX} seconds", Fore.BLUE)

        except FloodWaitError as e:
            log(f"⚠️ FLOODWAIT detected! Sleeping for {e.seconds} seconds...", Fore.YELLOW)
            await asyncio.sleep(e.seconds)

            DELAY_BETWEEN_MESSAGES_MIN += ADAPTIVE_DELAY_INCREMENT
            DELAY_BETWEEN_MESSAGES_MAX += ADAPTIVE_DELAY_INCREMENT
            stable_sends = 0

            log(f"🔴 Increased delay to {DELAY_BETWEEN_MESSAGES_MIN}-{DELAY_BETWEEN_MESSAGES_MAX} seconds after FloodWait", Fore.RED)

        except Exception as e:
            log(f"❌ Error forwarding to {group.name or group.id}: {e}", Fore.RED)

async def auto_pro_sender(client, delay_after_all_groups):
    session_id = client.session.filename.split('/')[-1]
    num_messages = 1

    while True:
        try:
            history = await client(GetHistoryRequest(
                peer="me",
                limit=num_messages,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0))

            if not history.messages:
                log(f"No messages found in Saved Messages for session {session_id}.", Fore.RED)
                await asyncio.sleep(60)
                continue

            saved_messages = history.messages
            log(f"{len(saved_messages)} saved messages retrieved for session {session_id}.", Fore.CYAN)

            groups = sorted([d for d in await client.get_dialogs() if d.is_group],
                            key=lambda g: g.name.lower() if g.name else "")

            repeat = 1
            while True:
                log(f"Starting repetition {repeat} (Unlimited mode)", Fore.CYAN)

                for i in range(0, len(groups), BATCH_SIZE):
                    batch = groups[i:i+BATCH_SIZE]
                    tasks = []
                    for group in batch:
                        for msg in saved_messages:
                            tasks.append(forward_message_safe(client, group, msg))

                    await asyncio.gather(*tasks)

                    if i + BATCH_SIZE < len(groups):
                        cooldown = random.randint(COOLDOWN_MIN, COOLDOWN_MAX)
                        log(f"Cooldown for {cooldown} seconds after sending {len(batch)} groups...", Fore.YELLOW)
                        await asyncio.sleep(cooldown)

                log(f"Completed repetition {repeat}. Waiting {delay_after_all_groups} seconds...", Fore.CYAN)
                await asyncio.sleep(delay_after_all_groups)
                repeat += 1

        except Exception as e:
            log(f"Error in auto_pro_sender: {e}", Fore.RED)
            log("Retrying in 30 seconds...", Fore.YELLOW)
            await asyncio.sleep(30)

async def main():
    display_banner()

    session_json_path = os.path.join(CREDENTIALS_FOLDER, f"{SESSION_NAME}.json")
    session_file_path = os.path.join(CREDENTIALS_FOLDER, f"{SESSION_NAME}.session")

    if not os.path.exists(session_json_path):
        log(f"Credentials file {session_json_path} not found. Please upload it.", Fore.RED)
        return
    if not os.path.exists(session_file_path):
        log(f"Session file {session_file_path} not found. Please upload it.", Fore.RED)
        return

    with open(session_json_path, "r") as f:
        credentials = json.load(f)

    await start_web_server()

    retries = 0
    while True:
        try:
            client = TelegramClient(session_file_path,
                                    credentials["api_id"], credentials["api_hash"])
            await client.connect()

            if not await client.is_user_authorized():
                log("Session not authorized. Please upload a working session file (.session).", Fore.RED)
                return

            log(f"Starting Auto Pro Sender mode with unlimited repetitions and {DELAY_AFTER_ALL_GROUPS}s delay.", Fore.GREEN)

            await auto_pro_sender(client, delay_after_all_groups=DELAY_AFTER_ALL_GROUPS)

        except Exception as e:
            log(f"Error in main loop: {e}", Fore.RED)
            log("Reconnecting in 30 seconds...", Fore.YELLOW)
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
