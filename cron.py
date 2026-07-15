import requests
import json
import logging
from Config import Config

class CronManager:
    """Manages automated prompts using OpenWebUI's automations API.
    
    This class handles the creation, updating, deletion, and execution of automated prompts.
    """
    def __init__(self, logger: logging.Logger, config: Config):
        """Initialize the CronManager with a logger and configuration.
        
        Args:
            logger (logging.Logger): The logger for logging messages.
            config (Config): The configuration object for the application.
        """
        self.logger = logger
        self.config = config
        self.ca_cert = self.config.get_value("openwebui_ca_cert")
        self.initialize() 
    
    def initialize(self):
        """Initialize the CronManager with the base URL and token."""
        self.logger.info("Initializing CronManager...")
        self.base_url = str(self.config.get_value("openwebui_url")) + "/api/v1/automations"
        self.token = self.config.get_value('openwebui_token')
        if not self.token:
            self.logger.error("Could not load Open WebUI token from config. Please make sure to include it in 'openwebui_token'.")
            quit(1)

    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def list_automations(self, page=1):
        url = f"{self.base_url}/list?page={page}"
        print(f"Listing automations from: {url}")
        try:
            response = requests.get(url, headers=self._get_headers(), verify=self.ca_cert)
        except Exception as e:
            print(e)
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        if response.status_code != 200:
            raise Exception(f"Failed to list automations: {response.text}")
        return response.json()

    def create_automation(self, name, prompt, model_id, rrule, is_active=True):
        url = f"{self.base_url}/create"
        data = {
            "name": name,
            "data": {
                "prompt": prompt,
                "model_id": model_id,
                "rrule": f"RRULE:{rrule}"
            },
            "is_active": is_active
        }
        response = requests.post(url, headers=self._get_headers(), data=json.dumps(data), verify=self.ca_cert)
        if response.status_code != 200:
            raise Exception(f"Failed to create automation: {response.text}")
        return response.json()

    def update_automation(self, automation_id, name, prompt, model_id, rrule, is_active=True):
        url = f"{self.base_url}/{automation_id}/update"
        data = {
            "name": name,
            "data": {
                "prompt": prompt,
                "model_id": model_id,
                "rrule": f"RRULE:{rrule}"
            },
            "is_active": is_active
        }
        response = requests.post(url, headers=self._get_headers(), data=json.dumps(data), verify=self.ca_cert)
        if response.status_code != 200:
            raise Exception(f"Failed to update automation: {response.text}")
        return response.json()

    def run_automation(self, automation_id):
        url = f"{self.base_url}/{automation_id}/run"
        response = requests.post(url, headers=self._get_headers(), verify=self.ca_cert)
        if response.status_code != 200:
            raise Exception(f"Failed to run automation: {response.text}")
        return response.json()

    def delete_automation(self, automation_id):
        url = f"{self.base_url}/{automation_id}/delete"
        response = requests.delete(url, headers=self._get_headers(), verify=self.ca_cert)
        if response.status_code != 200:
            raise Exception(f"Failed to delete automation: {response.text}")
        return response.json()
