"""
Google Drive Brain Loader
Loads brain files for each bot from a shared Google Drive folder.

Folder structure in GDrive:
  KDM Executive Bots Brain/
  ├── cfo-brain/      ← CFO bot reads this
  ├── cmo-brain/      ← CMO bot reads this
  └── coo-brain/      ← COO bot reads this

Supported file types: .txt, .md, .pdf
"""

import logging
import io
import os

logger = logging.getLogger(__name__)

# Supported MIME types to download
SUPPORTED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    # Google Docs exported as plain text
    "application/vnd.google-apps.document",
}

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
    creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "/run/secrets/gdrive_creds.json")
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
    if not files:
        return None
    return files[0]["id"]


def _extract_text_from_bytes(file_bytes: bytes, mime_type: str, filename: str) -> str:
    """Extract plain text from file bytes based on MIME type."""
    if "pdf" in mime_type:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text.strip()
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
        # Export Google Doc as plain text
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    else:
        request = service.files().get_media(fileId=file_id)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def load_brain(bot_folder_name: str, root_folder_name: str = "KDM Executive Bots Brain") -> tuple[str, bool]:
    """
    Load all brain files for a bot from its GDrive subfolder.

    Args:
        bot_folder_name: e.g. "cfo-brain", "cmo-brain", "coo-brain"
        root_folder_name: The top-level folder in GDrive

    Returns:
        (brain_text, success) — brain_text is empty string if loading failed
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

        # Find bot subfolder
        bot_folder_id = _find_folder_id(service, bot_folder_name, parent_id=root_id)
        if not bot_folder_id:
            logger.warning(f"⚠️  GDrive subfolder '{bot_folder_name}' not found.")
            return "", False

        # List all files in the bot folder
        query = f"'{bot_folder_id}' in parents and trashed=false"
        result = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size)"
        ).execute()
        files = result.get("files", [])

        if not files:
            logger.info(f"📂 No brain files found in '{bot_folder_name}'.")
            return "", True  # Folder exists but empty — not an error

        brain_parts = []
        loaded_count = 0

        for f in files:
            mime = f.get("mimeType", "")
            name = f.get("name", "unknown")

            # Skip unsupported types and large files (>2MB)
            size = int(f.get("size", 0))
            if size > 2 * 1024 * 1024:
                logger.warning(f"⚠️  Skipping {name} — too large ({size} bytes)")
                continue

            # Check supported types
            is_supported = any(t in mime for t in ["text/", "pdf", "google-apps.document"])
            if not is_supported:
                logger.info(f"⏭️  Skipping {name} — unsupported type ({mime})")
                continue

            try:
                file_bytes = _download_file(service, f["id"], mime)
                text = _extract_text_from_bytes(file_bytes, mime, name)
                if text:
                    brain_parts.append(f"=== {name} ===\n{text}")
                    loaded_count += 1
                    logger.info(f"✅ Loaded brain file: {name}")
            except Exception as e:
                logger.error(f"❌ Failed to load {name}: {e}")
                continue

        if not brain_parts:
            return "", True

        brain_text = f"\n\n--- BRAIN KNOWLEDGE BASE ({bot_folder_name}) ---\n\n"
        brain_text += "\n\n".join(brain_parts)
        brain_text += "\n\n--- END OF BRAIN KNOWLEDGE BASE ---"

        logger.info(f"🧠 Brain loaded for {bot_folder_name}: {loaded_count} file(s)")
        return brain_text, True

    except FileNotFoundError as e:
        logger.warning(f"⚠️  GDrive credentials not found: {e}")
        return "", False
    except Exception as e:
        logger.error(f"❌ GDrive brain loading failed for {bot_folder_name}: {e}")
        return "", False
