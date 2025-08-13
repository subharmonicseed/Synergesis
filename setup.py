from setuptools import setup, find_packages

setup(
    name="synergesis",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.100.0",
        "neo4j>=5.0.0",
        "pydantic>=2.0.0",
        "pytest>=7.0.0",
        "pytest-mock>=3.0.0",
    ],
    python_requires='>=3.8',
)
