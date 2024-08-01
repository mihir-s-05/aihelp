# AIHelp

AIHelp is a command-line tool that uses the GroqCloud API to interpret and execute natural language commands.

## Installation

1. Clone this repository
2. Navigate to the project directory
3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
4. Install the package:
   ```
   pip install -e .
   ```

## Configuration

Create a `.env` file in the project root directory with your GroqCloud API key:

```
GROQ_API_KEY=your_api_key_here
```

## Usage

Use the tool with a natural language command:

```
aihelp "your natural language command here"
```

### Model Management

- Specify a different Groq model for a single command:
  ```
  aihelp "your natural language command here" -m model_name
  ```

- Show the current default model:
  ```
  aihelp --show-model
  ```

- Set a new default model:
  ```
  aihelp --set-model model_name
  ```

- Reset to the original default model:
  ```
  aihelp --reset-model
  ```

### Examples

1. Default usage:
   ```
   aihelp "copy data.txt from /home/user/documents to /home/user/backup"
   ```

2. With a specific model (one-time use):
   ```
   aihelp "copy data.txt from /home/user/documents to /home/user/backup" -m llama-3.1-8b-instant
   ```

3. Set a new default model:
   ```
   aihelp --set-model llama-3.1-8b-instant
   ```

4. Show current default model:
   ```
   aihelp --show-model
   ```

5. Reset to original default model:
   ```
   aihelp --reset-model
   ```

## Note

- This tool executes commands on your system. Use with caution and review the generated commands before execution.
- The original default model is "llama-3.1-8b-instant". You can change this permanently using `--set-model` or temporarily using the `-m` flag.
- Your preferred model is stored in `~/.aihelp_config.json`.