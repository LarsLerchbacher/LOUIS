from Config import Config
from mistralai.client import Mistral 
import json

class AgentLLM():
    """The tool selector and output generator of the program
    """

    def __init__(self, model: str, config: Config, tools):
        self.model = model
        self.config = config
        self.prompt = f"""
You are the tool and communication interface of an AI agent.
You will receive a list of usable tools, as well as all messages up to this point. 
You can message the user using the message tool. You should message them regularly to tell them, what you are currently doing.

Your execution loop is as follows (this is handled by the program, not you):
1. You receive user input
2. You select a tool to execute (messaging the user is a tool too). If no tool is executed, go to step 6
3. The tool gets executed
4. You get the results
5. Go back to step 2
6. End turn and wait for new message

You should adapt the following persona:
{self.config.get_value("persona")}
"""
        self.messages = [{"role": "system", "content": self.prompt}]
        self.tools = tools
        self.client = Mistral(api_key=self.config.get_value("mistral_api_key"))

    def send(self, message: str):
        """Send a message to the LLM and return the text response."""
        self.messages.append({"role": "user", "content": message})

        # Define tools if provided
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
            temperature=0.0,
        )
        
        # Extract the assistant's message
        assistant_message = response.choices[0].message

        # Append the assistant's message to the messages list
        self.messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": assistant_message.tool_calls
        })

        return response

    def reset(self) -> None:
        """Clears the current chat history"""
        self.messages = [{"role": "system", "content": self.prompt}]

