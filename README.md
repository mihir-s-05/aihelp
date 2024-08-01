# AIHelp

AIHelp is a command-line tool that uses the GroqCloud API to interpret and execute natural language commands.

## Installation

1. Clone this repository
2. Navigate to the project directory
3. Run `pip install -e .`

## Usage

Set your GroqCloud API key as an environment variable:

```
export GROQ_API_KEY=your_api_key_here
```

Then use the tool:

```
aihelp "your natural language command here"
```

You can optionally specify a different Groq model using the `-m` flag:

```
aihelp "your natural language command here" -m model_name
```

For example:

```
aihelp "copy data.txt from /home/user/documents to /home/user/backup"
```

Or with a specific model:

```
aihelp "copy data.txt from /home/user/documents to /home/user/backup" -m llama2-70b-4096
```

## Note

This tool executes commands on your system. Use with caution and review the generated commands before execution.

The default model used is "llama-3.1-8b-instant". You can change this by using the `-m` flag followed by the desired model name.