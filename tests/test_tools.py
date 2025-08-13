# tests/test_tools.py
import pytest
import os
from tools.file_tool import FileTool
from tools.shell_tool import ShellTool

@pytest.fixture
def file_tool():
    return FileTool(base_dir="test_sandbox")

@pytest.fixture
def shell_tool():
    return ShellTool(allowed_commands=["echo", "ls"], cwd="test_sandbox")

def test_file_tool_write_read(file_tool):
    content = "Hello, Synergesis!"
    file_tool.write_file("test.txt", content)
    result = file_tool.read_file("test.txt")
    assert content in result

def test_file_tool_prevents_traversal(file_tool):
    with pytest.raises(ValueError):
        file_tool.read_file("../../etc/passwd")

def test_shell_tool_allowed_command(shell_tool):
    result = shell_tool.run("echo hello")
    assert "hello" in result

def test_shell_tool_blocks_disallowed(shell_tool):
    result = shell_tool.run("rm -rf /")
    assert "not allowed" in result

def test_shell_tool_timeout():
    slow_tool = ShellTool(timeout=1)
    result = slow_tool.run("sleep 5")
    assert "timed out" in result.lower()
