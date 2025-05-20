"""
AIHelp: A CLI tool that translates natural language commands into bash commands
and executes them, using Groq API for language interpretation.
"""
import os
import subprocess
import sys
import re
import argparse
import json
import datetime
from dotenv import load_dotenv

# LLM Provider Imports (actual clients initialized later)
from groq import Groq
# from openai import OpenAI # Placeholder for future OpenAI client
# from google.generativeai import GenerativeModel # Placeholder
# from anthropic import Anthropic # Placeholder

load_dotenv()

# --- Global Configuration & Constants ---

CONFIG_FILE = os.path.expanduser("~/.aihelp_config.json")
SUPPORTED_PROVIDERS = ["groq", "openai", "google", "anthropic"]

# Original default models for each provider
ORIGINAL_DEFAULT_MODELS = {
    "groq": "llama-3.1-8b-instant",
    "openai": "gpt-3.5-turbo",
    "google": "gemini-1.5-flash-latest", # Updated example
    "anthropic": "claude-3-haiku-20240307",
}

# Default list of dangerous command patterns (regular expressions)
ORIGINAL_DEFAULT_DANGEROUS_PATTERNS = [
    r"sudo\s+rm\s+-rf\s+/\s*(?![\w./])",  # sudo rm -rf / (but not /usr or /home/user etc.)
    r"dd\s+if=/dev/zero\s+of=/dev/sd[a-z]+", # dd if=/dev/zero of=/dev/sda
    r"mkfs\.", # mkfs.ext4, mkfs.xfs, etc.
    r":\s*\(.*\)\s*\{.*;\s*};", # fork bomb variant 1
    r"\^\^", # fork bomb variant 2 (less common, but simple)
    r">\s*/dev/sd[a-z]+", # redirect output to disk device
    r"mv\s+.*\s+/dev/null", # moving something important to /dev/null
    # Add more researched patterns here
]

# --- Default Policy Settings ---
DEFAULT_COMMAND_POLICY_MODE = "none"
DEFAULT_COMMAND_ALLOWLIST = []
DEFAULT_COMMAND_BLOCKLIST = []


# API key environment variable names
API_KEY_ENV_VARS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY", # Often GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS
    "anthropic": "ANTHROPIC_API_KEY",
}

# Stores the initialized client for the current session
# e.g., {"groq": <GroqClientInstance>}
# This will be populated by get_llm_provider_client
active_clients = {}


