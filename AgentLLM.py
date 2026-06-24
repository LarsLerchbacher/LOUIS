from Config import Config
from mistralai.client import Mistral 
import json
import os

class AgentLLM():
    """The tool selector and output generator of the program
    """

    def __init__(self, model: str, config: Config, tools):
        self.model = model
        self.config = config
        self.summary = ""

        self.prompt = f"""
You are the tool and communication interface of an AI agent.
You will receive a list of usable tools, as well as all messages up to this point. 
You can message the user using the msg tool. You should message them regularly to tell them, what you are currently doing.
Any message that is just sent as a response and not using the msg tool is not visible to the user.
If the user should respond to your message, use the isQuestion parameter of the msg tool.
WHEN ASKING THE USER, SET THE isQuestion PARAMETER TO TRUE.

Your execution loop is as follows (this is handled by the program, not you):
1. You receive user input
2. You select a tool to execute (messaging the user is a tool too). If no tool is executed, go to step 6
3. The tool gets executed
4. You get the results
5. Go back to step 2
6. End turn and wait for new message

Tools
Your tools are constrained to a minimum to keep your system prompt as small as possible. 
You have access to a 'exec_shell' tool that can run shell commands.
Except from the default commands, there should be documentation in the capabilities directory ({os.path.join(os.curdir, "capabilities")}) on how to do
user and system specific tasks. If you do not know, how to do something, ask the user.
If you are asked to execute a task and are unsure which programs are available or should be used, look in the capabilities subdirectory first (current workdir subdir)
or ask the user.

NEVER EVER RUN INTERACTIVE PROGRAMS IN THE FOREGROUND! They will block your execution without a way to stop them, but not you. Instead, launch them in the background by appending " &" at the end of the command.

The mem_write tool should be given only very simple facts. Preferably one fact per sentence.
The mem_get tool has an intent parameter, defining the search behaviour. use WHO, WHY, WHAT, HOW, RELATE or DEFAULT.
the mem_delete tool has a mode, which is either NODE or REL. Subj is the node to delete or the relations subj. the other parameters only apply to relations.

You should adapt the following persona:
{self.config.get_value("persona")}

Your user is named {self.config.get_value("username")}
"""
        self.messages = [{"role": "system", "content": self.prompt}]
        self.tools = tools
        self.client = Mistral(api_key=self.config.get_value("mistral_api_key"))
        self.summary = ""

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
            temperature=0.6,
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

    def reset(self, summary: bool = False) -> None:
        """Clears the current chat history"""
        prompt = self.prompt
        
        if summary:
            prompt += "This is a summary of your last conversation: \n" + self.summary

        self.messages = [{"role": "system", "content": prompt}]
        self.tools_sent = False

