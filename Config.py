"""
	This file is part of LOUIS
	LOUIS is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
	LOUIS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details
	
	You should have received a copy of the GNU Affero General Public License along with LOUIS. If not, see <https://www.gnu.org/licenses/>.
"""
 
import json
import logging
import os

class Config():
        """Manages configuration settings for the application.

        This class handles loading, saving, and managing configuration data
        stored in a JSON file.
        """
        def __init__(self, logger: logging.Logger):
                """Initialize the Config class with a logger.
                
                Args:
                    logger (logging.Logger): The logger for logging messages.
                """
                self.logger = logger
                self.data = {}

        def load(self) -> int:
                """Load configuration data from the config file.
                
                Returns:
                    int: 0 on success, -1 on failure.
                """
                try:
                        xdg_conf_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
                        conf_dir = os.path.join(xdg_conf_home, "louis")
                        os.makedirs(conf_dir, exist_ok=True)

                        with open(os.path.join(conf_dir, "config.json"), mode="r+") as file:
                                data = file.read()
                        self.data = json.loads(data)
                        return 0
                except FileNotFoundError:
                        self.logger.error(f"Configuration file not found at {os.path.join(os.curdir, 'config.json')}")
                        return -1
                except Exception as e:
                        self.logger.error(f"Error parsing configuration: {e}")
                        return -1
                
        def write(self) -> None:
                """Write configuration data to the config file."""
                xdg_conf_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
                conf_dir = os.path.join(xdg_conf_home, "louis")
                os.makedirs(conf_dir, exist_ok=True)

                with open(os.path.join(conf_dir, "config.json"), mode="w") as file:
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
                