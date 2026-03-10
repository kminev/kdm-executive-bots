"""
Base bot class - shared logic for all KDM Executive Bots
"""

import logging
import os
import anthropic
from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config.settings import MAX_FILE_SIZE_MB, ALLOWED_FILE_TYPES

logger = logging.getLogger(__name__)


def _load_allowed_users() -> set[int]:
    """
    Load allowed Telegram user IDs from ALLOWED_TELEGRAM_IDS env var.
    Expects a comma-separated list of integer IDs, e.g.: 123456789,987654321
    """
    raw = os.environ.get("ALLOWED_TELEGRAM_IDS", "")
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    if not ids:
        logger.warning("⚠️  ALLOWED_TELEGRAM_IDS is not set — bot is open to everyone!")
    return ids


class BaseBot:
    def __init__(self, token: str, bot_name: str, system_prompt: str):
        self.token = token
        self.bot_name = bot_name
        self.system_prompt = system_prompt
        self.anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.conversation_history: dict[int, list] = {}  # chat_id -> message list
        self.uploaded_files: dict[int, list] = {}  # chat_id -> file context list
        self.allowed_users: set[int] = _load_allowed_users()

    def _is_authorized(self, update: Update) -> bool:
        """Return True if the sender is in the allowed users list."""
        if not self.allowed_users:
            return True  # No restriction set — allow all (not recommended)
        return update.effective_user.id in self.allowed_users

    async def _deny(self, update: Update):
        """Send an unauthorized message and log the attempt."""
        user = update.effective_user
        logger.warning(
            f"🚫 Unauthorized access attempt by {user.full_name} "
            f"(id={user.id}, username=@{user.username})"
        )
        await update.message.reply_text(
            "🚫 Sorry, you are not authorized to use this bot."
        )

    # ──────────────────────────────────────────────
    # Command Handlers
    # ──────────────────────────────────────────────

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await self._deny(update)
            return
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Hello {user.first_name}! I'm your *{self.bot_name}* for KDM Ventures LLC.\n\n"
            f"{self._get_welcome_message()}\n\n"
            "Commands:\n"
            "• /start — Show this message\n"
            "• /clear — Clear conversation history\n"
            "• /files — List uploaded files\n"
            "• /help — Get help\n\n"
            "You can also upload PDF, TXT, or image files and I'll use them as context.",
            parse_mode="Markdown",
        )

    async def clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await self._deny(update)
            return
        chat_id = update.effective_chat.id
        self.conversation_history.pop(chat_id, None)
        self.uploaded_files.pop(chat_id, None)
        await update.message.reply_text("✅ Conversation and file context cleared.")

    async def files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await self._deny(update)
            return
        chat_id = update.effective_chat.id
        file_list = self.uploaded_files.get(chat_id, [])
        if not file_list:
            await update.message.reply_text("📂 No files uploaded yet.")
        else:
            names = "\n".join(f"• {f['name']}" for f in file_list)
            await update.message.reply_text(f"📂 Uploaded files:\n{names}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await self._deny(update)
            return
        await update.message.reply_text(self._get_help_message(), parse_mode="Markdown")

    # ──────────────────────────────────────────────
    # Message & File Handlers
    # ──────────────────────────────────────────────

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await self._deny(update)
            return
        chat_id = update.effective_chat.id
        user_text = update.message.text

        if chat_id not in self.conversation_history:
            self.conversation_history[chat_id] = []

        # Build context from uploaded files
        file_context = ""
        if chat_id in self.uploaded_files and self.uploaded_files[chat_id]:
            file_context = "\n\n--- UPLOADED FILE CONTEXT ---\n"
            for f in self.uploaded_files[chat_id]:
                file_context += f"\nFile: {f['name']}\nContent:\n{f['content'][:3000]}\n---"

        self.conversation_history[chat_id].append({"role": "user", "content": user_text})

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            response = self.anthropic_client.messages.create(
                model="claude-opus-4-5",
                max_tokens=2048,
                system=self.system_prompt + file_context,
                messages=self.conversation_history[chat_id],
            )

            assistant_reply = response.content[0].text
            self.conversation_history[chat_id].append(
                {"role": "assistant", "content": assistant_reply}
            )

            # Telegram message limit is 4096 chars; split if needed
            for chunk in self._split_message(assistant_reply):
                await update.message.reply_text(chunk, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            await update.message.reply_text(
                "⚠️ Sorry, I encountered an error. Please try again."
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await self._deny(update)
            return
        chat_id = update.effective_chat.id
        doc: Document = update.message.document

        # Size check
        if doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            await update.message.reply_text(
                f"⚠️ File too large. Max size is {MAX_FILE_SIZE_MB}MB."
            )
            return

        # Type check
        mime = doc.mime_type or ""
        if not any(t in mime for t in ALLOWED_FILE_TYPES):
            await update.message.reply_text(
                "⚠️ Unsupported file type. Please upload PDF or TXT files."
            )
            return

        await update.message.reply_text(f"📎 Processing *{doc.file_name}*...", parse_mode="Markdown")

        try:
            file = await context.bot.get_file(doc.file_id)
            file_bytes = await file.download_as_bytearray()

            content = self._extract_text(file_bytes, mime, doc.file_name)

            if chat_id not in self.uploaded_files:
                self.uploaded_files[chat_id] = []

            # Replace if same filename exists
            self.uploaded_files[chat_id] = [
                f for f in self.uploaded_files[chat_id] if f["name"] != doc.file_name
            ]
            self.uploaded_files[chat_id].append({"name": doc.file_name, "content": content})

            await update.message.reply_text(
                f"✅ *{doc.file_name}* uploaded and ready! I'll use this as context in our conversation.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await update.message.reply_text("⚠️ Failed to process the file. Please try again.")

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _extract_text(self, file_bytes: bytearray, mime: str, filename: str) -> str:
        if "pdf" in mime:
            try:
                import pypdf
                import io
                reader = pypdf.PdfReader(io.BytesIO(bytes(file_bytes)))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                logger.error(f"PDF extraction error: {e}")
                return f"[Could not extract text from {filename}]"
        else:
            try:
                return file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                return f"[Could not decode {filename}]"

    def _split_message(self, text: str, limit: int = 4096) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks = []
        while text:
            chunks.append(text[:limit])
            text = text[limit:]
        return chunks

    def _get_welcome_message(self) -> str:
        return "How can I help you today?"

    def _get_help_message(self) -> str:
        return f"I'm your *{self.bot_name}*. Ask me anything related to my area of expertise!"

    def build_app(self):
        """Build and return the Application with all handlers registered."""
        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("clear", self.clear))
        app.add_handler(CommandHandler("files", self.files))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

        logger.info(f"{self.bot_name} is ready...")
        return app
