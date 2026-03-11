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
from brain.gdrive_loader import load_brain

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
    def __init__(self, token: str, bot_name: str, system_prompt: str, brain_folder: str):
        self.token = token
        self.bot_name = bot_name
        self.system_prompt = system_prompt
        self.brain_folder = brain_folder  # e.g. "cfo-brain"
        self.anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.conversation_history: dict[int, list] = {}  # chat_id -> message list
        self.uploaded_files: dict[int, list] = {}        # chat_id -> file context list
        self.allowed_users: set[int] = _load_allowed_users()

        # Load brain from GDrive at startup
        self.brain_text, self.brain_loaded = self._load_brain()

    def _load_brain(self) -> tuple[str, bool]:
        """Load brain files from GDrive at startup."""
        logger.info(f"🧠 Loading brain for {self.bot_name} from GDrive folder '{self.brain_folder}'...")
        brain_text, success = load_brain(self.brain_folder)
        if success and brain_text:
            logger.info(f"✅ Brain loaded for {self.bot_name}")
        elif success and not brain_text:
            logger.info(f"📂 Brain folder empty for {self.bot_name} — running without brain context")
        else:
            logger.warning(f"⚠️  Brain unavailable for {self.bot_name} — GDrive unreachable")
        return brain_text, success

    def _is_authorized(self, update: Update) -> bool:
        """Return True if the sender is in the allowed users list."""
        if not self.allowed_users:
            return True
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

        brain_status = "🧠 Brain loaded" if (self.brain_loaded and self.brain_text) else \
                       "📂 Brain folder empty" if self.brain_loaded else \
                       "⚠️ Brain unavailable (GDrive unreachable)"

        await update.message.reply_text(
            f"👋 Hello {user.first_name}! I'm your *{self.bot_name}* for KDM Ventures LLC.\n\n"
            f"{self._get_welcome_message()}\n\n"
            f"Status: {brain_status}\n\n"
            "Commands:\n"
            "• /start — Show this message\n"
            "• /clear — Clear conversation history\n"
            "• /files — List uploaded files\n"
            "• /brain — Show brain status\n"
            "• /reloadbrain — Reload brain from GDrive\n"
            "• /help — Get help\n\n"
            "You can also upload PDF or TXT files and I'll use them as context.",
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
            await update.message.reply_text("📂 No files uploaded in this session.")
        else:
            names = "\n".join(f"• {f['name']}" for f in file_list)
            await update.message.reply_text(f"📂 Uploaded files:\n{names}")

    async def brain_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current brain status."""
        if not self._is_authorized(update):
            await self._deny(update)
            return
        if self.brain_loaded and self.brain_text:
            size = len(self.brain_text)
            await update.message.reply_text(
                f"🧠 *Brain Status:* Loaded\n"
                f"📁 Folder: `{self.brain_folder}`\n"
                f"📊 Size: {size:,} characters",
                parse_mode="Markdown"
            )
        elif self.brain_loaded:
            await update.message.reply_text(
                f"📂 *Brain Status:* Folder empty\n"
                f"📁 Folder: `{self.brain_folder}`\n"
                "Upload files to your GDrive brain folder and run /reloadbrain",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"⚠️ *Brain Status:* Unavailable\n"
                "GDrive is unreachable. Check your service account credentials.",
                parse_mode="Markdown"
            )

    async def reload_brain(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reload brain files from GDrive on demand."""
        if not self._is_authorized(update):
            await self._deny(update)
            return
        await update.message.reply_text("🔄 Reloading brain from GDrive...")
        self.brain_text, self.brain_loaded = self._load_brain()
        if self.brain_loaded and self.brain_text:
            await update.message.reply_text(f"✅ Brain reloaded! ({len(self.brain_text):,} characters)")
        elif self.brain_loaded:
            await update.message.reply_text("📂 Brain folder is empty. Add files to GDrive and try again.")
        else:
            await update.message.reply_text("⚠️ Could not reach GDrive. Brain unavailable.")

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

        # Build full system prompt = base prompt + brain + session files
        full_system = self.system_prompt

        # Append brain knowledge base
        if self.brain_text:
            full_system += self.brain_text

        # Append session-uploaded files
        if chat_id in self.uploaded_files and self.uploaded_files[chat_id]:
            full_system += "\n\n--- SESSION UPLOADED FILES ---\n"
            for f in self.uploaded_files[chat_id]:
                full_system += f"\nFile: {f['name']}\nContent:\n{f['content'][:3000]}\n---"

        self.conversation_history[chat_id].append({"role": "user", "content": user_text})

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            response = self.anthropic_client.messages.create(
                model="claude-opus-4-5",
                max_tokens=2048,
                system=full_system,
                messages=self.conversation_history[chat_id],
            )

            assistant_reply = response.content[0].text
            self.conversation_history[chat_id].append(
                {"role": "assistant", "content": assistant_reply}
            )

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

        if doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            await update.message.reply_text(
                f"⚠️ File too large. Max size is {MAX_FILE_SIZE_MB}MB."
            )
            return

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

            self.uploaded_files[chat_id] = [
                f for f in self.uploaded_files[chat_id] if f["name"] != doc.file_name
            ]
            self.uploaded_files[chat_id].append({"name": doc.file_name, "content": content})

            await update.message.reply_text(
                f"✅ *{doc.file_name}* uploaded and ready!",
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

    def build_app(self) -> Application:
        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("clear", self.clear))
        app.add_handler(CommandHandler("files", self.files))
        app.add_handler(CommandHandler("brain", self.brain_status))
        app.add_handler(CommandHandler("reloadbrain", self.reload_brain))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

        logger.info(f"{self.bot_name} is ready...")
        return app
