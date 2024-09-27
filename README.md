# AIHelp

AIHelp is a command-line tool that uses the GroqCloud API to interpret and execute natural language commands.

## Installation

### Prerequisites

- **Python 3.6 or higher**
- **pipx** (recommended for installing Python applications)

### Installation Steps

1. **Install pipx** (if not already installed):
   ```bash
   sudo apt install pipx
   pipx ensurepath
   ```
   After running these commands, **restart your terminal** or run `source ~/.bashrc` to update your PATH.

2. **Clone this repository**:
   ```bash
   git clone https://github.com/mihir-s-05/aihelp.git
   cd aihelp
   ```

3. **Install AIHelp using pipx**:
   ```bash
   pipx install .
   ```

4. **Test the Installation**:
   Open a new terminal window and test the command:
   ```bash
   aihelp --help
   ```

## Configuration

Set up your GroqCloud API key as an environment variable:

1. Open your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`):
   ```bash
   nano ~/.bashrc
   ```

2. Add the following line at the end of the file:
   ```bash
   export GROQ_API_KEY=your_api_key_here
   ```

3. Save the file and reload your shell configuration:
   ```bash
   source ~/.bashrc
   ```

## Usage

Use the tool with a natural language command:

```bash
aihelp "your natural language command here"
```

### Model Management

- **Specify a different Groq model for a single command**:
  ```bash
  aihelp "your natural language command here" -m model_name
  ```

- **Show the current default model**:
  ```bash
  aihelp --show-model
  ```

- **Set a new default model**:
  ```bash
  aihelp --set-model model_name
  ```

- **Reset to the original default model**:
  ```bash
  aihelp --reset-model
  ```

### Examples

1. Default usage:
   ```bash
   aihelp "copy data.txt from /home/user/documents to /home/user/backup"
   ```

2. With a specific model (one-time use):
   ```bash
   aihelp "copy data.txt from /home/user/documents to /home/user/backup" -m llama-3.1-8b-instant
   ```

3. Set a new default model:
   ```bash
   aihelp --set-model llama-3.1-8b-instant
   ```

4. Show current default model:
   ```bash
   aihelp --show-model
   ```

5. Reset to original default model:
   ```bash
   aihelp --reset-model
   ```

## Note

- This tool executes commands on your system. Use with caution and review the generated commands before execution.
- The original default model is "llama-3.1-8b-instant". You can change this permanently using `--set-model` or temporarily using the `-m` flag.
- Your preferred model is stored in `~/.aihelp_config.json`.

## Uninstallation

To uninstall AIHelp, use the following command:
```bash
pipx uninstall aihelp
```

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with your improvements.
