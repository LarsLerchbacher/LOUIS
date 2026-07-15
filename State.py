import json
import logging
import os

class State():
        """Manages state data for the application.

        This class handles loading, saving, and managing state data
        stored in a JSON file in the XDG_STATE_HOME directory.
        """
        def __init__(self, logger: logging.Logger):
                """Initialize the State class with a logger.
                
                Args:
                    logger (logging.Logger): The logger for logging messages.
                """
                self.logger = logger
                self.data = {}

        def load(self) -> int:
                """Load state data from the state file.
                
                Returns:
                    int: 0 on success, -1 on failure.
                """
                try:
                        xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
                        state_dir = os.path.join(xdg_state_home, "louis")
                        os.makedirs(state_dir, exist_ok=True)

                        with open(os.path.join(state_dir, "state.json"), mode="r+") as file:
                                data = file.read()
                        self.data = json.loads(data)
                        return 0
                except FileNotFoundError:
                        self.logger.info("State file not found. Creating a new one.")
                        self.data = {
                            "last_summary": "",
                            "message-calls": 0,
                            "memory_get-calls": 0,
                            "memory_write-calls": 0,
                            "memory_delete-calls": 0,
                            "exec_shell-calls": 0,
                            "input-tokens": 0,
                            "completions-tokens": 0,
                            "total-tokens": 0
                        }
                        self.write()
                        return 0
                except Exception as e:
                        self.logger.error(f"Error parsing state: {e}")
                        return -1
                
        def write(self) -> None:
                """Write state data to the state file."""
                xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
                state_dir = os.path.join(xdg_state_home, "louis")
                os.makedirs(state_dir, exist_ok=True)

                with open(os.path.join(state_dir, "state.json"), mode="w") as file:
                        file.write(json.dumps(self.data))
                
        def get_value(self, key: str) -> str:
                """Get the value associated with the specified key.
                
                Args:
                    key (str): The key to retrieve the value for.
                    
                Returns:
                    str: The value associated with the key, or None if the key does not exist.
                """
                try:
                    return self.data[key]
                except KeyError:
                        return None
                
        def set_value(self, key: str, value: str|int) -> None:
                """Set the value for the specified key.
                
                Args:
                    key (str): The key to set the value for.
                    value (str|int): The value to associate with the key.
                """
                self.data[key] = value