import os
import subprocess
import sys
import re
import argparse
import json
import shlex
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

def init_client():
    global client
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.")
        sys.exit(1)
    client = Groq(api_key=api_key)

def execute_command(command):
    try:
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
        # Use shlex to split the command into a list
        command_list = shlex.split(command)

        # Run the command in a dry-run mode
        result = subprocess.run(command_list, capture_output=True, text=True, shell=False, check=True)

        # If the command runs successfully in dry-run mode, it's considered valid
        return True
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Bash command validation error: {e.stderr.strip()}")
    except Exception as e:
        raise ValueError(f"An error occurred during command validation: {e}")

def interpret_and_execute(user_input, model):
    try:
        prompt = f"""
        Interpret the following command and provide the appropriate bash commands to execute it:
        {user_input}

        Respond with only the bash commands, no explanation.
        """

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that translates natural language commands into bash commands."},
                {"role": "user", "content": prompt}
            ],
            model=model,
            max_tokens=1000
        )

        bash_commands = response.choices[0].message.content.strip()

        validate_command(bash_commands)
        validate_bash_command(bash_commands)

        bash_commands = check_file_directory(bash_commands)

        print(f"Executing: {bash_commands}")
        result = execute_command(bash_commands)
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

    args = parser.parse_args()

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

    init_client()

    user_input = " ".join(args.command)
    model = args.model

    print(f"Using model: {model}")
    interpret_and_execute(user_input, model)

if __name__ == "__main__":
    main()
