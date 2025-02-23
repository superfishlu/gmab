# setup.py
from setuptools import setup, find_packages
from pathlib import Path

def read_requirements(filename: str):
    return [line.strip() for line in Path(filename).read_text().splitlines()
            if line.strip() and not line.startswith('#')]

# Read the requirements
requirements = read_requirements('requirements.txt')

setup(
    name="gmab",
    version="0.1.0",
    description="Give Me A Box - CLI tool to spawn, list, and manage temporary cloud boxes",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Your Name",  # Add your name
    author_email="your.email@example.com",  # Add your email
    url="https://github.com/yourusername/gmab",  # Add your repo URL
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gmab=gmab.cli:main"
        ]
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)