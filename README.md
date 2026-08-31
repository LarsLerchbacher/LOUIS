L.O.U.I.S
=========

```text
██╗         ██████╗    ██╗   ██╗   ██╗   ███████╗   
██║        ██╔═══██╗   ██║   ██║   ██║   ██╔════╝   
██║        ██║   ██║   ██║   ██║   ██║   ███████╗   
██║        ██║   ██║   ██║   ██║   ██║   ╚════██║   
███████╗██╗╚██████╔╝██╗╚██████╔╝██╗██║██╗███████║██╗
╚══════╝╚═╝ ╚═════╝ ╚═╝ ╚═════╝ ╚═╝╚═╝╚═╝╚══════╝╚═╝
    Lars Optimized Useful Intelligent System
```

![A very annoyed owl in a labcoat, holding a cup of coffee (the personality of LOUIS)](LOUIS.png)



> [!WARNING]  
> LOUIS is an experimental personal project and is currently under active development. Some features may be unstable.

## What is LOUIS
LOUIS is an experimental AI agent and API built around a custom long-term memory system based on a semantic network and spreading activation. It is primarily designed to be used as a backend for [Open WebUI](https://docs.openwebui.com/), with an additional CLI for direct interaction.

## Memory

Instead of representing long-term memory as a collection of text snippets, LOUIS stores information as a semantic network consisting of concepts and weighted relations. Queries activate relevant nodes, and activation propagates through the network to retrieve related information. This also allows it to do some basic reasoning at memory level (e.g. `Socrates is_a human`, `human has_property mortal` can lead to `Socrates has_property mortal`).

## How can I use LOUIS?

You can download it, create a python virtual environment and install the requirements from `requirements.txt`.
Edit the default config.json file, add your own API key (the included one is invalid, if you're wondering, uploaded it by mistake), set your name, the name of the AI and adjust its personality prompt.

### Quick start with terminal chat
Then just run `python main.py chat` to start chatting with your own agent from your terminal. The terminal chat has a /reset command, which summarizes the current session and starts a new one.
The summary is added to its system prompt, so it knows what happened in the last session.
There is also /new, which starts a clean new session. 
To exit it, enter /exit<br>


### Intended use
The intended use of LOUIS is combined with Open WebUI. This adds a lot of additional features, like chats, voice conversations and scheduled prompts.
For this to work, you need to run an Open WebUI server and add an OpenAI endpoint, pointing to the IP address of the LOUIS server at port 8000.


### Memory
The LOUIS CLI also has support for manual memory interactions, to view or edit the agents memory. This is available with the graph command and the following subcommands:

`python main.py graph show` opens the graph view in the browser (is updated every write, just reload the page)<br>
`python main.py graph query` Queries the memory for a term. You will get exactly what LOUIS sees too, when querying his memory.<br>
`python main.py graph write` Writes a fact to memory. State the fact in VERY simple language. The extractor LLM easily misinterprets stuff, so try to stick to one fact per sentence. Facts should be rephrasable to the form: `subj --- relation --> object`. This is what the graph stores internally.


## What makes LOUIS special

Aside from the fact, that it uses a semantic network as its main memory system, LOUIS also features a custom interaction loop:

1. The user sends input
2. The agent decides which tool to use. If none is selected go to step 6
3. The tool gets executed.
4. The results get added to the messages
5. Go to step 2
6. The user is prompted for their next message

The interaction loop itself is relatively straightforward. What is more unusual is the set of tools available to the agent:

- msg: The message tool allows the agent to communicate with the user. As it is a tool itself, it can be used between other tool calls, enabling the agent to give regular status updates. It can also be used to ask the user a question and pause the execution until an answer is received. This allows it to ask for clarification instead of guessing.
- mem_get: Queries the memory graph
- mem_write: Writes facts to the memory
- mem_delete: Delete wrong/old nodes and relations for memory
- exec: Execute a shell command. Commands that take longer than 30 seconds are executed in the background. Only one command can be run at a time, but the agent can choose to overwrite the current task with a new one, in case it runs a non-terminating command.
- checkProc: Get the output of the last exec command


## Capabilities

LOUIS uses a different approach than OpenClaw, when it comes to adding features.

We have 'capabilities', which are markdown files, just like Skills in OpenClaw, containing usage information about different user- or system specific tools and workflows.
The agent is instructed to look through the available capabilities before guessing how to execute an action.

Capabilities are **markdown files on disk** and **are only injected into context**, when the user's message contains their name. The agent can also read them freely to find
the correct tool. e.g. `spotify.md` gets injected when the prompt contains `spotify`.

This is the major difference to OpenClaw, which exposes all available skills and tools every turn, regardless of the task. Our approach reduces token cost **immensely**.


## History

If you're interested, check HISTORY.md

