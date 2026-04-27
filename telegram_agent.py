# telegram_agent.py (place in project root)
import os
import sys
import io
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Import the new text-based entry point from our orchestrator
from src.agent_orchestrator import process_job_from_text

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # optional security

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_agent_and_get_output(job_text: str) -> str:
    """Capture all print output from the agent orchestrator."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        process_job_from_text(job_text)
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Super Agent Ready!\nSend me any job description, and I'll design the n8n workflow."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if AUTHORIZED_CHAT_ID and chat_id != AUTHORIZED_CHAT_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    job_description = update.message.text
    await update.message.reply_text("⚙️ Processing your job description... Please wait.")

    try:
        output = run_agent_and_get_output(job_description)
        # Telegram message limit 4096 chars, split if longer
        if len(output) > 4000:
            for i in range(0, len(output), 4000):
                await update.message.reply_text(output[i:i+4000])
        else:
            await update.message.reply_text(output)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Telegram bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"🩺 Health server running on port {port}")
    server.serve_forever()

# Start health server in background thread
threading.Thread(target=run_health_server, daemon=True).start()