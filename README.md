# AIHelp - Intelligent Command Line Assistant

AIHelp is a versatile command-line tool that translates your natural language queries into executable shell commands. It leverages various Large Language Models (LLMs) to understand your intent and provides a safer, more intuitive way to interact with your terminal.

## Features

*   **Natural Language to Command Translation:** Simply tell AIHelp what you want to do, and it will generate the appropriate shell command.
*   **Multi-Provider LLM Support:**
    *   Currently supports **Groq** (Llama 3.1, Mixtral, Gemma).
    *   Designed for easy extension, with skeleton support for **OpenAI (GPT models), Google (Gemini models), and Anthropic (Claude models)**. Full integration for these is planned.
*   **Platform Agnostic Goal:** While primarily developed and tested on Linux, the tool is designed with platform agnosticism in mind. Basic structures for platform-specific command considerations are included, aiming for future cross-platform compatibility.
*   **Flexible Model Selection:**
    *   Choose a global default LLM provider.
    *   Set default models for each provider.
    *   Override the provider and model on a per-command basis.
*   **Dangerous Command Detection & Confirmation:**
    *   AIHelp automatically checks generated commands against a list of configurable regular expression patterns designed to detect potentially harmful operations (e.g., `sudo rm -rf /`, `dd`, `mkfs`).
    *   If a dangerous pattern is matched, you will be prompted for explicit confirmation before execution, showing the command and the matched pattern.
    *   Use the `--force` (or `--skip-danger-check`) flag to bypass this interactive confirmation (use with extreme caution).
    *   Manage dangerous patterns via CLI: view, add, or remove regex patterns.
*   **Command Allowlist/Blocklist Policy:**
    *   Enforce fine-grained control over executable commands with three policy modes:
        *   `allow`: Only commands (or command prefixes ending with `*`) explicitly in the allowlist can be run.
        *   `block`: Commands (or command prefixes ending with `*`) in the blocklist are forbidden. All others are permitted (subject to dangerous command checks).
        *   `none`: No allowlist/blocklist policy is enforced (default).
    *   Manage the policy mode and the allow/block lists via CLI commands.
*   **Comprehensive Configuration:**
    *   User-specific settings are stored in `~/.aihelp_config.json`. The `~` symbol represents your home directory (e.g., `/Users/yourusername` on macOS, `/home/yourusername` on Linux, or `C:\Users\yourusername` on Windows).
    *   This file includes:
        *   Default LLM provider and model preferences for each provider.
        *   Environment variable names for API keys (API keys themselves are **not** stored).
        *   Customizable list of regex patterns for dangerous command detection.
        *   Command allowlist, blocklist, and the active policy mode.
    *   The configuration file is automatically created with sensible defaults on first run or if missing.
*   **Command Logging:**
    *   All interpreted commands, execution attempts, and key events can be logged to `~/.aihelp_command_log.txt` (located in your home directory as described above) when the `--log` flag is used.

## Installation

### Prerequisites

*   **Python 3.9 or higher** (due to dependencies like `google-generativeai`).
*   **pip** (Python package installer).
*   **Git** (for cloning the repository).

It's highly recommended to use Python virtual environments to manage dependencies and avoid conflicts with system-wide packages. This also helps in standardizing `python` and `pip` command usage.

### Installation Steps

1.  **Clone this repository**:
    ```bash
    git clone https://github.com/your-username/aihelp.git # Replace with the actual repository URL
    cd aihelp
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # On macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    
    # On Windows (Command Prompt)
    python -m venv .venv
    .venv\Scripts\activate.bat
    
    # On Windows (PowerShell)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    ```
    If you're not using a virtual environment, you might need to use `python3` and `pip3` instead of `python` and `pip` on some systems, especially macOS and Linux. Using virtual environments avoids this ambiguity.

3.  **Install dependencies and the package**:
    (Inside the activated virtual environment)
    ```bash
    pip install -r requirements.txt
    pip install .
    ```

4.  **Test the Installation**:
    Open a new terminal window (or ensure your virtual environment is active) and test the command:
    ```bash
    aihelp --help
    ```

## Setup

### 1. API Keys

