import os
import subprocess
import sys
import re
import argparse
import json
import shlex
import datetime
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

client = None
ORIGINAL_DEFAULT_MODEL = "llama-3.1-8b-instant"
CONFIG_FILE = os.path.expanduser("~/.aihelp_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"default_model": ORIGINAL_DEFAULT_MODEL}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

config = load_config()
DEFAULT_MODEL = config["default_model"]

def init_log_file(logging_enabled):
    if not logging_enabled:
        return
    log_file = os.path.expanduser("~/.aihelp_command_log.txt")
    if not os.path.exists(log_file):
        try:
            with open(log_file, "w") as f:
                f.write("AIHelp Command Log\n")
            print(f"Initialized log file: {log_file}")
        except IOError as e:
            print(f"Error creating log file: {e}")
            print(f"Attempted to create: {log_file}")

def init_client():
    global client
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.")
        sys.exit(1)
    client = Groq(api_key=api_key)

def log_command(command, logging_enabled):
    if not logging_enabled:
        return
    log_file = os.path.expanduser("~/.aihelp_command_log.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_file, "a") as f:
            f.write(f"{timestamp}: {command}\n")
    except IOError as e:
        print(f"Error writing to log file: {e}")
        print(f"Attempted to write to: {log_file}")

def execute_command(command, logging_enabled):
    try:
        log_command(command, logging_enabled)
        result = subprocess.run(command, capture_output=True, text=True, shell=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"Error output: {e.stderr}")
        return None

def validate_command(command):
    dangerous_commands = ['rm -rf', 'mkfs', 'dd', '> /dev/sda', '| sh', '> /dev/null']

    for dangerous in dangerous_commands:
        if dangerous in command:
            raise ValueError(f"Potentially dangerous command detected: {dangerous}")

    file_paths = re.findall(r'/[\w/.-]+', command)
    for path in file_paths:
        if not os.path.normpath(path).startswith('/'):
            raise ValueError(f"Invalid file path detected: {path}")

    return True

def check_file_directory(command):
    dir_paths = re.findall(r'(?:^|\s)(/[\w/.-]+)(?=\s|$)', command)

    for path in dir_paths:
        if not os.path.exists(path):
            parent_dir = os.path.dirname(path)
            if os.path.isdir(parent_dir):
                print(f"Creating directory: {path}")
                os.makedirs(path, exist_ok=True)
            else:
                print(f"Parent directory does not exist: {parent_dir}")

    return command

def validate_bash_command(command):
    try:
        # Use bash -n to check syntax without executing
        result = subprocess.run(['bash', '-n', '-c', command], capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Bash command syntax error: {e.stderr.strip()}")
    except Exception as e:
        raise ValueError(f"An error occurred during command validation: {e}")

def interpret_and_execute(user_input, model, logging_enabled):
    init_client()
    if client is None:
        print("Error: Unable to initialize the Groq client. Please check your API key and internet connection.")
        return
    try:
        prompt = f"""
        You are an expert Linux system administrator. Your task is to translate the following natural language command into precise, correct, and safe bash commands:

        "{user_input}"

        Important guidelines:
        1. Provide ONLY the bash commands, with no explanations or markdown.
        2. Ensure the commands are syntactically correct and executable in a bash shell.
        3. Use full paths for commands when necessary (e.g., /usr/bin/grep instead of just grep).
        4. Include necessary error checking and safeguards where appropriate.
        5. If multiple commands are needed, use a single line with semicolons or && between commands.
        6. Do not include any potentially dangerous or destructive commands.
        7. If the request is ambiguous or requires more information, do not guess. Instead, output: "Error: More information required."

        Output the bash command(s) now:
        """

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that translates natural language commands into bash commands."},
                {"role": "user", "content": prompt}
            ],
            model=model,
            max_tokens=1000
        )

        bash_commands = response.choices[0].message.content.strip() if response.choices else ""

        if not bash_commands:
            print("Error: No command was generated. Please try rephrasing your request.")
            return

        validate_command(bash_commands)
        validate_bash_command(bash_commands)

        bash_commands = check_file_directory(bash_commands)

        log_command(bash_commands, logging_enabled)
        print(f"Executing: {bash_commands}")
        result = execute_command(bash_commands, logging_enabled)
        if result is not None:
            print(f"Result: {result}")
    except ValueError as e:
        print(f"Command validation error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    parser = argparse.ArgumentParser(description="AIHelp: Interprets and executes natural language commands.")
    parser.add_argument("command", nargs="*", help="The natural language command to interpret and execute.")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Specify the Groq model to use (default: %(default)s)")
    parser.add_argument("--show-model", action="store_true", help="Display the current default model")
    parser.add_argument("--set-model", help="Set a new default model")
    parser.add_argument("--reset-model", action="store_true", help="Reset the default model to the original")
    parser.add_argument("--log", action="store_true", help="Enable logging of executed commands")

    args = parser.parse_args()
    logging_enabled = args.log

    init_log_file(logging_enabled) # Initialize the log file if logging is enabled

    if args.show_model:
        print(f"Current default model: {DEFAULT_MODEL}")
        return

    if args.set_model:
        config["default_model"] = args.set_model
        save_config(config)
        print(f"Default model has been set to: {args.set_model}")
        return

    if args.reset_model:
        config["default_model"] = ORIGINAL_DEFAULT_MODEL
        save_config(config)
        print(f"Default model has been reset to: {ORIGINAL_DEFAULT_MODEL}")
        return

    if not args.command:
        parser.print_help()
        return

    user_input = " ".join(args.command)
    model = args.model
    logging_enabled = args.log

    print(f"Using model: {model}")
    print(f"Logging {'enabled' if logging_enabled else 'disabled'}")
    interpret_and_execute(user_input, model, logging_enabled)

if __name__ == "__main__":
    main()
