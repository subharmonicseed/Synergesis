"""Setuptools-based packaging for synergesis."""

from setuptools import setup, find_packages


setup(
    name="synergesis",
    version="0.1.0",
    description="Modular AI agent system with planning, memory, and tools",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "synergesis-chat=synergesis.cli.chat_cli:main",
        ],
    },
)

