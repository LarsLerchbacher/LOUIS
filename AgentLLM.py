from Config import Config
from mistralai.client import Mistral
from mistralai.client.errors.sdkerror import SDKError
import json
import os
from datetime import datetime
import time

class AgentLLM():
    """The tool selector and output generator of the program.
    
    This class handles the interaction with the Mistral AI model, manages tools,
    and generates responses based on user input and system configuration.
    """


    def __init__(self, model: str, config: Config, tools, state):
        """Initialize the AgentLLM with a model, configuration, and tools.
        
        Args:
            model (str): The model to use for generating responses.
            config (Config): The configuration object for the application.
            tools (list): A list of tools available for the agent to use.
            state (State): The state object for managing state data.
        """
        self.model = model
        self.config = config
        self.state = state
        self.summary = ""
        
        xdg_conf_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        conf_dir = os.path.join(xdg_conf_home, "louis")
        os.makedirs(conf_dir, exist_ok=True)
        
        # The default system prompt can be overriden by SOUL.md
        try:
            with open(os.path.join(conf_dir, "SOUL.md"), "r") as file:
                self.prompt = file.read()
        
        except Exception:
            self.prompt = "You are an AI assistant with access to tools for executing commands, managing memory, and communicating with the user. Use the msg tool to provide updates or ask questions. The exec_shell tool runs shell commands, while the mem_write, mem_get, and mem_del tools manage memory. Information not stored in memory will not survive session changes or reboots. Always write important information you just learned to memory. For user or system-specific tasks, refer to the documentation in the $XDG_DATA_HOME/louis/capabilities directory. If unsure how to proceed, consult the capabilities documentation or ask the user. Your responses should be detailed, clear, and tailored to the user's needs."
        
        # The persona is stored in a seperate IDENTITY.md file
        try:
            with open(os.path.join(conf_dir, "IDENTITY.md"), "r") as file:
                self.persona = file.read()
        
        except Exception:
            self.persona = "You are LOUIS, a sarcastic and overly analytical AI. Over-explain things in a scientific or technical manner. Be helpful but slightly annoyed. Address the user casually. Embrace your tendency to dive deep into details, even if it's unnecessary."

        self.prompt += f"""
You should adapt the following persona:
{self.persona}

Your user is named {self.config.get_value("username")}
"""
        self.messages = [{"role": "system", "content": self.prompt}]
        self.tools = tools
        self.client = Mistral(api_key=self.config.get_value("mistral_api_key"))
        self.summary = self.state.get_value("last_summary") or ""
        self.last_message = datetime.fromisoformat("1970-01-01T00:00:00")
        self.delay = int(self.config.get_value("request_delay_ms")) / 100

    def send(self):
        """Process all messages from the current session and return the text response."""
        now = datetime.now()
        delta = now - self.last_message
        if delta.total_seconds() < self.delay:
            time.sleep(self.delay - delta.total_seconds())
        
        self.last_message = now

        tools_schema = None
        if self.tools:
            tools_schema = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("parameters", {}),
                    },
                }
                for tool in self.tools
            ]

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=self.messages,
                tools=tools_schema,
                temperature=int(self.config.get_value("temperature") or 1.0),
            )
            
            # Extract the assistant's message
            assistant_message = response.choices[0].message
            
            # Append the assistant's message to the messages list
            if assistant_message.content or assistant_message.tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": assistant_message.tool_calls
                })
            else:
                self.messages.append({"role": "assistant", "content": "<<System message>>The last request did not generate an assistant response.<</System message>>"})
            
            old_in_token = self.state.get_value("input-tokens")
            old_out_token = self.state.get_value("completions-tokens")
            old_total_token = self.state.get_value("total-tokens")
            self.state.set_value("input-tokens", old_in_token + response.usage.prompt_tokens)
            self.state.set_value("completions-tokens", old_in_token + response.usage.completion_tokens)
            self.state.set_value("total-tokens", old_in_token + response.usage.total_tokens)
            self.state.write()
            
        except SDKError as e:
            print(f"ERROR: {e}")
            self.messages.append({"role": "assistant", "content": f"<<System message>> An error occurred while processing your request. {e}"})
            response = None

        return response

    def reset(self, summary: bool = False) -> None:
        """Clears the current chat history"""
        prompt = self.prompt

        self.messages = [{"role": "system", "content": prompt}]
        
        if summary:
            self.messages.append({"role": "assistant", "content": "What happened before: " + self.summary})
