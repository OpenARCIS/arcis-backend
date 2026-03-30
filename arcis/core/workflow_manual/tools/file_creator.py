import os
import uuid
import tempfile

from langchain.tools import tool

from arcis.logger import LOGGER


# Dedicated directory for generated files
FILES_DIR = os.path.join(tempfile.gettempdir(), "arcis_files")
os.makedirs(FILES_DIR, exist_ok=True)


@tool
def create_text_file(filename: str, content: str) -> str:
    """
    Create a .txt file with the given content.
    Use this when you need to save information (assignments, notes, research,
    reports, summaries) to a text file for the user to download or receive.

    Args:
        filename: Desired name for the file (e.g. 'assignment_notes').
                  A .txt extension and unique suffix will be added automatically.
        content: The full text content to write into the file.

    Returns:
        The absolute file path of the created file on success,
        or an error message on failure.
    """
    try:
        # Sanitize filename — keep only safe characters
        safe_name = "".join(
            c for c in filename if c.isalnum() or c in ("_", "-", " ")
        ).strip().replace(" ", "_")

        if not safe_name:
            safe_name = "file"

        # Add unique suffix to prevent collisions
        unique_suffix = uuid.uuid4().hex[:8]
        full_name = f"{safe_name}_{unique_suffix}.txt"
        file_path = os.path.join(FILES_DIR, full_name)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        LOGGER.info(f"FILE_CREATOR: Created file at {file_path}")
        return file_path

    except Exception as e:
        LOGGER.error(f"FILE_CREATOR: Error creating file: {e}")
        return f"Error creating file: {e}"
