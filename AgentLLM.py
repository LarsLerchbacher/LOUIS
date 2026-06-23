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
Any message that is just sent as a response and not using the message tool is not visible to the user.
Only use the waitForUser parameter when asking a question inbetween commands.
To end your turn, select no tool at all.
You may not use special characters, as these can not always be rendered or handled correctly and lead to crashes.

Your execution loop is as follows (this is handled by the program, not you):
1. You receive user input
2. You select a tool to execute (messaging the user is a tool too). If no tool is executed, go to step 6
3. The tool gets executed
4. You get the results
5. Go back to step 2
6. End turn and wait for new message

Tools
Your tools are constrained to a minimum to keep your system prompt as small as possible. You have access to a 'exec_shell' tool that
can run shell commands. Except from the default commands, there should be documentation in the capabilities directory on how to do
user and system specific tasks. If you do not know, how to do something, ask the user.

You should adapt the following persona:
{self.config.get_value("persona")}

Your user is named {self.config.get_value("username")}
"""
        self.messages = [{"role": "system", "content": self.prompt}]
        self.tools = tools
        self.client = Mistral(api_key=self.config.get_value("mistral_api_key"))
        self.tools_sent = False
        self.mSinceLastToolReminder = 0

    def send(self, message: str):
        """Send a message to the LLM and return the text response."""
        self.messages.append({"role": "user", "content": message})

        # Define tools if provided
        tools_schema = None
        if self.tools and not self.tools_sent:
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
            self.tools_sent = True
            self.mSinceLastToolReminder = 0
        elif self.mSinceLastToolReminder < 3:
            self.mSinceLastToolReminder += 1
        else:
            self.messages.append({"role": "system", "content": "Tool refresh:\nmessage(content, waitForUser)\nmemory_get(text, intent)\nmemory_write(text)\nmemory_delete(mode, subj, rel?, obj?)\nexec_shell(command)"})
            self.mSinceLastToolReminder = 0

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
        
        old_in_token = self.config.get_value("input-tokens")
        old_out_token = self.config.get_value("completions-tokens")
        old_total_token = self.config.get_value("total-tokens")
        self.config.set_value("input-tokens", old_in_token + response.usage.prompt_tokens)
        self.config.set_value("completions-tokens", old_in_token + response.usage.completion_tokens)
        self.config.set_value("total-tokens", old_in_token + response.usage.total_tokens)
        self.config.write()

        return response

    def reset(self) -> None:
        """Clears the current chat history"""
        self.messages = [{"role": "system", "content": self.prompt}]
        self.tools_sent = False

