"""
Google Drive Brain Loader
Loads brain files for each bot from a shared Google Drive folder.

Folder structure in GDrive:
  KDM Executive Bots Brain/
  ├── shared-brain/      ← ALL bots read this
  ├── cfo-brain/         ← CFO bot reads this
  ├── cmo-brain/         ← CMO bot reads this
  └── coo-brain/         ← COO bot reads this

Supported file types: .txt, .md, .pdf, Google Docs
"""

import logging
import io
import os

logger = logging.getLogger(__name__)

GDRIVE_AVAILABLE = False

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import pypdf
    GDRIVE_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  Google Drive libraries not installed. Brain loading disabled.")


def _get_drive_service():
    """Build and return an authenticated Google Drive service client."""
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "/root/kdm-executive-bots/gdrive-creds.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Service account JSON not found at: {creds_path}")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_folder_id(service, folder_name: str, parent_id: str = None) -> str | None:
    """Find a folder by name, optionally within a parent folder."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    result = service.files().list(q=query, fields="files(id, name)").execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _extract_text_from_bytes(file_bytes: bytes, mime_type: str, filename: str) -> str:
    """Extract plain text from file bytes based on MIME type."""
    if "pdf" in mime_type:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as e:
            logger.error(f"PDF extraction error for {filename}: {e}")
            return f"[Could not extract text from {filename}]"
    else:
        try:
            return file_bytes.decode("utf-8", errors="ignore").strip()
        except Exception:
            return f"[Could not decode {filename}]"


def _download_file(service, file_id: str, mime_type: str) -> bytes:
    """Download a file from Google Drive, exporting Google Docs as plain text."""
    if mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    else:
        request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def _load_folder(service, folder_id: str, folder_name: str) -> list[str]:
    """Load all supported files from a single GDrive folder. Returns list of text blocks."""
    query = f"'{folder_id}' in parents and trashed=false"
    result = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size)"
    ).execute()
    files = result.get("files", [])

    parts = []
    for f in files:
        mime = f.get("mimeType", "")
        name = f.get("name", "unknown")
        size = int(f.get("size", 0))

        if size > 2 * 1024 * 1024:
            logger.warning(f"⚠️  Skipping {name} — too large ({size} bytes)")
            continue

        is_supported = any(t in mime for t in ["text/", "pdf", "google-apps.document"])
        if not is_supported:
            logger.info(f"⏭️  Skipping {name} — unsupported type ({mime})")
            continue

        try:
            file_bytes = _download_file(service, f["id"], mime)
            text = _extract_text_from_bytes(file_bytes, mime, name)
            if text:
                parts.append(f"=== {name} ===\n{text}")
                logger.info(f"✅ Loaded brain file: {folder_name}/{name}")
        except Exception as e:
            logger.error(f"❌ Failed to load {folder_name}/{name}: {e}")

    return parts


def load_brain(
    bot_folder_name: str,
    root_folder_name: str = "KDM Executive Bots Brain",
    shared_folder_name: str = "shared-brain"
) -> tuple[str, bool]:
    """
    Load shared brain + bot-specific brain for a given bot.

    Args:
        bot_folder_name:    e.g. "cfo-brain", "cmo-brain", "coo-brain"
        root_folder_name:   Top-level GDrive folder name
        shared_folder_name: Shared subfolder read by all bots

    Returns:
        (brain_text, success)
    """
    if not GDRIVE_AVAILABLE:
        return "", False

    try:
        service = _get_drive_service()

        # Find root folder
        root_id = _find_folder_id(service, root_folder_name)
        if not root_id:
            logger.warning(f"⚠️  GDrive root folder '{root_folder_name}' not found.")
            return "", False

        all_parts = []

        # ── Load shared brain (all bots read this) ──
        shared_id = _find_folder_id(service, shared_folder_name, parent_id=root_id)
        if shared_id:
            shared_parts = _load_folder(service, shared_id, shared_folder_name)
            if shared_parts:
                all_parts.append("--- SHARED COMPANY KNOWLEDGE ---\n\n" + "\n\n".join(shared_parts))
                logger.info(f"🧠 Shared brain: {len(shared_parts)} file(s) loaded")
            else:
                logger.info("📂 shared-brain folder is empty")
        else:
            logger.warning("⚠️  shared-brain folder not found in GDrive")

        # ── Load bot-specific brain ──
        bot_folder_id = _find_folder_id(service, bot_folder_name, parent_id=root_id)
        if bot_folder_id:
            bot_parts = _load_folder(service, bot_folder_id, bot_folder_name)
            if bot_parts:
                all_parts.append(f"--- {bot_folder_name.upper()} KNOWLEDGE ---\n\n" + "\n\n".join(bot_parts))
                logger.info(f"🧠 Bot brain ({bot_folder_name}): {len(bot_parts)} file(s) loaded")
            else:
                logger.info(f"📂 {bot_folder_name} folder is empty")
        else:
            logger.warning(f"⚠️  {bot_folder_name} folder not found in GDrive")

        if not all_parts:
            return "", True  # Folders exist but empty — not an error

        brain_text = "\n\n--- BRAIN KNOWLEDGE BASE ---\n\n"
        brain_text += "\n\n".join(all_parts)
        brain_text += "\n\n--- END OF BRAIN KNOWLEDGE BASE ---"

        return brain_text, True

    except FileNotFoundError as e:
        logger.warning(f"⚠️  GDrive credentials not found: {e}")
        return "", False
    except Exception as e:
        logger.error(f"❌ GDrive brain loading failed for {bot_folder_name}: {e}")
        return "", False