def load_config():
    """
    Loads configuration from JSON file.
    If file doesn't exist or is invalid, creates a default structure.
    Ensures all supported providers have a basic config structure.
    """
    default_config = {
        "default_provider": "groq",
        "providers": {
            provider: {
                "api_key_env": API_KEY_ENV_VARS[provider],
                "default_model": ORIGINAL_DEFAULT_MODELS[provider],
                "last_used_model": ORIGINAL_DEFAULT_MODELS[provider],
            }
            for provider in SUPPORTED_PROVIDERS
        },
        "dangerous_command_patterns": list(ORIGINAL_DEFAULT_DANGEROUS_PATTERNS),
        "command_policy_mode": DEFAULT_COMMAND_POLICY_MODE,
        "command_allowlist": list(DEFAULT_COMMAND_ALLOWLIST),
        "command_blocklist": list(DEFAULT_COMMAND_BLOCKLIST),
    }
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file not found at {CONFIG_FILE}. Creating with default settings.")
        save_config(default_config) # Save immediately so it exists
        return default_config

    try:
        with open(CONFIG_FILE, 'r') as f:
            loaded_config = json.load(f)
            
        # Validate and merge with defaults to ensure all keys are present
        # Default provider
        if "default_provider" not in loaded_config or loaded_config["default_provider"] not in SUPPORTED_PROVIDERS:
            loaded_config["default_provider"] = default_config["default_provider"]
        
        # Providers structure
        if "providers" not in loaded_config:
            loaded_config["providers"] = default_config["providers"]
        else:
            for provider_key in SUPPORTED_PROVIDERS:
                if provider_key not in loaded_config["providers"]:
                    loaded_config["providers"][provider_key] = default_config["providers"][provider_key]
                else:
                    for key, value in default_config["providers"][provider_key].items():
                        if key not in loaded_config["providers"][provider_key]:
                            loaded_config["providers"][provider_key][key] = value
        
        # Ensure all supported providers are in the loaded config (handles newly added providers to the tool)
        for provider_key in SUPPORTED_PROVIDERS:
            if provider_key not in loaded_config["providers"]:
                loaded_config["providers"][provider_key] = default_config["providers"][provider_key]
        
        # Ensure API key env var names are always from our constants, not user-saved ones
        for provider_key in SUPPORTED_PROVIDERS:
            if provider_key in loaded_config["providers"]: # Should always be true after above
                 loaded_config["providers"][provider_key]["api_key_env"] = API_KEY_ENV_VARS[provider_key]

        # Dangerous command patterns
        if "dangerous_command_patterns" not in loaded_config or \
           not isinstance(loaded_config["dangerous_command_patterns"], list):
            loaded_config["dangerous_command_patterns"] = list(ORIGINAL_DEFAULT_DANGEROUS_PATTERNS)
        else:
            loaded_config["dangerous_command_patterns"] = [
                str(p) for p in loaded_config["dangerous_command_patterns"] if isinstance(p, str)
            ] # Basic validation: ensure all are strings
            if not loaded_config["dangerous_command_patterns"] and ORIGINAL_DEFAULT_DANGEROUS_PATTERNS: # only if default is not empty
                 # This case might be too aggressive if user intentionally wants an empty list
                 # For now, if it's empty, we assume it's an error if defaults are not empty.
                 # A better approach might be to only reset if the key type was wrong.
                 pass # Allow empty list if user explicitly set it.
        
        # Command policy settings
        if "command_policy_mode" not in loaded_config or \
           loaded_config["command_policy_mode"] not in ["allow", "block", "none"]:
            loaded_config["command_policy_mode"] = DEFAULT_COMMAND_POLICY_MODE
        
        if "command_allowlist" not in loaded_config or \
           not isinstance(loaded_config["command_allowlist"], list):
            loaded_config["command_allowlist"] = list(DEFAULT_COMMAND_ALLOWLIST)
        else: # Ensure all items are strings
            loaded_config["command_allowlist"] = [
                str(c) for c in loaded_config["command_allowlist"] if isinstance(c, str)
            ]

        if "command_blocklist" not in loaded_config or \
           not isinstance(loaded_config["command_blocklist"], list):
            loaded_config["command_blocklist"] = list(DEFAULT_COMMAND_BLOCKLIST)
        else: # Ensure all items are strings
            loaded_config["command_blocklist"] = [
                str(c) for c in loaded_config["command_blocklist"] if isinstance(c, str)
            ]

        # If the loaded config was modified (e.g., by adding new providers or keys), save it back.
        # This check is not perfect but covers many cases of schema updates.
        # A more robust check would involve deep comparison before and after merging defaults.
        # For now, if the file existed and we potentially modified loaded_config, we save.
        # The initial save_config(default_config) handles the case where the file doesn't exist.
        if os.path.exists(CONFIG_FILE): # Only save if it was an existing file we might have modified
            current_content_on_disk = {}
            with open(CONFIG_FILE, 'r') as f_read: # Re-read to compare
                current_content_on_disk = json.load(f_read)
            if loaded_config != current_content_on_disk:
                 print(f"Notice: Updating config file at {CONFIG_FILE} with new/missing provider defaults.")
                 save_config(loaded_config)

        return loaded_config
    except (IOError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load or parse config file {CONFIG_FILE}: {e}. Using default configuration.")
        # Fallback to default if there's an error with an existing file
        save_config(default_config) # Try to save a clean default config
        return default_config


def save_config(config_to_save):
    """Saves configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_to_save, f, indent=2)
    except IOError as e:
        print(f"Error: Could not save config file {CONFIG_FILE}: {e}")

# Initialize global config object
config = load_config()

# --- Logging ---
# (logging_enabled will be set from args in main)
logging_enabled_globally = False 

def init_log_file(logging_enabled_arg):
    """Initializes the command log file if logging is enabled."""
    global logging_enabled_globally
    logging_enabled_globally = logging_enabled_arg
    if not logging_enabled_globally:
        return # Exit early if logging is disabled

    log_file = os.path.expanduser("~/.aihelp_command_log.txt")
    if not os.path.exists(log_file):
        try:
            with open(log_file, "w") as f:
                f.write("AIHelp Command Log - Tracks commands executed by AIHelp\n")
                f.write("=" * 50 + "\n")
            print(f"Initialized log file: {log_file}")
        except IOError as e:
            print(f"Error: Could not create log file {log_file}: {e}")

# --- LLM Provider Abstraction (Skeleton) ---

class LLMProvider:
    """Base class for LLM providers."""
    def __init__(self, api_key_env_var):
        self.api_key = os.environ.get(api_key_env_var)
        self.client = None

    def is_configured(self):
        """Checks if the API key is set."""
        return bool(self.api_key)

    def get_completion(self, user_prompt, model_name, max_tokens=150, temperature=0.0):
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get_models(self): # For --list-models
        """Returns a list of example model names for the provider."""
        return ["model1-default", "model2-experimental"]


class GroqProvider(LLMProvider):
    def __init__(self):
        super().__init__(API_KEY_ENV_VARS["groq"])
        if self.is_configured():
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"Error: Failed to initialize Groq client: {e}")
                self.client = None # Ensure client is None if init fails
        else:
            print("Warning: Groq API key not found. Groq provider will not be available.")

    def get_completion(self, user_prompt_content, model_name, max_tokens=150, temperature=0.0):
        if not self.client:
            return "Error: Groq client not initialized or API key missing."
        
        # This is the detailed prompt structure from the previous version
        full_prompt = f"""
        You are an expert Linux system administrator. Your task is to translate the following natural language command into precise, correct, and safe bash commands:

        "{user_prompt_content}"

        Important guidelines for generating the bash command:
        1. Output ONLY the raw bash command(s). Do not include any descriptive text, explanations, or markdown formatting (e.g., no ```bash ... ```).
        2. Ensure the command is syntactically correct and directly executable in a standard bash shell.
        3. Use absolute paths for critical system utilities if there's any ambiguity (e.g., /bin/rm instead of rm), but prefer common command names if they are standard and unambiguous (e.g., mkdir, cp, ls).
        4. If multiple distinct steps are required, chain them using '&&' for sequential execution stopping on error, or ';' if subsequent commands should run regardless of prior success (use with caution). Prefer '&&'.
        5. Prioritize safety. Avoid commands that are destructive by nature unless explicitly and unambiguously requested (this system has other checks, but your first-line safety is crucial).
        6. If the user's request is dangerously ambiguous, unclear, or requests a potentially harmful action without sufficient clarity (e.g., "delete all files"), output only the string: "Error: Request is ambiguous or potentially harmful."
        7. If the request is too complex or clearly outside the scope of a bash command (e.g., "write a novel"), output: "Error: Request is out of scope."
        8. Do not ask for clarification. Provide the best possible command or one of the error strings above.

        User's natural language command: "{user_prompt_content}"
        Bash command:
        """
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a highly skilled Linux system administrator AI. Your sole purpose is to convert natural language requests into accurate and safe bash commands. You must strictly follow the user's formatting guidelines for the output."},
                    {"role": "user", "content": full_prompt}
                ],
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip() if response.choices and response.choices[0].message else ""
        except Exception as e:
            return f"Error during Groq API call: {e}"

    def get_models(self):
        return ["llama-3.1-8b-instant", "llama-3.1-70b-versatile", "gemma-7b-it", "mixtral-8x7b-32768"]


class OpenAIProvider(LLMProvider):
    def __init__(self):
        super().__init__(API_KEY_ENV_VARS["openai"])
        # Basic client initialization if key exists (actual OpenAI client not imported yet)
        if self.is_configured():
            # self.client = OpenAI(api_key=self.api_key) # Future
            pass # Placeholder
        else:
            print("Warning: OpenAI API key not found. OpenAI provider will not be available.")


    def get_completion(self, user_prompt_content, model_name, max_tokens=150, temperature=0.0):
        if not self.is_configured(): return "Error: OpenAI API key not configured."
        return "Provider OpenAI not yet fully implemented." # Placeholder

    def get_models(self):
        return ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "dall-e-3"] # Example models


class GoogleProvider(LLMProvider):
    def __init__(self):
        super().__init__(API_KEY_ENV_VARS["google"])
        if self.is_configured():
            # self.client = GenerativeModel(...) # Future
            pass # Placeholder
        else:
            print("Warning: Google API key not found. Google provider will not be available.")

    def get_completion(self, user_prompt_content, model_name, max_tokens=150, temperature=0.0):
        if not self.is_configured(): return "Error: Google API key not configured."
        return "Provider Google (Vertex/Gemini) not yet fully implemented." # Placeholder

    def get_models(self):
        return ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-1.0-pro"] # Example models


class AnthropicProvider(LLMProvider):
    def __init__(self):
        super().__init__(API_KEY_ENV_VARS["anthropic"])
        if self.is_configured():
            # self.client = Anthropic(api_key=self.api_key) # Future
            pass # Placeholder
        else:
            print("Warning: Anthropic API key not found. Anthropic provider will not be available.")


    def get_completion(self, user_prompt_content, model_name, max_tokens=150, temperature=0.0):
        if not self.is_configured(): return "Error: Anthropic API key not configured."
        return "Provider Anthropic not yet fully implemented." # Placeholder

    def get_models(self):
        return ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]


PROVIDER_CLASSES = {
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "anthropic": AnthropicProvider,
}

def get_llm_provider_client(provider_name):
    """Initializes and returns a client for the specified provider."""
    global active_clients
    global config # Ensure we are using the loaded config

    if provider_name in active_clients and active_clients[provider_name].client:
        return active_clients[provider_name]

    if provider_name not in SUPPORTED_PROVIDERS:
        print(f"Error: Provider '{provider_name}' is not supported.")
        return None

    # Ensure the provider has an entry in the config (load_config should handle this)
    if provider_name not in config["providers"]:
        print(f"Error: Configuration missing for provider '{provider_name}'. Try running `aihelp --reset-model {provider_name}` or check config file.")
        return None
        
    api_key_env_name = API_KEY_ENV_VARS.get(provider_name)
    if not os.environ.get(api_key_env_name):
        print(f"Warning: API key environment variable {api_key_env_name} for {provider_name} is not set.")
        # Still return an instance so user can try to set model, etc.
        # The is_configured() method of provider will reflect this.
    
    provider_class = PROVIDER_CLASSES.get(provider_name)
    if provider_class:
        instance = provider_class()
        active_clients[provider_name] = instance
        return instance
    else:
        print(f"Error: No implementation class found for provider '{provider_name}'.")
        return None

# --- Logging (continued) ---
def log_message(message_to_log): # Renamed from log_command to be more generic
    """Logs the given message to the log file with a timestamp if logging is enabled."""
    if not logging_enabled_globally: # Use the global flag
        return
    log_file = os.path.expanduser("~/.aihelp_command_log.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message_to_log}\n")
    except IOError as e:
        print(f"Warning: Could not write to log file {log_file}: {e}")

# --- Core Command Execution & Validation Logic (largely unchanged but uses log_message) ---

def execute_command(command_to_execute): # logging_enabled removed, uses global
    """
    Executes a shell command and returns its output.
    Logs the command execution details if logging is enabled.
    """
    try:
        # Command is logged by the caller (_execute_validated_commands) before this point
        result = subprocess.run(command_to_execute, capture_output=True, text=True, shell=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if logging_enabled_globally:
            log_message(f"Error executing: '{command_to_execute}'. Details: {e}. Stderr: {e.stderr.strip() if e.stderr else 'N/A'}")
        print(f"Error executing command: '{command_to_execute}'")
        print(f"  Reason: {e}")
        if e.stderr:
            print(f"  Error output (stderr):\n{e.stderr.strip()}")
        return None
    except FileNotFoundError as e:
        if logging_enabled_globally:
            log_message(f"Command not found: {e.filename} during execution of '{command_to_execute}'.")
        print(f"Error: Command not found: {e.filename}. Please ensure it's installed and in your PATH.")
        return None


def validate_command(command_to_validate): # No logging changes needed here directly
    """
    Validates a command against a list of potentially dangerous command patterns
    and checks for invalid file path formats.
    Raises ValueError if a pattern is matched (this function is for the initial, non-interactive check).
    Returns a tuple (is_potentially_dangerous, matched_pattern_string, error_message).
    If a dangerous pattern is matched, (True, pattern, None) is returned.
    If a path validation error occurs, (False, None, error_message) is returned.
    If no issues, (False, None, None) is returned.
    """
    global config # Use the loaded configuration for patterns
    
    # Check against dangerous command patterns first
    dangerous_patterns_list = config.get("dangerous_command_patterns", list(ORIGINAL_DEFAULT_DANGEROUS_PATTERNS))
    if not dangerous_patterns_list: # Fallback if config somehow has empty list
        dangerous_patterns_list = list(ORIGINAL_DEFAULT_DANGEROUS_PATTERNS)

    for pattern_regex in dangerous_patterns_list:
        try:
            if re.search(pattern_regex, command_to_validate):
                return True, pattern_regex, None # Potentially dangerous, pattern, no error message for this part
        except re.error as e:
            log_message(f"Regex error in dangerous command pattern: '{pattern_regex}'. Error: {e}. Skipping this pattern.")
            print(f"Warning: Invalid regex in dangerous_command_patterns: '{pattern_regex}'. Please fix or remove it.")
            # Continue to the next pattern
    
    # Then, perform path validation (original logic)
    # This part raises ValueError directly if an invalid path is found.
    # We should change this to return an error message instead of raising here.
    file_paths = re.findall(r'/(?:[\w.-]+/)*[\w.-]+', command_to_validate)
    for path_segment in file_paths:
        normalized_path = os.path.normpath(path_segment)
        # The original check was: `if not os.path.normpath(path).startswith('/')`
        # Let's refine this to be more explicit about what constitutes an invalid path.
        # For this CLI, assuming paths in commands should generally be absolute if specified with a leading '/'
        if path_segment.startswith('/') and not os.path.isabs(normalized_path):
             # This could happen if path is like "/../outside_root" but normpath resolves it weirdly
             # or if normpath itself fails. More likely, isabs() is the key.
            return False, None, f"Path validation error: '{path_segment}' (normalized: '{normalized_path}') seems invalid or malformed."

        # A simple check: if a path starts with '/', it should be absolute.
        # This is a basic heuristic. More complex validation might be needed for edge cases.
        if path_segment.startswith('/') and not normalized_path.startswith('/'): # after normpath
             # This specific check might be redundant if os.path.isabs covers it well.
             # The main goal is to catch things like `rm -rf / tmp/myfiles` where `/ tmp/...` might be misinterpreted by regex.
             # The regex for dangerous commands should be the primary defense for command structure.
             # This path validation is more about path *forms*.
            pass # This condition might be too noisy or already covered by `isabs`.

    return False, None, None # Not dangerous by pattern, no path error found by this function


def check_file_directory(command_text):
    """
    Identifies directory paths in a command string and creates them if they
    do not exist and their parent directory exists.
    This is a best-effort attempt for convenience and might not cover all cases.
    """
    # Regex to find potential directory paths (simplistic)
    # It looks for sequences starting with / and containing typical path characters,
    # possibly ending a word or the string.
    dir_paths = re.findall(r'(?:^|\s|="|\()(/[\w/.-]+)', command_text)
    created_paths = set()

    for path_candidate in dir_paths:
        # Normalize path to handle '..' or '.' and remove trailing slashes
        path = os.path.normpath(path_candidate)

        # Skip if it's likely a file by checking for an extension, or if it's just '/'
        if ('.' in os.path.basename(path) and '.' != os.path.basename(path)[0]) or path == '/':
            continue
        
        # Attempt to create if it doesn't exist and isn't a file
        if not os.path.exists(path) and path not in created_paths:
            try:
                # Check parent directory
                parent_dir = os.path.dirname(path)
                if not parent_dir: # Should not happen for absolute paths like /foo
                    continue
                if not os.path.exists(parent_dir):
                    print(f"Notice: Parent directory {parent_dir} for {path} does not exist. Skipping auto-creation.")
                    continue
                if not os.path.isdir(parent_dir):
                    print(f"Notice: Parent path {parent_dir} for {path} is not a directory. Skipping auto-creation.")
                    continue

                print(f"Notice: Directory {path} identified in command does not exist. Attempting to create.")
                os.makedirs(path, exist_ok=True)
                created_paths.add(path)
                print(f"Successfully created directory: {path}")
            except OSError as e:
                print(f"Warning: Could not create directory {path}: {e}. Proceeding with command execution.")
            except Exception as e: # Catch any other unexpected error during path creation
                print(f"Warning: An unexpected error occurred while trying to create directory {path}: {e}. Proceeding.")
    return command_text # Return original command text, creation is a side-effect


def validate_bash_command(command_to_validate):
    """
    Validates bash command syntax using `bash -n`.
    Raises ValueError if syntax is incorrect.
    """
    try:
        process = subprocess.run(['bash', '-n', '-c', command_to_validate], capture_output=True, text=True, check=False)
        if process.returncode != 0:
            error_message = process.stderr.strip() if process.stderr else "No error message from bash."
            if logging_enabled_globally:
                 log_message(f"Bash validation failed for: '{command_to_validate}'. Error: {error_message}")
            raise ValueError(f"Bash command syntax error: {error_message}\nCommand: '{command_to_validate}'")
        return True
    except FileNotFoundError:
        raise EnvironmentError("Bash executable not found. Please ensure bash is installed and in your PATH.")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred during bash command validation: {e}")

# --- LLM Interaction & Main Workflow ---

def get_llm_completion(provider_instance, user_input_text, model_to_use):
    """
    Gets command completion from the specified LLM provider.
    Args:
        provider_instance (LLMProvider): An initialized instance of an LLMProvider subclass.
        user_input_text (str): The natural language command from the user.
        model_to_use (str): The specific model name for the provider.
    Returns:
        str or None: The bash command string from the LLM, or None if an error occurs.
    """
    if not provider_instance or not provider_instance.is_configured():
        # Provider specific warnings (e.g. API key missing) should be handled by get_llm_provider_client or provider __init__
        print(f"Error: LLM provider client for '{provider_instance.__class__.__name__ if provider_instance else 'unknown'}' is not available or not configured. Cannot get completion.")
        log_message(f"LLM completion failed: {provider_instance.__class__.__name__ if provider_instance else 'unknown'} client not available/configured.")
        return None
    
    log_message(f"Requesting LLM completion from {provider_instance.__class__.__name__} for: '{user_input_text}' with model {model_to_use}")

    try:
        # The actual call to the provider's get_completion method
        # The prompt construction is now part of the GroqProvider, 
        # and will need to be generalized or made part of each provider.
        # For now, other providers will return their "not implemented" message.
        bash_commands = provider_instance.get_completion(user_input_text, model_to_use)

        if not bash_commands:
            error_msg = f"Error: {provider_instance.__class__.__name__} did not generate a command. The response was empty."
            print(error_msg)
            log_message(error_msg)
            return None
        
        if bash_commands.startswith("Error:"): # Handles errors from provider or our "not implemented" messages
            print(bash_commands) 
            log_message(f"LLM {provider_instance.__class__.__name__} responded with an error: {bash_commands}")
            return None

        log_message(f"LLM {provider_instance.__class__.__name__} completion successful. Received: '{bash_commands}'")
        return bash_commands

    except Exception as e:
        error_msg = f"Error communicating with {provider_instance.__class__.__name__} API: {e}"
        print(error_msg)
        log_message(f"{provider_instance.__class__.__name__} API communication error: {e}")
        return None


def _validate_commands(commands_to_validate): # logging_enabled removed
    """
    Validates the given commands for bash syntax.
    Security/dangerous pattern checks are now separate.
    Raises ValueError if syntax validation fails.
    """
    if logging_enabled_globally:
        log_message(f"Validating command (bash syntax): '{commands_to_validate}'")
    validate_bash_command(commands_to_validate) # This checks bash syntax


def _confirm_dangerous_command_execution(command_text, matched_pattern):
    """
    Prompts the user for confirmation to execute a potentially dangerous command.
    Returns True if user confirms, False otherwise.
    """
    print("\n" + "="*60)
    print("⚠️  DANGEROUS COMMAND DETECTED  ⚠️".center(60))
    print("="*60)
    print(f"\nThe command:\n  {command_text}")
    print(f"\nMatches the dangerous pattern:\n  {matched_pattern}")
    print("\nThis command could have unintended or destructive consequences.")
    
    while True:
        try:
            confirm = input("Do you want to proceed with executing this command? (yes/no): ").strip().lower()
            if confirm in ["yes", "y"]:
                log_message(f"User confirmed execution of dangerous command: '{command_text}' (pattern: '{matched_pattern}')")
                return True
            elif confirm in ["no", "n"]:
                log_message(f"User denied execution of dangerous command: '{command_text}' (pattern: '{matched_pattern}')")
                return False
            else:
                print("Invalid input. Please type 'yes' or 'no'.")
        except EOFError: # Handle Ctrl+D or redirected input
            print("\nConfirmation input aborted. Assuming 'no'.")
            log_message(f"User confirmation aborted for dangerous command: '{command_text}' (pattern: '{matched_pattern}'). Assuming no.")
            return False
        except KeyboardInterrupt: # Handle Ctrl+C
            print("\nConfirmation cancelled by user. Assuming 'no'.")
            log_message(f"User confirmation cancelled (KeyboardInterrupt) for dangerous command: '{command_text}' (pattern: '{matched_pattern}'). Assuming no.")
            return False

def _execute_validated_commands(commands_to_execute):
    """
    Prepares (e.g., creates directories) and executes validated commands.
    Logs the command to be executed. Uses global logging_enabled_globally.
    """
    # (Platform-specific comments remain relevant but omitted for brevity here)

    if logging_enabled_globally:
        log_message(f"Preparing environment for command: '{commands_to_execute}'")
    prepared_commands = check_file_directory(commands_to_execute) 

    if logging_enabled_globally:
        log_message(f"Final command for execution: {prepared_commands}")
    print(f"Executing: {prepared_commands}")
    
    result = execute_command(prepared_commands)
    
    if result is not None:
        print(f"Result:\n{result}")
    return result


def interpret_and_execute(user_input_cmd, provider_name_arg, model_name_arg):
    """
    Main workflow: gets command from AI, validates, checks policy, checks for danger, confirms, and executes.
    Uses global config and logging_enabled_globally.
    `skip_danger_check_arg` comes from args.force.
    """
    global config # Ensure we use the global config

    # Determine provider and model
    current_provider_name = provider_name_arg if provider_name_arg else config["default_provider"]
    provider_config = config["providers"].get(current_provider_name)
    if not provider_config:
        print(f"Error: Configuration for provider '{current_provider_name}' not found.")
        log_message(f"Execution failed: Configuration for provider '{current_provider_name}' not found.")
        return
    current_model_name = model_name_arg if model_name_arg else provider_config["default_model"]

    log_message(f"Starting interpretation. Provider: {current_provider_name}, Model: {current_model_name}, Input: '{user_input_cmd}'")

    provider_client = get_llm_provider_client(current_provider_name)
    if not provider_client or not provider_client.is_configured():
        log_message(f"Failed to get/initialize client for provider {current_provider_name}. Ensure API key is set.")
        return

    bash_commands = get_llm_completion(provider_client, user_input_cmd, current_model_name)
    if not bash_commands:
        return # Error already handled by get_llm_completion

    try:
        # Step 1: Basic syntax validation (raises ValueError on syntax error)
        _validate_commands(bash_commands) # Checks bash syntax

        # Step 2: Command Policy Check (Allow/Block lists)
        if not _check_command_policy(bash_commands):
            # _check_command_policy already prints and logs specific reasons
            print("Command execution aborted due to command policy.")
            log_message(f"Execution of '{bash_commands}' aborted due to command policy violation.")
            return # Abort execution
        
        # Step 3: Check for dangerous patterns and path issues from validate_command
        is_dangerous, matched_pattern, path_error_message = validate_command(bash_commands)

        if path_error_message:
            # If validate_command found a path error, treat it as a validation failure.
            raise ValueError(path_error_message)

        # Step 4: Handle dangerous command confirmation if needed
        if is_dangerous:
            log_message(f"Potentially dangerous command detected: '{bash_commands}' (Pattern: '{matched_pattern}')")
            if not skip_danger_check_arg: # if --force is not used
                print(f"\nInfo: The generated command has been flagged as potentially dangerous based on the pattern: '{matched_pattern}'.")
                if not _confirm_dangerous_command_execution(bash_commands, matched_pattern):
                    print("Execution aborted by user due to dangerous command detection.")
                    log_message(f"Execution of '{bash_commands}' aborted by user (dangerous command).")
                    return # Abort execution
                # If user confirmed, proceed
            else: # --force was used
                print(f"Warning: Executing potentially dangerous command due to --force flag: '{bash_commands}' (Pattern: '{matched_pattern}')")
                log_message(f"User forced execution of dangerous command: '{bash_commands}' (Pattern: '{matched_pattern}') via --force flag.")

        # Step 5: Execute if all checks passed or were overridden
        _execute_validated_commands(bash_commands)
        
        config["providers"][current_provider_name]["last_used_model"] = current_model_name
        save_config(config)

    except ValueError as e:
        error_message = f"Command processing error: {e}"
        print(error_message)
        if logging_enabled_globally:
            log_message(f"Error during processing of '{bash_commands}': {e}")
    except EnvironmentError as e:
        error_message = f"Environment error: {e}"
        print(error_message)
        if logging_enabled_globally:
            log_message(f"Environment error for '{bash_commands}': {e}")
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        if logging_enabled_globally:
            log_message(f"Unexpected error for '{bash_commands}': {e}")


def main():
    """Parses arguments, initializes, and runs the command interpretation process."""
    global config  # To allow main to modify config via set/reset model
    global logging_enabled_globally # To set based on args global config
    
    # This function needs to be defined before it's called in interpret_and_execute
    # or at least before main() calls interpret_and_execute.
    # Let's define it higher up, after config loading and logging setup.
    
# (Moving _check_command_policy definition higher up, before main)

def _check_command_policy(generated_commands_string):
    """
    Checks the generated command string against the configured command policy.
    Returns True if the command is permitted, False otherwise.
    """
    policy_mode = config.get("command_policy_mode", DEFAULT_COMMAND_POLICY_MODE)
    
    if policy_mode == "none":
        return True

    allowlist = config.get("command_allowlist", [])
    blocklist = config.get("command_blocklist", [])

    # Simple parsing: split by '&&' then by ';'. This handles common chains.
    # More complex parsing (e.g., subshells, pipes with complex commands) is not handled here.
    # Commands are stripped of leading/trailing whitespace for matching.
    
    # First split by '&&' which has higher precedence in shell execution usually
    chained_commands_and = generated_commands_string.split("&&")
    individual_commands = []
    for cmd_part_and in chained_commands_and:
        # Then split each part by ';'
        chained_commands_semicolon = cmd_part_and.split(";")
        for cmd_part_semi in chained_commands_semicolon:
            cmd_stripped = cmd_part_semi.strip()
            if cmd_stripped: # Avoid empty strings if there are consecutive separators
                individual_commands.append(cmd_stripped)
    
    if not individual_commands and generated_commands_string.strip(): # If no separators, check the whole string
        individual_commands = [generated_commands_string.strip()]
    
    if not individual_commands: # Should not happen if generated_commands_string is not empty
        return True # Or False, depending on desired strictness for empty commands

    log_message(f"Checking command policy. Mode: {policy_mode}. Commands to check: {individual_commands}")

    if policy_mode == "allow":
        if not allowlist: # If allowlist is empty, and mode is "allow", effectively nothing is allowed.
            print("Command policy is 'allow', but the allowlist is empty. No commands permitted.")
            log_message(f"Command '{generated_commands_string}' rejected: Policy is 'allow' and allowlist is empty.")
            return False
        for cmd in individual_commands:
            # For exact match:
            is_allowed = False
            for allowed_cmd_pattern in allowlist:
                if cmd == allowed_cmd_pattern: # Exact match
                    is_allowed = True
                    break
                # Simple prefix match (e.g. "git *" becomes "git ")
                if allowed_cmd_pattern.endswith("*") and cmd.startswith(allowed_cmd_pattern[:-1].strip()):
                    is_allowed = True
                    break
            if not is_allowed:
                print(f"Command '{cmd}' (part of '{generated_commands_string}') is not in the allowlist.")
                log_message(f"Command '{cmd}' rejected: Not in allowlist. Full command: '{generated_commands_string}'")
                return False
        log_message(f"All parts of command '{generated_commands_string}' are in the allowlist.")
        return True

    elif policy_mode == "block":
        for cmd in individual_commands:
            # For exact match:
            for blocked_cmd_pattern in blocklist:
                if cmd == blocked_cmd_pattern: # Exact match
                    print(f"Command '{cmd}' (part of '{generated_commands_string}') is in the blocklist.")
                    log_message(f"Command '{cmd}' rejected: Found in blocklist. Full command: '{generated_commands_string}'")
                    return False
                # Simple prefix match
                if blocked_cmd_pattern.endswith("*") and cmd.startswith(blocked_cmd_pattern[:-1].strip()):
                    print(f"Command '{cmd}' (part of '{generated_commands_string}') matches blocklist pattern '{blocked_cmd_pattern}'.")
                    log_message(f"Command '{cmd}' rejected: Matches blocklist pattern '{blocked_cmd_pattern}'. Full command: '{generated_commands_string}'")
                    return False
        log_message(f"No parts of command '{generated_commands_string}' found in blocklist.")
        return True

    return True # Should not be reached if mode is one of allow/block/none


def main():
    """Parses arguments, initializes, and runs the command interpretation process."""
    global config  # To allow main to modify config via set/reset model
    global logging_enabled_globally # To set based on args

    parser = argparse.ArgumentParser(
        description="AIHelp: Translates natural language to bash commands using various LLMs.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"""
Examples:
  aihelp create a new directory called 'my_new_folder'
  aihelp --provider openai list all python files
  aihelp --model gemini-1.5-pro-latest --provider google summarize /var/log/syslog
  aihelp --log show me the disk usage for the home directory

Supported Providers: {', '.join(SUPPORTED_PROVIDERS)}

Configuration:
  Default provider and models are stored in {CONFIG_FILE}
  API keys must be set as environment variables (e.g., GROQ_API_KEY, OPENAI_API_KEY).
"""
    )
    parser.add_argument("command", nargs="*", help="The natural language command to interpret and execute.")
    parser.add_argument("-p", "--provider", choices=SUPPORTED_PROVIDERS + [None], default=None,
                        help="Specify the LLM provider to use. If not set, uses default_provider from config.")
    parser.add_argument("-m", "--model", default=None, help="Specify the model to use. If not set, uses default_model for the selected provider.")
    parser.add_argument("--force", "--skip-danger-check", action="store_true", help="Bypass the interactive dangerous command confirmation. Use with caution.")

    config_group = parser.add_argument_group("Configuration Management")    
    config_group.add_argument("--list-providers", action="store_true", help="List all supported LLM providers and exit.")
    config_group.add_argument("--list-models", choices=SUPPORTED_PROVIDERS, metavar="PROVIDER",
                              help="List example models for a specific provider and exit.")
    config_group.add_argument("--show-model", choices=SUPPORTED_PROVIDERS, metavar="PROVIDER",
                              help="Display the current default model for a specific provider and exit.")
    config_group.add_argument("--set-model", nargs=2, metavar=("PROVIDER", "MODEL_NAME"),
                              help="Set a new default model for a specific provider and exit.")
    config_group.add_argument("--reset-model", choices=SUPPORTED_PROVIDERS, metavar="PROVIDER",
                              help="Reset the default model for a specific provider to its original default and exit.")
    config_group.add_argument("--set-default-provider", choices=SUPPORTED_PROVIDERS, metavar="PROVIDER",
                              help="Set the global default provider for aihelp and exit.")
    
    danger_group = parser.add_argument_group("Dangerous Command Pattern Management")
    danger_group.add_argument("--view-dangerous-patterns", action="store_true", help="View current dangerous command patterns and exit.")
    danger_group.add_argument("--add-dangerous-pattern", metavar="REGEX_PATTERN", help="Add a new regex pattern to the dangerous command list and exit.")
    danger_group.add_argument("--remove-dangerous-pattern", metavar="REGEX_PATTERN_OR_INDEX", help="Remove a regex pattern (by string or 1-based index) from the dangerous command list and exit.")

    policy_group = parser.add_argument_group("Command Policy Management (Allow/Block lists)")
    policy_group.add_argument("--set-command-policy", choices=["allow", "block", "none"], help="Set the active command policy mode (allow, block, none) and exit.")
    policy_group.add_argument("--show-command-policy", action="store_true", help="Show current command policy mode and lists, then exit.")
    policy_group.add_argument("--add-allowed-command", metavar="COMMAND", help="Add a command to the allowlist and exit.")
    policy_group.add_argument("--remove-allowed-command", metavar="COMMAND_OR_INDEX", help="Remove a command from the allowlist (by string or 1-based index) and exit.")
    policy_group.add_argument("--add-blocked-command", metavar="COMMAND", help="Add a command to the blocklist and exit.")
    policy_group.add_argument("--remove-blocked-command", metavar="COMMAND_OR_INDEX", help="Remove a command from the blocklist (by string or 1-based index) and exit.")

    parser.add_argument("--log", action="store_true", help=f"Enable detailed logging to {os.path.expanduser('~/.aihelp_command_log.txt')}")

    args = parser.parse_args()
    
    # Update global config if it's modified by pattern management args
    # This needs to be done before other operations that might use the config
    
    logging_enabled_globally = args.log # Set logging status early
    init_log_file(logging_enabled_globally) # Initialize log file based on arg state
    
    # Handle dangerous pattern management and command policy management commands first
    # as they modify config and should typically exit.

    if args.view_dangerous_patterns:
        print("Current dangerous command patterns (regex):")
        patterns = config.get("dangerous_command_patterns", [])
        if patterns:
            for i, pattern in enumerate(patterns):
                print(f"  {i+1}: {pattern}")
        else:
            print("  No dangerous command patterns defined.")
        return

    if args.add_dangerous_pattern:
        new_pattern = args.add_dangerous_pattern
        try:
            re.compile(new_pattern) # Validate regex
        except re.error as e:
            print(f"Error: Invalid regex pattern '{new_pattern}': {e}")
            sys.exit(1)
        # Ensure the list exists and is a list
        if not isinstance(config.get("dangerous_command_patterns"), list):
            config["dangerous_command_patterns"] = [] # Initialize if not list or missing
        
        if new_pattern not in config["dangerous_command_patterns"]:
            config["dangerous_command_patterns"].append(new_pattern)
            save_config(config)
            print(f"Added dangerous pattern: {new_pattern}")
        else:
            print(f"Pattern '{new_pattern}' already exists in dangerous_command_patterns.")
        return

    if args.remove_dangerous_pattern:
        pattern_to_remove = args.remove_dangerous_pattern
        patterns_list = config.get("dangerous_command_patterns")
        if isinstance(patterns_list, list):
            removed_by_str = False
            if pattern_to_remove in patterns_list:
                patterns_list.remove(pattern_to_remove)
                save_config(config)
                print(f"Removed dangerous pattern: {pattern_to_remove}")
                removed_by_str = True
            
            if not removed_by_str: # Try by index if not removed by string match
                try:
                    idx_to_remove = int(pattern_to_remove) - 1 # 1-based index for user
                    if 0 <= idx_to_remove < len(patterns_list):
                        removed_item = patterns_list.pop(idx_to_remove)
                        save_config(config)
                        print(f"Removed dangerous pattern (by index {idx_to_remove+1}): {removed_item}")
                    else:
                        print(f"Invalid index: {pattern_to_remove}. Use --view-dangerous-patterns to see indices.")
                except ValueError: # Not an int, and not found by string match earlier
                     print(f"Pattern '{pattern_to_remove}' not found. Use --view-dangerous-patterns to see existing patterns/indices.")
        else:
            print("No dangerous patterns configured to remove, or 'dangerous_command_patterns' is not a list.")
        return

    if args.set_command_policy:
        config["command_policy_mode"] = args.set_command_policy
        save_config(config)
        print(f"Command policy mode set to: {config['command_policy_mode']}")
        return

    if args.show_command_policy:
        print(f"Current command policy mode: {config.get('command_policy_mode', DEFAULT_COMMAND_POLICY_MODE)}")
        print("\nAllowed commands:")
        allow_list = config.get("command_allowlist", [])
        if allow_list:
            for i, cmd in enumerate(allow_list):
                print(f"  {i+1}: {cmd}")
        else:
            print("  (empty)")
        print("\nBlocked commands:")
        block_list = config.get("command_blocklist", [])
        if block_list:
            for i, cmd in enumerate(block_list):
                print(f"  {i+1}: {cmd}")
        else:
            print("  (empty)")
        return

    # Helper for add/remove from allow/block lists
    def manage_command_list(list_name, command_to_add_or_remove, add_action):
        if not isinstance(config.get(list_name), list):
             config[list_name] = [] # Initialize if not list or missing
        
        target_list = config[list_name]
        action_str = "Added to" if add_action else "Removed from"
        item_str = command_to_add_or_remove

        if add_action:
            if command_to_add_or_remove not in target_list:
                target_list.append(command_to_add_or_remove)
                save_config(config)
                print(f"{action_str} {list_name}: {command_to_add_or_remove}")
            else:
                print(f"Command '{command_to_add_or_remove}' already exists in {list_name}.")
        else: # Remove action
            removed_by_str = False
            if command_to_add_or_remove in target_list:
                target_list.remove(command_to_add_or_remove)
                save_config(config)
                print(f"{action_str} {list_name}: {command_to_add_or_remove}")
                removed_by_str = True
            
            if not removed_by_str: # Try by index
                try:
                    idx_to_remove = int(command_to_add_or_remove) - 1
                    if 0 <= idx_to_remove < len(target_list):
                        removed_item = target_list.pop(idx_to_remove)
                        save_config(config)
                        print(f"{action_str} {list_name} (by index {idx_to_remove+1}): {removed_item}")
                    else:
                        print(f"Invalid index: {command_to_add_or_remove} for {list_name}.")
                except ValueError:
                    print(f"Command '{command_to_add_or_remove}' not found in {list_name}.")
    
    if args.add_allowed_command:
        manage_command_list("command_allowlist", args.add_allowed_command, add_action=True)
        return
    if args.remove_allowed_command:
        manage_command_list("command_allowlist", args.remove_allowed_command, add_action=False)
        return
    if args.add_blocked_command:
        manage_command_list("command_blocklist", args.add_blocked_command, add_action=True)
        return
    if args.remove_blocked_command:
        manage_command_list("command_blocklist", args.remove_blocked_command, add_action=False)
        return

    # --- Standard config commands ---
    if args.list_providers: # This and other provider/model ops should come after policy/danger ops
        print("Supported LLM Providers:")
        for p_name in SUPPORTED_PROVIDERS:
            client_instance = get_llm_provider_client(p_name) # To check API key status
            status = "Configured (API key found)" if client_instance and client_instance.is_configured() else "Not Configured (API key missing or invalid)"
            print(f"  - {p_name} ({status})")
        return

    if args.list_models:
        provider_to_list = args.list_models
        client_instance = get_llm_provider_client(provider_to_list)
        if client_instance:
            print(f"Example models for {provider_to_list}:")
            for model_example in client_instance.get_models():
                print(f"  - {model_example}")
        else:
            # This case should ideally not be reached if get_llm_provider_client handles unknown providers
            print(f"Could not get models for provider: {provider_to_list}. Provider might be unsupported or misconfigured.")
        return

    if args.show_model:
        provider_to_show = args.show_model
        if provider_to_show in config["providers"]:
            print(f"Current default model for {provider_to_show}: {config['providers'][provider_to_show]['default_model']}")
        else:
            print(f"Provider {provider_to_show} not found in configuration.")
        return

    if args.set_model:
        provider_to_set, new_model = args.set_model
        if provider_to_set not in SUPPORTED_PROVIDERS:
            print(f"Error: Provider '{provider_to_set}' is not supported.")
            sys.exit(1)
        config["providers"][provider_to_set]["default_model"] = new_model
        save_config(config)
        print(f"Default model for {provider_to_set} has been set to: {new_model}")
        return

    if args.reset_model:
        provider_to_reset = args.reset_model
        if provider_to_reset not in SUPPORTED_PROVIDERS:
            print(f"Error: Provider '{provider_to_reset}' is not supported.")
            sys.exit(1)
        original_model = ORIGINAL_DEFAULT_MODELS[provider_to_reset]
        config["providers"][provider_to_reset]["default_model"] = original_model
        save_config(config)
        print(f"Default model for {provider_to_reset} has been reset to: {original_model}")
        return
        
    if args.set_default_provider:
        new_default_provider = args.set_default_provider
        config["default_provider"] = new_default_provider
        save_config(config)
        print(f"Global default provider has been set to: {new_default_provider}")
        return

    # --- Main execution logic ---
    if not args.command:
        parser.print_help()
        if logging_enabled_globally:
            log_message("No command provided, showing help.")
        return

    user_input = " ".join(args.command).strip()
    
    # Determine provider: use arg, then config default.
    chosen_provider = args.provider if args.provider else config["default_provider"]
    provider_specific_config = config["providers"].get(chosen_provider)
    if not provider_specific_config:
        print(f"Error: Configuration for provider '{chosen_provider}' is missing. Cannot determine model.")
        log_message(f"Execution failed: Configuration for provider '{chosen_provider}' missing.")
        sys.exit(1)
    chosen_model = args.model if args.model else provider_specific_config["default_model"]

    if logging_enabled_globally:
        log_message(f"AIHelp Invoked. Provider: {chosen_provider}, Model: {chosen_model}, Input: '{user_input}', Logging: {logging_enabled_globally}, Force: {args.force}")
    
    print(f"Interpreting: \"{user_input}\"")
    print(f"Using Provider: {chosen_provider}, Model: {chosen_model}")
    if args.force:
        print("Running with --force: Dangerous command checks will be bypassed if confirmed by pattern.")
    if logging_enabled_globally:
        print(f"Logging to: {os.path.expanduser('~/.aihelp_command_log.txt')}")
    
    interpret_and_execute(user_input, chosen_provider, chosen_model, args.force)

if __name__ == "__main__":
    main()
