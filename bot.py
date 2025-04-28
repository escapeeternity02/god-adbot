import os
import json
import asyncio
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import GetHistoryRequest
from colorama import Fore, Style, init
import pyfiglet
from aiohttp import web
import datetime

# Initialize colorama for colorful outputs
init(autoreset=True)

# Folder for saving session credentials
CREDENTIALS_FOLDER = "sessions"
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

# Display banner
def display_banner():
    banner = pyfiglet.figlet_format("ESCAPExETERNITY")
    print(Fore.RED + banner)
    print(Fore.GREEN + Style.BRIGHT + "Made by @EscapeEternity\n")

# Stats tracking
bot_stats = {
    "status": "Starting...",
    "session": "session1",
    "groups_done": 0,
    "messages_sent": 0,
    "floodwaits": 0,
    "current_delay": "0s",
    "last_send": "N/A"
}

# Tiny web server to keep Render alive
async def start_web_server():
    async def handle(request):
        return web.Response(text="Service is running!")
    
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/stats/json', get_stats)  # Ensure stats endpoint is available
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    print(Fore.YELLOW + "Web server started to keep Render service alive.")

# Update bot stats in real-time
def update_bot_stats(status, groups_done, messages_sent, floodwaits, current_delay, last_send):
    bot_stats["status"] = status
    bot_stats["groups_done"] = groups_done
    bot_stats["messages_sent"] = messages_sent
    bot_stats["floodwaits"] = floodwaits
    bot_stats["current_delay"] = current_delay
    bot_stats["last_send"] = last_send

# Serve the dashboard HTML
async def stats_handler(request):
    with open("dashboard.html", "r") as f:
        return web.Response(text=f.read(), content_type="text/html")

# API route to send stats in JSON format
async def get_stats(request):
    return web.json_response(bot_stats)

# Auto sender with group forwarding
async def auto_pro_sender(client, delay_after_all_groups):
    session_id = client.session.filename.split('/')[-1]
    num_messages = 1
    while True:
        try:
            # Get saved messages
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
                print(Fore.RED + f"No messages found in Saved Messages for session {session_id}.")
                await asyncio.sleep(60)
                continue

            saved_messages = history.messages
            print(Fore.CYAN + f"{len(saved_messages)} saved messages retrieved for session {session_id}.\n")

            groups = sorted([d for d in await client.get_dialogs() if d.is_group], key=lambda g: g.name.lower() if g.name else "")
            repeat = 1

            while True:
                print(Fore.CYAN + f"\nStarting repetition {repeat} (Unlimited mode)")
                for group in groups:
                    for msg in saved_messages:
                        try:
                            await client.forward_messages(group.id, msg.id, "me")
                            print(Fore.GREEN + f"Message sent to group: {group.name or group.id}")
                            update_bot_stats("Sending messages", len(groups), len(saved_messages), bot_stats["floodwaits"], f"{delay_after_all_groups}s", str(datetime.datetime.now()))
                        except errors.FloodWaitError as e:
                            print(Fore.RED + f"Flood wait error: {e}. Retrying in {e.seconds} seconds.")
                            update_bot_stats("Waiting for flood", len(groups), len(saved_messages), bot_stats["floodwaits"], f"{e.seconds}s", str(datetime.datetime.now()))
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            print(Fore.RED + f"Error forwarding to {group.name or group.id}: {e}")

                print(Fore.CYAN + f"\nCompleted repetition {repeat}. Waiting {delay_after_all_groups} seconds...")
                await asyncio.sleep(delay_after_all_groups)
                repeat += 1
        except Exception as e:
            print(Fore.RED + f"Error in auto_pro_sender: {e}")
            print(Fore.YELLOW + "Retrying in 30 seconds...")
            await asyncio.sleep(30)

# Main function with auto-reconnect
async def main():
    display_banner()

    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print(Fore.RED + f"Credentials file {path} not found. Please upload session1.json in 'sessions' folder.")
        return

    with open(path, "r") as f:
        credentials = json.load(f)

    while True:
        try:
            client = TelegramClient(os.path.join(CREDENTIALS_FOLDER, session_name), credentials["api_id"], credentials["api_hash"])
            await client.connect()

            if not await client.is_user_authorized():
                print(Fore.RED + "Session not authorized. Please upload a working session file (.session).")
                return

            print(Fore.GREEN + "Starting Auto Pro Sender mode with unlimited repetitions and 500s delay.")
            await asyncio.gather(
                start_web_server(),
                auto_pro_sender(client, delay_after_all_groups=500)
            )
        except Exception as e:
            print(Fore.RED + f"Error in main loop: {e}")
            print(Fore.YELLOW + "Reconnecting in 30 seconds...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
