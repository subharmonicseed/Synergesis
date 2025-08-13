# tools/file_tool.py
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FileTool:
    def __init__(self, base_dir: str = "sandbox"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _sanitize_path(self, path: str) -> str:
        # Resolve absolute path
        abs_path = os.path.abspath(os.path.join(self.base_dir, path))
        # Ensure it stays within base_dir
        if not abs_path.startswith(self.base_dir):
            raise ValueError("Access to restricted path denied")
        return abs_path

    def read_file(self, path: str) -> str:
        try:
            safe_path = self._sanitize_path(path)
            logger.info(f"Reading file: {safe_path}")
            with open(safe_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except Exception as e:
            logger.error(f"Read failed: {str(e)}")
            return f"Error reading file: {str(e)}"

    def write_file(self, path: str, content: str) -> str:
        try:
            safe_path = self._sanitize_path(path)
            logger.info(f"Writing file: {safe_path}")
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            logger.error(f"Write failed: {str(e)}")
            return f"Error writing file: {str(e)}"
