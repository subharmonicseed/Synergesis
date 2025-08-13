# tools/shell_tool.py
import subprocess
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

class ShellTool:
    def __init__(self, allowed_commands: Optional[List[str]] = None, timeout: int = 30, cwd: Optional[str] = None):
        self.allowed_commands = allowed_commands or ["ls", "cat", "echo", "pwd", "mkdir", "touch", "dir", "type"]
        self.timeout = timeout
        self.cwd = cwd or os.getcwd()  # Restrict working directory

    def run(self, command: str) -> str:
        try:
            # Split command and validate first word
            cmd_list = command.strip().split()
            if not cmd_list:
                return "Error: Empty command"

            cmd_name = cmd_list[0]
            if cmd_name not in self.allowed_commands:
                return f"Error: Command '{cmd_name}' is not allowed."

            logger.info(f"Executing shell command: {command}")

            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Error: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out: {command}")
            return "Error: Command timed out"
        except Exception as e:
            logger.error(f"Shell command failed: {str(e)}")
            return f"Error: {str(e)}"
