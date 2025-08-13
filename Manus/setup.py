#!/usr/bin/env python3
# File: setup.py
# Description: Script d'installation pour le pipeline Synergesis

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="synergesis-pipeline",
    version="1.0.0",
    author="Équipe Synergesis",
    author_email="contact@synergesis.ai",
    description="Pipeline réflexif topologique pour le projet Synergesis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/synergesis/synergesis-pipeline",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "synergesis-pipeline=synergesis_pipeline.synergesis_reflexive_pipeline:main",
        ],
    },
)
