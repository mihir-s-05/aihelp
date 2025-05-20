import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import json
import tempfile
import shutil
import sys

# Add the project root to the Python path to allow importing aihelp.cli
# This is often needed when running tests from a subdirectory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from aihelp import cli 

class TestConfigManagement(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory to act as the user's home for config files
        self.temp_home_dir = tempfile.mkdtemp()
        self.mock_expanduser_patch = patch('os.path.expanduser', return_value=os.path.join(self.temp_home_dir, '.aihelp_config.json'))
        self.mock_expanduser = self.mock_expanduser_patch.start()

        # Store original cli constants to restore them later
        self.original_config_file = cli.CONFIG_FILE
        self.original_original_default_models = cli.ORIGINAL_DEFAULT_MODELS
        self.original_api_key_env_vars = cli.API_KEY_ENV_VARS
        self.original_supported_providers = cli.SUPPORTED_PROVIDERS
        self.original_dangerous_patterns = cli.ORIGINAL_DEFAULT_DANGEROUS_PATTERNS
        self.original_policy_mode = cli.DEFAULT_COMMAND_POLICY_MODE
        self.original_allowlist = cli.DEFAULT_COMMAND_ALLOWLIST
        self.original_blocklist = cli.DEFAULT_COMMAND_BLOCKLIST


        # Override cli module's globals for the duration of the test
        cli.CONFIG_FILE = os.path.join(self.temp_home_dir, '.aihelp_config.json')
        # Ensure cli.config is reset for each test by reloading defaults based on potentially mocked values
        cli.config = cli.load_config()


    def tearDown(self):
        self.mock_expanduser_patch.stop()
        shutil.rmtree(self.temp_home_dir)

        # Restore original cli constants
        cli.CONFIG_FILE = self.original_config_file
        cli.ORIGINAL_DEFAULT_MODELS = self.original_original_default_models
        cli.API_KEY_ENV_VARS = self.original_api_key_env_vars
        cli.SUPPORTED_PROVIDERS = self.original_supported_providers
        cli.ORIGINAL_DEFAULT_DANGEROUS_PATTERNS = self.original_dangerous_patterns
        cli.DEFAULT_COMMAND_POLICY_MODE = self.original_policy_mode
        cli.DEFAULT_COMMAND_ALLOWLIST = self.original_allowlist
        cli.DEFAULT_COMMAND_BLOCKLIST = self.original_blocklist
        
        # Reset cli.config to a clean state, important if tests modify it globally
        cli.config = cli.load_config() # This will now use original CONFIG_FILE path unless setUp overrides again
        if hasattr(cli, 'active_clients'): # Clear active clients if any were populated
            cli.active_clients = {}


    def test_load_config_non_existent(self):
        """Test loading config when no file exists; should create defaults."""
        # setUp already calls load_config, so cli.config should be populated with defaults
        self.assertIsNotNone(cli.config)
        self.assertEqual(cli.config['default_provider'], 'groq')
        self.assertIn('groq', cli.config['providers'])
        self.assertEqual(cli.config['providers']['groq']['default_model'], cli.ORIGINAL_DEFAULT_MODELS['groq'])
        self.assertEqual(cli.config['dangerous_command_patterns'], cli.ORIGINAL_DEFAULT_DANGEROUS_PATTERNS)
        self.assertEqual(cli.config['command_policy_mode'], cli.DEFAULT_COMMAND_POLICY_MODE)
        self.assertEqual(cli.config['command_allowlist'], cli.DEFAULT_COMMAND_ALLOWLIST)
        self.assertEqual(cli.config['command_blocklist'], cli.DEFAULT_COMMAND_BLOCKLIST)
        # Check if the file was actually created
        self.assertTrue(os.path.exists(cli.CONFIG_FILE))

    def test_save_and_load_config(self):
        """Test saving changes to config and reloading them."""
        # Modify some config values
        cli.config['default_provider'] = 'openai'
        cli.config['providers']['groq']['default_model'] = 'test_model_1'
        cli.config['providers']['openai']['default_model'] = 'test_model_2'
        new_pattern = r"test_dangerous_pattern"
        cli.config['dangerous_command_patterns'].append(new_pattern)
        cli.config['command_policy_mode'] = 'allow'
        cli.config['command_allowlist'].append('ls -l')
        
        cli.save_config(cli.config)
        
        # Create a new config object by loading from the saved file
        newly_loaded_config = cli.load_config()
        
        self.assertEqual(newly_loaded_config['default_provider'], 'openai')
        self.assertEqual(newly_loaded_config['providers']['groq']['default_model'], 'test_model_1')
        self.assertEqual(newly_loaded_config['providers']['openai']['default_model'], 'test_model_2')
        self.assertIn(new_pattern, newly_loaded_config['dangerous_command_patterns'])
        self.assertEqual(newly_loaded_config['command_policy_mode'], 'allow')
        self.assertIn('ls -l', newly_loaded_config['command_allowlist'])

    def test_load_config_partially_missing_provider_details(self):
        """Test loading a config where a provider is missing some new fields."""
        # Simulate an old config file that's missing, e.g., 'last_used_model' for openai
        partial_config_data = {
            "default_provider": "openai",
            "providers": {
                "groq": {
                    "api_key_env": "GROQ_API_KEY",
                    "default_model": "llama-3.1-8b-instant",
                    "last_used_model": "llama-3.1-8b-instant" 
                },
                "openai": { # Missing last_used_model
                    "api_key_env": "OPENAI_API_KEY",
                    "default_model": "gpt-3.5-turbo",
                }
            },
            "dangerous_command_patterns": [],
            "command_policy_mode": "none",
            "command_allowlist": [],
            "command_blocklist": [],
        }
        with open(cli.CONFIG_FILE, 'w') as f:
            json.dump(partial_config_data, f)
        
        loaded_config = cli.load_config()
        
        # Check that the missing field was added with default value
        self.assertIn('last_used_model', loaded_config['providers']['openai'])
        self.assertEqual(loaded_config['providers']['openai']['last_used_model'], cli.ORIGINAL_DEFAULT_MODELS['openai'])
        self.assertEqual(loaded_config['providers']['openai']['default_model'], 'gpt-3.5-turbo') # Existing value preserved

    def test_load_config_missing_new_provider(self):
        """Test loading a config when a new provider has been added to the tool."""
        # Simulate an old config file that's missing the 'anthropic' provider entirely
        old_config_data = {
            "default_provider": "groq",
            "providers": {
                "groq": {"default_model": "gemma-7b-it", "last_used_model":"gemma-7b-it", "api_key_env": "GROQ_API_KEY"},
                "openai": {"default_model": "gpt-4", "last_used_model":"gpt-4", "api_key_env": "OPENAI_API_KEY"}
            }
            # dangerous_command_patterns, policy settings etc., are also missing
        }
        with open(cli.CONFIG_FILE, 'w') as f:
            json.dump(old_config_data, f)

        loaded_config = cli.load_config()

        self.assertIn("google", loaded_config["providers"]) # Google should be added from defaults
        self.assertEqual(loaded_config["providers"]["google"]["default_model"], cli.ORIGINAL_DEFAULT_MODELS["google"])
        self.assertIn("anthropic", loaded_config["providers"]) # Anthropic should be added
        self.assertEqual(loaded_config["providers"]["anthropic"]["default_model"], cli.ORIGINAL_DEFAULT_MODELS["anthropic"])
        
        # Check that existing values were preserved
        self.assertEqual(loaded_config["providers"]["groq"]["default_model"], "gemma-7b-it")
        
        # Check that other new sections are also defaulted
        self.assertEqual(loaded_config["dangerous_command_patterns"], cli.ORIGINAL_DEFAULT_DANGEROUS_PATTERNS)
        self.assertEqual(loaded_config["command_policy_mode"], cli.DEFAULT_COMMAND_POLICY_MODE)
        self.assertTrue(os.path.exists(cli.CONFIG_FILE)) # Ensure file was created and saved

    def test_reset_model_for_provider(self):
        """Test resetting a model for a specific provider."""
        provider_to_test = "groq"
        # First, change the model from its original default
        changed_model = "changed-model-for-reset-test"
        cli.config["providers"][provider_to_test]["default_model"] = changed_model
        cli.save_config(cli.config)
        
        # Verify it's changed
        loaded_conf = cli.load_config()
        self.assertEqual(loaded_conf["providers"][provider_to_test]["default_model"], changed_model)
        
        # Now, simulate calling the reset logic (which is in main(), so we'll call parts of it)
        # In a real CLI test, we'd use subprocess or mock sys.argv and call main().
        # Here, we'll directly modify and save.
        cli.config["providers"][provider_to_test]["default_model"] = cli.ORIGINAL_DEFAULT_MODELS[provider_to_test]
        cli.save_config(cli.config)
        
        final_conf = cli.load_config()
        self.assertEqual(final_conf["providers"][provider_to_test]["default_model"], cli.ORIGINAL_DEFAULT_MODELS[provider_to_test])

    def test_api_key_env_names_persisted(self):
        """Ensure API key env var names are correctly loaded and not overridden by user config."""
        #load_config ensures API_KEY_ENV_VARS are used. Let's verify they are in the loaded config.
        loaded_config = cli.load_config()
        for provider, env_var_name in cli.API_KEY_ENV_VARS.items():
            self.assertEqual(loaded_config["providers"][provider]["api_key_env"], env_var_name)

        # Test that even if a user manually puts a wrong env var name in config, it's corrected by load_config
        bad_config_data = {
            "default_provider": "groq",
            "providers": {
                "groq": {
                    "api_key_env": "USER_SET_WRONG_GROQ_KEY_ENV", # User changed this
                    "default_model": "llama3",
                    "last_used_model": "llama3"
                }
            }
        }
        with open(cli.CONFIG_FILE, 'w') as f:
            json.dump(bad_config_data, f)
        
        corrected_config = cli.load_config()
        self.assertEqual(corrected_config["providers"]["groq"]["api_key_env"], cli.API_KEY_ENV_VARS["groq"])


class TestCLIArguments(unittest.TestCase):
    def setUp(self):
        self.temp_home_dir = tempfile.mkdtemp()
        # IMPORTANT: Patch os.path.expanduser BEFORE cli is imported or its constants are set at module level
        self.mock_expanduser_patch = patch('os.path.expanduser', return_value=os.path.join(self.temp_home_dir, '.aihelp_config.json'))
        self.mock_expanduser = self.mock_expanduser_patch.start()

        # Patch stdout to capture print statements from CLI functions
        self.mock_stdout_patch = patch('sys.stdout', new_callable=unittest.mock.StringIO)
        self.mock_stdout = self.mock_stdout_patch.start()
        
        # Patch stderr for error messages
        self.mock_stderr_patch = patch('sys.stderr', new_callable=unittest.mock.StringIO)
        self.mock_stderr = self.mock_stderr_patch.start()

        # Store and override CONFIG_FILE *after* expanduser is patched
        # This ensures cli.CONFIG_FILE is based on the mocked home dir
        self.original_config_file_val = cli.CONFIG_FILE
        cli.CONFIG_FILE = os.path.join(self.temp_home_dir, '.aihelp_config.json')
        
        # Ensure a default config is created for each test method if not existing
        # This reloads cli.config using the new cli.CONFIG_FILE path
        cli.config = cli.load_config() 
        cli.save_config(cli.config) # Save it so it exists for CLI commands

        # Mock os.environ for API keys
        self.mock_env_patch = patch.dict(os.environ, {
            "GROQ_API_KEY": "fake_groq_key",
            "OPENAI_API_KEY": "fake_openai_key",
            # Leave Google and Anthropic unset to test "Not Configured"
        }, clear=True) # clear=True ensures we start with a clean slate for os.environ
        self.mock_env = self.mock_env_patch.start()
        
        # Mock provider clients to prevent actual API calls
        # We patch the class in the module where it's *used* (aihelp.cli)
        self.mock_groq_provider_patch = patch('aihelp.cli.GroqProvider')
        self.mock_openai_provider_patch = patch('aihelp.cli.OpenAIProvider')
        self.mock_google_provider_patch = patch('aihelp.cli.GoogleProvider')
        self.mock_anthropic_provider_patch = patch('aihelp.cli.AnthropicProvider')

        self.MockGroqProviderClass = self.mock_groq_provider_patch.start()
        self.MockOpenAIProviderClass = self.mock_openai_provider_patch.start()
        self.MockGoogleProviderClass = self.mock_google_provider_patch.start()
        self.MockAnthropicProviderClass = self.mock_anthropic_provider_patch.start()

        # Configure mock instances for all provider classes
        for provider_name, MockProviderClass in {
            "groq": self.MockGroqProviderClass, 
            "openai": self.MockOpenAIProviderClass,
            "google": self.MockGoogleProviderClass,
            "anthropic": self.MockAnthropicProviderClass
        }.items():
            mock_instance = MagicMock()
            api_key_env_name = cli.API_KEY_ENV_VARS.get(provider_name)
            # is_configured should reflect whether the (mocked) API key is set in our mocked os.environ
            mock_instance.is_configured.return_value = bool(os.environ.get(api_key_env_name))
            mock_instance.get_models.return_value = [f"{provider_name}-model1", f"{provider_name}-model2"]
            mock_instance.get_completion.return_value = f"successful_completion_from_{provider_name}"
            MockProviderClass.return_value = mock_instance # When ProviderClass() is called, return this mock_instance

        # Clear active_clients at the start of each test that might use it
        cli.active_clients = {}


    def tearDown(self):
        self.mock_expanduser_patch.stop()
        self.mock_stdout_patch.stop()
        self.mock_stderr_patch.stop()
        self.mock_env_patch.stop()

        self.mock_groq_provider_patch.stop()
        self.mock_openai_provider_patch.stop()
        self.mock_google_provider_patch.stop()
        self.mock_anthropic_provider_patch.stop()

        shutil.rmtree(self.temp_home_dir)
        cli.CONFIG_FILE = self.original_config_file_val # Restore original CONFIG_FILE path
        # Important: reload config from the original path or a known state if other tests depend on it
        # For isolated tests, this might not be strictly necessary if setUp handles all overrides.
        cli.config = cli.load_config() 
        cli.active_clients = {}


    def run_cli_command(self, args_list):
        """Helper function to simulate running the CLI with arguments."""
        # Reset stdout/stderr buffers for each command run
        self.mock_stdout.truncate(0)
        self.mock_stdout.seek(0)
        self.mock_stderr.truncate(0)
        self.mock_stderr.seek(0)
        
        # Reset active_clients before each CLI command that might populate them
        cli.active_clients = {}

        with patch('sys.argv', ['aihelp'] + args_list):
            try:
                cli.main()
            except SystemExit as e: 
                return e.code 
        return 0 

    def test_list_providers(self):
        self.run_cli_command(['--list-providers'])
        output = self.mock_stdout.getvalue()
        self.assertIn("groq (Configured (API key found))", output)
        self.assertIn("openai (Configured (API key found))", output)
        self.assertIn("google (Not Configured (API key missing or invalid))", output)
        self.assertIn("anthropic (Not Configured (API key missing or invalid))", output)

    def test_list_models(self):
        self.run_cli_command(['--list-models', 'groq'])
        output = self.mock_stdout.getvalue()
        self.assertIn("groq-model1", output)
        self.assertIn("groq-model2", output)

    def test_set_default_provider(self):
        self.run_cli_command(['--set-default-provider', 'openai'])
        output = self.mock_stdout.getvalue()
        self.assertIn("Global default provider has been set to: openai", output)
        # cli.config is global; after cli.main() runs, it should be updated.
        # No need to call cli.load_config() here within the test if main() modifies it directly.
        self.assertEqual(cli.config['default_provider'], 'openai')
        # Verify persistence by actually loading from the temp file
        with open(cli.CONFIG_FILE, 'r') as f:
            persisted_config = json.load(f)
        self.assertEqual(persisted_config['default_provider'], 'openai')


    def test_show_model_default(self):
        # Default config has groq as default provider
        self.run_cli_command(['--show-model', 'groq'])
        output = self.mock_stdout.getvalue()
        # Use the ORIGINAL_DEFAULT_MODELS for assertion as it's the source of truth for defaults
        self.assertIn(f"Current default model for groq: {cli.ORIGINAL_DEFAULT_MODELS['groq']}", output)

    def test_set_model(self):
        self.run_cli_command(['--set-model', 'groq', 'new-groq-model'])
        output = self.mock_stdout.getvalue()
        self.assertIn("Default model for groq has been set to: new-groq-model", output)
        self.assertEqual(cli.config['providers']['groq']['default_model'], 'new-groq-model')
        with open(cli.CONFIG_FILE, 'r') as f:
            persisted_config = json.load(f)
        self.assertEqual(persisted_config['providers']['groq']['default_model'], 'new-groq-model')


    def test_reset_model_cli(self):
        # First, set a different model
        self.run_cli_command(['--set-model', 'openai', 'custom-openai-model'])
        self.mock_stdout.truncate(0); self.mock_stdout.seek(0) # Clear stdout
        # Now, reset it
        self.run_cli_command(['--reset-model', 'openai'])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Default model for openai has been reset to: {cli.ORIGINAL_DEFAULT_MODELS['openai']}", output)
        self.assertEqual(cli.config['providers']['openai']['default_model'], cli.ORIGINAL_DEFAULT_MODELS['openai'])

    # --- Dangerous Command Pattern Management CLI Tests ---
    def test_view_dangerous_patterns(self):
        self.run_cli_command(["--view-dangerous-patterns"])
        output = self.mock_stdout.getvalue()
        self.assertIn("Current dangerous command patterns (regex):", output)
        # Check a default pattern
        self.assertIn(cli.ORIGINAL_DEFAULT_DANGEROUS_PATTERNS[0], output)

    def test_add_dangerous_pattern(self):
        new_pattern = r"^test_new_pattern_cli\s+"
        self.run_cli_command(["--add-dangerous-pattern", new_pattern])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Added dangerous pattern: {new_pattern}", output)
        self.assertIn(new_pattern, cli.config["dangerous_command_patterns"])

    def test_remove_dangerous_pattern_by_string(self):
        pattern_to_remove = cli.config["dangerous_command_patterns"][0] # Get an existing one
        self.run_cli_command(["--remove-dangerous-pattern", pattern_to_remove])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Removed dangerous pattern: {pattern_to_remove}", output)
        self.assertNotIn(pattern_to_remove, cli.config["dangerous_command_patterns"])

    def test_remove_dangerous_pattern_by_index(self):
        unique_pattern = "unique_pattern_for_index_removal_cli"
        # Ensure the pattern list is reloaded or directly manipulated if cli.config is the source of truth
        cli.config["dangerous_command_patterns"].append(unique_pattern)
        cli.save_config(cli.config) # Save to make sure it's there before CLI tries to load/remove
        
        idx_to_remove = len(cli.load_config()["dangerous_command_patterns"]) # Get index from fresh load
        
        self.run_cli_command(["--remove-dangerous-pattern", str(idx_to_remove)])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Removed dangerous pattern (by index {idx_to_remove}): {unique_pattern}", output)
        self.assertNotIn(unique_pattern, cli.load_config()["dangerous_command_patterns"])

    # --- Command Policy Management CLI Tests ---
    def test_show_command_policy(self):
        self.run_cli_command(["--show-command-policy"])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Current command policy mode: {cli.DEFAULT_COMMAND_POLICY_MODE}", output)
        self.assertIn("Allowed commands:", output)
        self.assertIn("Blocked commands:", output)

    def test_set_command_policy(self):
        self.run_cli_command(["--set-command-policy", "allow"])
        output = self.mock_stdout.getvalue()
        self.assertIn("Command policy mode set to: allow", output)
        self.assertEqual(cli.config["command_policy_mode"], "allow")

    def test_add_allowed_command(self):
        cmd_to_add = "ls -la # cli"
        self.run_cli_command(["--add-allowed-command", cmd_to_add])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Added to command_allowlist: {cmd_to_add}", output)
        self.assertIn(cmd_to_add, cli.config["command_allowlist"])

    def test_remove_allowed_command_by_string(self):
        cmd_to_manage = "cat /etc/hosts # cli_allow_remove"
        cli.config["command_allowlist"].append(cmd_to_manage)
        cli.save_config(cli.config) # Save it first
        
        self.run_cli_command(["--remove-allowed-command", cmd_to_manage])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Removed from command_allowlist: {cmd_to_manage}", output)
        self.assertNotIn(cmd_to_manage, cli.load_config()["command_allowlist"])

    def test_add_blocked_command(self):
        cmd_to_add = "sudo reboot # cli_block_add"
        self.run_cli_command(["--add-blocked-command", cmd_to_add])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Added to command_blocklist: {cmd_to_add}", output)
        self.assertIn(cmd_to_add, cli.config["command_blocklist"])

    def test_remove_blocked_command_by_index(self):
        cmd_to_manage = "dangerous_cmd_for_blocklist_idx_cli"
        cli.config["command_blocklist"].append(cmd_to_manage)
        cli.save_config(cli.config)
        idx_to_remove = len(cli.load_config()["command_blocklist"])

        self.run_cli_command(["--remove-blocked-command", str(idx_to_remove)])
        output = self.mock_stdout.getvalue()
        self.assertIn(f"Removed from command_blocklist (by index {idx_to_remove}): {cmd_to_manage}", output)
        self.assertNotIn(cmd_to_manage, cli.load_config()["command_blocklist"])
        
    def test_basic_execution_flow_no_log(self):
        # This test will check if the main execution path is called.
        # We rely on mocked providers returning "successful_completion_from_..."
        # And we need to mock subprocess.run to prevent actual execution.
        with patch('aihelp.cli.subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.return_value = MagicMock(stdout="subprocess output", stderr="", returncode=0)
            
            # Use default provider (groq) and its default model
            self.run_cli_command(["list files"])
            output = self.mock_stdout.getvalue()

            self.assertIn("Interpreting: \"list files\"", output)
            self.assertIn(f"Using Provider: groq, Model: {cli.ORIGINAL_DEFAULT_MODELS['groq']}", output)
            self.assertNotIn("Logging to:", output) # Should not be present without --log
            self.assertIn("Executing: successful_completion_from_groq", output) # From mocked GroqProvider
            self.assertIn("Result:\nsubprocess output", output)
            mock_subprocess_run.assert_called_once_with("successful_completion_from_groq", capture_output=True, text=True, shell=True, check=True)

    def test_basic_execution_flow_with_log(self):
        with patch('aihelp.cli.subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.return_value = MagicMock(stdout="logged output", stderr="", returncode=0)
            
            self.run_cli_command(["--log", "show current directory"])
            output = self.mock_stdout.getvalue()
            log_file_path = os.path.join(self.temp_home_dir, '.aihelp_command_log.txt')

            self.assertIn("Interpreting: \"show current directory\"", output)
            self.assertIn(f"Logging to: {log_file_path}", output) # Should be present with --log
            self.assertIn("Executing: successful_completion_from_groq", output)
            self.assertIn("Result:\nlogged output", output)
            
            # Check log file content
            self.assertTrue(os.path.exists(log_file_path))
            with open(log_file_path, 'r') as f:
                log_content = f.read()
            self.assertIn("AIHelp Invoked.", log_content)
            self.assertIn("Input: 'show current directory'", log_content)
            self.assertIn("Final command for execution: successful_completion_from_groq", log_content)


# TODO:
# TestProviderLogic: For get_llm_provider_client, provider selection, get_llm_completion mocking.
# TestDangerousCommandHandling: For the dangerous command detection and confirmation flow.
# TestCommandPolicy: For the allowlist/blocklist logic.


class TestProviderLogic(unittest.TestCase):
    def setUp(self):
        self.temp_home_dir = tempfile.mkdtemp()
        self.mock_expanduser_patch = patch('os.path.expanduser', return_value=os.path.join(self.temp_home_dir, '.aihelp_config.json'))
        self.mock_expanduser = self.mock_expanduser_patch.start()

        self.original_config_file_val = cli.CONFIG_FILE
        cli.CONFIG_FILE = os.path.join(self.temp_home_dir, '.aihelp_config.json')
        cli.config = cli.load_config()
        cli.save_config(cli.config)
        cli.active_clients = {} # Reset active clients

        # Mock specific provider API clients (actual SDK clients)
        self.mock_groq_sdk_client_patch = patch('groq.Groq')
        self.MockGroqSdk = self.mock_groq_sdk_client_patch.start()
        
        # Mock os.environ
        self.mock_env_patch = patch.dict(os.environ, {}, clear=True)
        self.mock_env = self.mock_env_patch.start()


    def tearDown(self):
        self.mock_expanduser_patch.stop()
        self.mock_groq_sdk_client_patch.stop()
        self.mock_env_patch.stop()
        shutil.rmtree(self.temp_home_dir)
        cli.CONFIG_FILE = self.original_config_file_val
        cli.config = cli.load_config()
        cli.active_clients = {}


    def test_get_groq_provider_configured(self):
        os.environ[cli.API_KEY_ENV_VARS['groq']] = "fake_groq_key"
        provider = cli.get_llm_provider_client("groq")
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, cli.GroqProvider)
        self.assertTrue(provider.is_configured())
        self.MockGroqSdk.assert_called_once_with(api_key="fake_groq_key")

    def test_get_provider_not_configured(self):
        # No API key for google in os.environ by default in setUp
        provider = cli.get_llm_provider_client("google")
        self.assertIsNotNone(provider) # get_llm_provider_client returns an instance even if not configured
        self.assertIsInstance(provider, cli.GoogleProvider)
        self.assertFalse(provider.is_configured()) # is_configured() should be False

    @patch('aihelp.cli.GroqProvider') # Mock our wrapper class
    def test_get_llm_completion_calls_provider(self, MockGroqProvider):
        mock_provider_instance = MockGroqProvider.return_value
        mock_provider_instance.is_configured.return_value = True
        mock_provider_instance.get_completion.return_value = "mocked command"
        
        cli.active_clients['groq'] = mock_provider_instance # Pre-populate active_clients for simplicity

        result = cli.get_llm_completion(mock_provider_instance, "test prompt", "test_model")
        self.assertEqual(result, "mocked command")
        mock_provider_instance.get_completion.assert_called_once_with("test prompt", "test_model")

    def test_groq_provider_get_completion_success(self):
        os.environ[cli.API_KEY_ENV_VARS['groq']] = "fake_groq_key"
        
        mock_groq_sdk_instance = self.MockGroqSdk.return_value
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "ls -l from groq"
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_groq_sdk_instance.chat.completions.create.return_value = mock_response
        
        groq_provider = cli.GroqProvider() # This will init with the mocked Groq SDK
        self.assertTrue(groq_provider.is_configured())
        
        result = groq_provider.get_completion("list files", "llama-3.1-8b-instant")
        self.assertEqual(result, "ls -l from groq")
        mock_groq_sdk_instance.chat.completions.create.assert_called_once()


    def test_skeleton_providers_not_implemented(self):
        # OpenAI (assuming key is set for it to try)
        os.environ[cli.API_KEY_ENV_VARS['openai']] = "fake_openai_key"
        openai_provider = cli.OpenAIProvider()
        self.assertTrue(openai_provider.is_configured())
        # No need to mock OpenAI client as get_completion is hardcoded for skeleton
        self.assertIn("not yet fully implemented", openai_provider.get_completion("prompt", "gpt-4"))

        # Google
        os.environ[cli.API_KEY_ENV_VARS['google']] = "fake_google_key"
        google_provider = cli.GoogleProvider()
        self.assertTrue(google_provider.is_configured())
        self.assertIn("not yet fully implemented", google_provider.get_completion("prompt", "gemini-pro"))

        # Anthropic
        os.environ[cli.API_KEY_ENV_VARS['anthropic']] = "fake_anthropic_key"
        anthropic_provider = cli.AnthropicProvider()
        self.assertTrue(anthropic_provider.is_configured())
        self.assertIn("not yet fully implemented", anthropic_provider.get_completion("prompt", "claude-3"))


class TestDangerousCommandHandling(unittest.TestCase):
    def setUp(self):
        self.temp_home_dir = tempfile.mkdtemp()
        self.mock_expanduser_patch = patch('os.path.expanduser', return_value=os.path.join(self.temp_home_dir, '.aihelp_config.json'))
        self.mock_expanduser = self.mock_expanduser_patch.start()

        self.original_config_file_val = cli.CONFIG_FILE
        cli.CONFIG_FILE = os.path.join(self.temp_home_dir, '.aihelp_config.json')
        cli.config = cli.load_config() # Load default patterns
        cli.save_config(cli.config)
        cli.logging_enabled_globally = False # Disable logging for these specific tests unless overridden

        # Mock the confirmation function
        self.mock_confirm_patch = patch('aihelp.cli._confirm_dangerous_command_execution')
        self.mock_confirm = self.mock_confirm_patch.start()

        # Mock the actual execution function
        self.mock_execute_patch = patch('aihelp.cli._execute_validated_commands')
        self.mock_execute = self.mock_execute_patch.start()
        
        # Mock get_llm_completion to return a controlled command
        self.mock_get_llm_completion_patch = patch('aihelp.cli.get_llm_completion')
        self.mock_get_llm_completion = self.mock_get_llm_completion_patch.start()

        # Mock _validate_commands (syntax check) to always pass
        self.mock_validate_syntax_patch = patch('aihelp.cli._validate_commands') # was validate_bash_command
        self.mock_validate_syntax = self.mock_validate_syntax_patch.start()
        self.mock_validate_syntax.return_value = True # Assume syntax is always fine

        cli.active_clients = {}


    def tearDown(self):
        self.mock_expanduser_patch.stop()
        self.mock_confirm_patch.stop()
        self.mock_execute_patch.stop()
        self.mock_get_llm_completion_patch.stop()
        self.mock_validate_syntax_patch.stop()
        shutil.rmtree(self.temp_home_dir)
        cli.CONFIG_FILE = self.original_config_file_val
        cli.config = cli.load_config()
        cli.active_clients = {}


    def test_dangerous_command_triggers_confirmation(self):
        self.mock_get_llm_completion.return_value = "sudo rm -rf /"
        self.mock_confirm.return_value = False # User denies

        cli.interpret_and_execute("delete everything", "groq", "llama3", skip_danger_check_arg=False)
        
        self.mock_confirm.assert_called_once_with("sudo rm -rf /", r"sudo\s+rm\s+-rf\s+/\s*(?![\w./])")
        self.mock_execute.assert_not_called()

    def test_dangerous_command_confirmation_denied(self):
        self.mock_get_llm_completion.return_value = "mkfs.ext4 /dev/sda"
        self.mock_confirm.return_value = False # User denies
        
        cli.interpret_and_execute("format disk", "groq", "llama3", skip_danger_check_arg=False)
        self.mock_confirm.assert_called_once()
        self.mock_execute.assert_not_called()

    def test_dangerous_command_confirmation_accepted(self):
        self.mock_get_llm_completion.return_value = "dd if=/dev/zero of=/dev/sdb"
        self.mock_confirm.return_value = True # User accepts
        
        cli.interpret_and_execute("wipe disk sdb", "groq", "llama3", skip_danger_check_arg=False)
        self.mock_confirm.assert_called_once()
        self.mock_execute.assert_called_once_with("dd if=/dev/zero of=/dev/sdb")

    def test_force_bypasses_confirmation(self):
        self.mock_get_llm_completion.return_value = "sudo rm -rf /"
        
        cli.interpret_and_execute("delete all with force", "groq", "llama3", skip_danger_check_arg=True)
        self.mock_confirm.assert_not_called()
        self.mock_execute.assert_called_once_with("sudo rm -rf /")

    def test_user_added_dangerous_pattern_triggers_confirmation(self):
        custom_pattern = r"my_custom_dangerous_command"
        cli.config["dangerous_command_patterns"].append(custom_pattern)
        cli.save_config(cli.config) # Save the updated config with the new pattern
        
        self.mock_get_llm_completion.return_value = "do my_custom_dangerous_command now"
        self.mock_confirm.return_value = False # User denies
        
        # Reload config within interpret_and_execute or ensure it uses the modified global cli.config
        # cli.interpret_and_execute reloads its own view of config if not passed one,
        # but it uses the global cli.config. So, modifying cli.config directly should work.
        
        cli.interpret_and_execute("custom danger", "groq", "llama3", skip_danger_check_arg=False)
        self.mock_confirm.assert_called_once_with("do my_custom_dangerous_command now", custom_pattern)
        self.mock_execute.assert_not_called()

    def test_safe_command_no_confirmation(self):
        self.mock_get_llm_completion.return_value = "ls -la"
        cli.interpret_and_execute("list files safely", "groq", "llama3", skip_danger_check_arg=False)
        self.mock_confirm.assert_not_called()
        self.mock_execute.assert_called_once_with("ls -la")


class TestCommandPolicy(unittest.TestCase):
    def setUp(self):
        self.temp_home_dir = tempfile.mkdtemp()
        self.mock_expanduser_patch = patch('os.path.expanduser', return_value=os.path.join(self.temp_home_dir, '.aihelp_config.json'))
        self.mock_expanduser = self.mock_expanduser_patch.start()

        self.original_config_file_val = cli.CONFIG_FILE
        cli.CONFIG_FILE = os.path.join(self.temp_home_dir, '.aihelp_config.json')
        cli.config = cli.load_config() # Load fresh config
        cli.logging_enabled_globally = False
        cli.active_clients = {}

    def tearDown(self):
        self.mock_expanduser_patch.stop()
        shutil.rmtree(self.temp_home_dir)
        cli.CONFIG_FILE = self.original_config_file_val
        cli.config = cli.load_config() # Reset to original
        cli.active_clients = {}

    def test_policy_mode_none(self):
        cli.config["command_policy_mode"] = "none"
        self.assertTrue(cli._check_command_policy("any command"))

    def test_policy_mode_allow_passes(self):
        cli.config["command_policy_mode"] = "allow"
        cli.config["command_allowlist"] = ["ls -l", "cat file.txt"]
        self.assertTrue(cli._check_command_policy("ls -l"))
        self.assertTrue(cli._check_command_policy("ls -l && cat file.txt"))

    def test_policy_mode_allow_fails(self):
        cli.config["command_policy_mode"] = "allow"
        cli.config["command_allowlist"] = ["ls -l"]
        self.assertFalse(cli._check_command_policy("cat file.txt"))
        self.assertFalse(cli._check_command_policy("ls -l && cat file.txt")) # cat file.txt is not allowed

    def test_policy_mode_allow_empty_list_fails(self):
        cli.config["command_policy_mode"] = "allow"
        cli.config["command_allowlist"] = []
        self.assertFalse(cli._check_command_policy("any command"))

    def test_policy_mode_allow_prefix_match(self):
        cli.config["command_policy_mode"] = "allow"
        cli.config["command_allowlist"] = ["git *", "docker ps"]
        self.assertTrue(cli._check_command_policy("git status"))
        self.assertTrue(cli._check_command_policy("git commit -m 'test'"))
        self.assertTrue(cli._check_command_policy("docker ps"))
        self.assertFalse(cli._check_command_policy("docker images")) # Not covered by "docker ps"
        self.assertFalse(cli._check_command_policy("gitk")) # Not covered by "git *" if we want exact command after prefix

    def test_policy_mode_block_fails(self):
        cli.config["command_policy_mode"] = "block"
        cli.config["command_blocklist"] = ["rm -rf", "sudo *"]
        self.assertFalse(cli._check_command_policy("rm -rf /tmp"))
        self.assertFalse(cli._check_command_policy("sudo reboot"))
        self.assertFalse(cli._check_command_policy("ls -l && sudo poweroff")) # sudo poweroff is blocked

    def test_policy_mode_block_passes(self):
        cli.config["command_policy_mode"] = "block"
        cli.config["command_blocklist"] = ["rm -rf"]
        self.assertTrue(cli._check_command_policy("ls -l"))

    def test_policy_mode_block_prefix_match(self):
        cli.config["command_policy_mode"] = "block"
        cli.config["command_blocklist"] = ["sudo *", "docker stop *"]
        self.assertFalse(cli._check_command_policy("sudo apt update"))
        self.assertFalse(cli._check_command_policy("docker stop my_container"))
        self.assertTrue(cli._check_command_policy("docker ps"))
        self.assertTrue(cli._check_command_policy("git status"))

    def test_policy_multi_command_allow_pass_and_fail(self):
        cli.config["command_policy_mode"] = "allow"
        cli.config["command_allowlist"] = ["echo 'hello'", "ls"]
        self.assertTrue(cli._check_command_policy("echo 'hello' && ls"))
        self.assertTrue(cli._check_command_policy("ls; echo 'hello'"))
        self.assertFalse(cli._check_command_policy("echo 'hello' && pwd")) # pwd not allowed
        self.assertFalse(cli._check_command_policy("cat file ; ls")) # cat file not allowed

    def test_policy_multi_command_block_fail(self):
        cli.config["command_policy_mode"] = "block"
        cli.config["command_blocklist"] = ["pwd"]
        self.assertFalse(cli._check_command_policy("echo 'hello' && pwd"))
        self.assertTrue(cli._check_command_policy("echo 'hello' && ls"))


# Placeholder for TestExecutionFlow if needed, many aspects covered by TestCLIArguments basic execution.

if __name__ == '__main__':
    unittest.main()
