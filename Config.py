import json
import logging
import os

class Config():
        def __init__(self, logger: logging.Logger):
                self.logger = logger
                self.data = {}

        def load(self) -> int:
                try:
                        with open("config.json", mode="r+") as file:
                                data = file.read()
                        self.data = json.loads(data)
                        return 0
                except FileNotFoundError:
                        self.logger.error(f"Configuration file not found at {os.path.join(os.curdir, 'config.json')}")
                        return -1
                except:
                        self.logger.error("Error parsing configuration.")
                        return -1
        
        def write(self) -> None:
                with open("config.json", mode="w") as file:
                        file.write(json.dumps(self.data))
        
        def get_value(self, key: str) -> str:
                try:
                        return self.data[key]
                except KeyError:
                        return None
        
        def set_value(self, key: str, value: str|int) -> None:
                self.data[key] = value
                