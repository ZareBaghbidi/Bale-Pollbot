from threading import Thread
from app.bot.handlers.main_handlers import on_message
from app.bot.messages import *
from app.services.poll import activate_poll
from app.db.cruds import init_db
from app.db.cruds import *
from app.bot.config import AppSettings, get_settings
from app.bot.callback_query import *
import traceback
import time
from balethon import Client
import asyncio


settings: AppSettings
client: Client

# ---------- STATE ----------
try:
    all_users = set(get_users())
except:
    all_users = set()

user_states = {}
pending_actions = {}

# ---------- AUTOSTART ----------


async def autostart_loop(client):
    while True:
        try:
            t = next_task()
            if t and t.get("t") and t["t"] <= time.time():
                print("autostart: activating poll", t["poll_id"])
                await activate_poll(client, t["poll_id"])
                del_task(t["id"])
        except Exception as e:
            print("autostart error:", e)
            traceback.print_exc()
        await asyncio.sleep(10)
        # time.sleep(10)


async def handle_pre_checkout(pre_checkout_query, client):
    query_id = pre_checkout_query.id
    payload = pre_checkout_query.invoice_payload

    try:
        await client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=True
        )
        print(f"✅ درخواست پرداخت برای کاربر {payload} تایید شد.")

    except Exception as e:
        print(f"❌ خطا در ارسال پاسخ تایید: {e}")
        traceback.print_exc()
        await client.answer_pre_checkout_query(
            pre_checkout_query_id=query_id,
            ok=False,
            error_message="خطای داخلی سرور در پردازش پرداخت."
        )


def main():
    # settings
    settings = get_settings()

    # db
    print("🛠 checking database tables...")
    init_db()
    print("✅ Database tables are ready.")

    # bot
    client = Client(settings.bale_bot_token)

    @client.on_message()
    async def _(message):
        global pending_actions, user_states
        await on_message(message, settings, client, user_states, pending_actions, all_users)

    @client.on_pre_checkout_query()
    async def _(pre_checkout_query):
        await handle_pre_checkout(pre_checkout_query, client)

    @client.on_callback_query()
    async def _(callback_query):
        global pending_actions, user_states
        await on_callback_query(callback_query, settings, client, pending_actions, user_states)

    print("🚀 Bot is starting...")

    with client:
        for owner in settings.owners:
            if owner in all_users:
                client.send_message(owner, "ربات روشن شد.")

    # async def _():
    #     asyncio.create_task(autostart_loop(client))

    # Thread(target=autostart_loop, args=(
    # client,), daemon=True).start()
    loop = asyncio.get_event_loop()

    # ساخت task
    loop.create_task(autostart_loop(client))
    print("autocheck started")

    client.run()


if __name__ == "__main__":
    try:
        main()
        # asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
