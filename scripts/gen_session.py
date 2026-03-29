"""
gen_session.py — One-time helper to generate a Pyrogram user session string.

Run this ONCE from the project root:
    python scripts/gen_session.py

It will prompt for your phone number and the OTP Telegram sends you.
After successful login it prints the SESSION STRING — copy it into your .env:

    TG_USER_SESSION=<paste here>

This script does NOT need to be run again unless you revoke the session.
"""

import asyncio
import os
import sys

# Make sure project root is on the path when running as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

from pyrogram import Client


async def main():
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("❌  TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in your .env file.")
        sys.exit(1)

    print("=" * 60)
    print("  ARCIS — Telegram User Session Generator")
    print("=" * 60)
    print("You will be asked to enter your phone number and the OTP")
    print("Telegram sends you. This is a ONE-TIME setup.\n")

    async with Client(
        name="arcis_session_gen",
        api_id=int(api_id),
        api_hash=api_hash,
        in_memory=True,          # Don't save a .session file — we want the string
    ) as app:
        session_string = await app.export_session_string()

    print("\n" + "=" * 60)
    print("✅  Session generated successfully!\n")
    print("Add this to your .env file:\n")
    print(f"TG_USER_SESSION={session_string}")
    print("\n" + "=" * 60)
    print("⚠️  Keep this string secret — it gives full access to your Telegram account.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
