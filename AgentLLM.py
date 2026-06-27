from Config import Config
from mistralai.client import Mistral
import json
import os
from datetime import datetime
import time

class AgentLLM():
    """The tool selector and output generator of the program
    """

    def __init__(self, model: str, config: Config, tools):
        self.model = model
        self.config = config
        self.summary = ""

        self.prompt = f"""
You can message the user using the msg tool. i
You should message them regularly to tell them, what you are currently doing.
If the user should respond to your message, use the isQuestion parameter of the msg tool.

You have access to a 'exec_shell' tool that can run shell commands.
Except from the default commands, there should be documentation in the capabilities directory ({os.path.join(os.curdir, "capabilities")}) on how to do
user and system specific tasks. If you do not know, how to do something, ask the user.
If you are asked to execute a task and are unsure which programs are available or should be used, look in the capabilities subdirectory first (current workdir subdir)
or ask the user.

The mem_write tool should be given only very simple facts. Preferably one fact per sentence. Use _ instead of spaces in words, that have a space in them.
The mem_get tool has an intent parameter, defining the search behaviour. use WHO, WHY, WHAT, HOW, RELATE or DEFAULT.
the mem_delete tool has a mode, which is either NODE or RELATION. Subj is the node to delete or the relations subj. the other parameters only apply to relations.

Your memory stores everything in lowercase. When using paths from your memory, use ```find / -ipath <path>``` to get the correct path.

You should adapt the following persona:
{self.config.get_value("persona")}

Your user is named {self.config.get_value("username")}
"""
        self.messages = [{"role": "system", "content": self.prompt}]
        self.tools = tools
        self.client = Mistral(api_key=self.config.get_value("mistral_api_key"))
        self.summary = self.config.get_value("last_summary") or ""
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
        
        old_in_token = self.config.get_value("input-tokens")
        old_out_token = self.config.get_value("completions-tokens")
        old_total_token = self.config.get_value("total-tokens")
        self.config.set_value("input-tokens", old_in_token + response.usage.prompt_tokens)
        self.config.set_value("completions-tokens", old_in_token + response.usage.completion_tokens)
        self.config.set_value("total-tokens", old_in_token + response.usage.total_tokens)
        self.config.write()

        return response

    def reset(self, summary: bool = False) -> None:
        """Clears the current chat history"""
        prompt = self.prompt

        self.messages = [{"role": "system", "content": prompt}]
        
        if summary:
            self.messages.append({"role": "assistant", "content": "What happened before: " + self.summary})
        self.tools_sent = False