AIHelp requires API keys for the LLM providers you intend to use. These keys must be set as environment variables. AIHelp **does not** store your API keys in its configuration file.

Supported environment variable names:

*   **Groq:** `GROQ_API_KEY`
*   **OpenAI:** `OPENAI_API_KEY`
*   **Google (Gemini):** `GOOGLE_API_KEY`
*   **Anthropic (Claude):** `ANTHROPIC_API_KEY`

**Setting Environment Variables:**

*   **macOS & Linux (bash/zsh):**
    To set an environment variable for your current session and persistently for future sessions, add the `export` command to your shell's profile file (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.profile`).

    1.  Open your shell configuration file. For example, for `bash`:
        ```bash
        nano ~/.bashrc
        ```
        For `zsh`:
        ```bash
        nano ~/.zshrc
        ```
    2.  Add the following lines for the providers you want to use, replacing `your_api_key_here` with your actual keys:
        ```bash
        export GROQ_API_KEY="your_groq_api_key_here"
        # export OPENAI_API_KEY="your_openai_api_key_here"
        # export GOOGLE_API_KEY="your_google_api_key_here"
        # export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
        ```
    3.  Save the file and reload your shell configuration (or open a new terminal):
        ```bash
        source ~/.bashrc  # Or source ~/.zshrc, etc.
        ```

*   **Windows:**

    *   **Command Prompt (Current Session Only):**
        To set an environment variable for the current Command Prompt session only:
        ```cmd
        set GROQ_API_KEY="your_groq_api_key_here"
        ```
        This variable will be lost when the Command Prompt window is closed.

    *   **PowerShell (Current Session Only):**
        To set an environment variable for the current PowerShell session only:
        ```powershell
        $env:GROQ_API_KEY="your_api_key_here"
        ```
        This variable will be lost when the PowerShell session is closed.

    *   **Persistent (System Properties):**
        For persistent environment variables on Windows:
        1.  Search for "environment variables" in the Start Menu.
        2.  Click on "Edit the system environment variables".
        3.  In the System Properties window, click the "Environment Variables..." button.
        4.  In the Environment Variables window, you can add or modify User variables (for your account) or System variables (for all users). Click "New..." under the appropriate section.
        5.  Enter the variable name (e.g., `GROQ_API_KEY`) and the variable value (your API key).
        6.  Click OK on all windows to save. You may need to restart your terminal or log out and log back in for these changes to take full effect.

### 2. Configuration File

The first time you run `aihelp` (e.g., `aihelp --list-providers`), it will automatically create a configuration file at `~/.aihelp_config.json` with default settings if one doesn't already exist. The `~` symbol represents your home directory:
*   On **macOS and Linux**, this is typically `/Users/yourusername` or `/home/yourusername`.
*   On **Windows**, this is typically `C:\Users\yourusername`.

You can manage most settings through the CLI, but you can also inspect this file.

## Usage

### Basic Command Execution

Translate natural language to a command:
```bash
aihelp "your natural language query here"
```
Example:
```bash
aihelp "list all files in the current directory that end with .py"
```

### Provider Selection

*   **Execute a command with a specific provider:**
    ```bash
    aihelp --provider openai "summarize the content of my_document.txt"
    ```
*   **List available LLM providers and their API key status:**
    ```bash
    aihelp --list-providers
    ```
*   **Set the global default LLM provider:**
    ```bash
    aihelp --set-default-provider groq
    ```

### Model Selection & Management

*   **List example models for a specific provider:**
    ```bash
    aihelp --list-models groq
    ```
*   **Set a new default model for a specific provider:**
    ```bash
    aihelp --set-model groq llama-3.1-70b-versatile
    ```
*   **Show the current default model for a specific provider:**
    ```bash
    aihelp --show-model groq
    ```
*   **Reset the default model for a provider to its original setting:**
    ```bash
    aihelp --reset-model openai
    ```
*   **Use a specific model for a single command (overrides defaults):**
    ```bash
    aihelp --provider groq --model mixtral-8x7b-32768 "find text 'error' in all log files"
    ```

### Dangerous Command Management

