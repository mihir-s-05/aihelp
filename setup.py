from setuptools import setup, find_packages

setup(
    name="aihelp",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "groq",
        "python-dotenv"
    ],
    entry_points={
        "console_scripts": [
            "aihelp=aihelp.cli:main",
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A CLI tool that uses GroqCloud API to interpret and execute natural language commands",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/aihelp",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)