import os
from setuptools import setup, find_packages

# Define dependencies here directly, as requirements.txt might not be perfectly in sync
# or might have issues being overwritten in the sandbox.
install_requires = [
    "groq==0.9.0",
    "python-dotenv==1.0.1",
    "openai>=1.79.0,<2.0.0",
    "google-generativeai>=0.8.5,<0.9.0",
    "anthropic>=0.20.0,<0.21.0",
    "pytest>=7.0.0,<8.0.0", # Included for users who might run tests from source
]

# Read README.md for long description
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="aihelp",
    version="0.4.0", # Incremented version for this feature update
    packages=find_packages(exclude=["tests", "tests.*"]), # Exclude tests from package
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "aihelp=aihelp.cli:main",
        ],
    },
    author="AI Squared", # Placeholder, update if needed
    author_email="dev@example.com", # Placeholder
    description="A CLI tool to translate natural language to bash commands using various LLMs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/aihelp", # Placeholder, update with actual URL
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License", 
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta", # Reflecting current state
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Shells",
        "Topic :: Utilities",
    ],
    python_requires='>=3.9', # Updated due to google-generativeai requirement
)