AIHelp checks generated commands against a list of regex patterns to prevent accidental execution of harmful commands.

*   **Execute a command that might be flagged as dangerous, bypassing interactive confirmation:**
    (Use with extreme caution!)
    ```bash
    aihelp --force "delete all files in the /tmp/my_temp_dir directory"
    ```
    Alternatively:
    ```bash
    aihelp --skip-danger-check "delete all files in the /tmp/my_temp_dir directory"
    ```
*   **View current dangerous command patterns:**
    ```bash
    aihelp --view-dangerous-patterns
    ```
*   **Add a new regex pattern to the dangerous list:**
    (Ensure your regex is valid and properly quoted by your shell)
    ```bash
    aihelp --add-dangerous-pattern "sudo\s+dangerous_utility\s+.*"
    ```
*   **Remove a regex pattern (by exact string or 1-based index from `--view`):**
    ```bash
    aihelp --remove-dangerous-pattern "sudo\s+dangerous_utility\s+.*"
    # or
    aihelp --remove-dangerous-pattern 3
    ```

### Command Policy Management (Allowlist/Blocklist)

Control which commands can be executed. Commands are checked after generation and basic syntax validation but before the dangerous command check. Policies apply to individual commands within a sequence (e.g., `cmd1 && cmd2`).

*   **Set the command policy mode:**
    *   `none`: (Default) No policy enforced.
    *   `allow`: Only commands in the allowlist are permitted.
    *   `block`: Commands in the blocklist are forbidden.
    ```bash
    aihelp --set-command-policy allow
    ```
*   **Show current command policy mode and lists:**
    ```bash
    aihelp --show-command-policy
    ```
*   **Manage Allowlist:**
    (Use `*` as a suffix for prefix matching, e.g., `git *` allows `git status`, `git commit`, etc.)
    ```bash
    aihelp --add-allowed-command "ls -la"
    aihelp --add-allowed-command "cat *"
    aihelp --remove-allowed-command "ls -la"
    aihelp --remove-allowed-command 1 # Removes by index from --show-command-policy
    ```
*   **Manage Blocklist:**
    ```bash
    aihelp --add-blocked-command "rm -rf"
    aihelp --remove-blocked-command "rm -rf"
    aihelp --remove-blocked-command 1 # Removes by index
    ```

### Logging

Enable logging of commands and actions to `~/.aihelp_command_log.txt` (in your home directory):
```bash
aihelp --log "your query here"
```

## Configuration File Details

The configuration file is located at `~/.aihelp_config.json`. The `~` symbol represents your user's home directory (e.g., `/Users/yourusername` on macOS, `/home/yourusername` on Linux, or `C:\Users\yourusername` on Windows).

It typically stores:

```json
{
  "default_provider": "groq",
  "providers": {
    "groq": {
      "api_key_env": "GROQ_API_KEY",
      "default_model": "llama-3.1-8b-instant",
      "last_used_model": "llama-3.1-8b-instant"
    },
    "openai": { /* ... */ },
    "google": { /* ... */ },
    "anthropic": { /* ... */ }
  },
  "dangerous_command_patterns": [
    "sudo\\s+rm\\s+-rf\\s+/\\s*(?![\\w./])",
    // ... other regex patterns ...
  ],
  "command_policy_mode": "none", // "allow", "block", or "none"
  "command_allowlist": [
    // "ls", "cat *", ...
  ],
  "command_blocklist": [
    // "rm -rf", ...
  ]
}
```
It's generally recommended to manage these settings via the CLI commands.

## Uninstallation

If installed in a virtual environment, simply deactivate and delete the environment.
If installed with `pip` globally (ensure you use `pip3` or `pip` consistently with how you installed it):
```bash
pip uninstall aihelp
```

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contributing

Contributions are welcome! If you have suggestions, feature requests, or bug reports, please open an issue on the GitHub repository. If you'd like to contribute code:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Add tests for your changes if applicable.
5.  Ensure your code follows existing style and linting practices.
6.  Submit a pull request with a clear description of your changes.

---

*AIHelp executes commands on your system. Always review generated commands carefully, especially when using the `--force` flag or modifying safety features.*
