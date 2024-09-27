from setuptools import setup, find_packages

setup(
    name="aihelp",
    version="0.3",
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
    author="Mihir Srivastava",
    author_email="mihir2k5@gmail.com",
    description="A CLI tool that uses GroqCloud API to interpret and execute natural language commands",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/mihir-s-05/aihelp",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
