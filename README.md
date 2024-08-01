
# AIHelp

AIHelp is a command-line tool that uses the GroqCloud API to interpret and execute natural language commands.

## Installation

### Prerequisites

- **Python 3.6 or higher**
- **pip** (Python package installer)

### Linux/Mac Installation

1. **Clone this repository**:
   ```bash
   git clone https://github.com/yourusername/aihelp.git
   cd aihelp
   ```

2. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the package**:
   ```bash
   pip install .
   ```

4. **Ensure the Command is Available**:
   - The `aihelp` script will be installed in your local bin directory (`/home/yourusername/.local/bin`).
   - Add this directory to your `PATH` by adding the following line to your `~/.bash_profile` (create it if it doesn’t exist):
     ```bash
     [ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc"
     ```
     And ensure `~/.bashrc` contains:
     ```bash
     export PATH="$PATH:/home/yourusername/.local/bin"
     ```

5. **Test the Installation**:
   Open a new terminal window and test the command:
   ```bash
   aihelp --help
   ```

### Windows Installation

1. **Clone this repository**:
   Open the Command Prompt or PowerShell and run:
   ```powershell
   git clone https://github.com/yourusername/aihelp.git
   cd aihelp
   ```

2. **Install the required packages**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Install the package**:
   ```powershell
   pip install .
   ```

4. **Add AIHelp to PATH**:
   To make `aihelp` available globally, you need to add the Scripts directory to your PATH. This is typically located at `C:\Users\YourUsername\AppData\Local\Programs\Python\PythonXX\Scripts`.

   - Search for "Environment Variables" in the Windows search bar.
   - Edit the `PATH` variable and add the directory above.

5. **Test the Installation**:
   Open a new Command Prompt or PowerShell window and test the command:
   ```powershell
   aihelp --help
   ```

## Configuration

Create a `.env` file in the project root directory with your GroqCloud API key:

```
GROQ_API_KEY=your_api_key_here
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

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with your improvements.
