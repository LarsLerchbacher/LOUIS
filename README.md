L.O.U.I.S
=========

Lars Original Usefull Intelligent System<br>

## What is LOUIS
LOUIS is an experiment to create a custom token efficient agent, building upon the current generation of **LLMs** combined with the power of **semantic networks** with **spread activation**.

## How can I use LOUIS?

You can download it, create a python virtual environment and install the requirements from `requirements.txt`.
Edit the default config.json file, add your own API key (the included one is invalid, if you're wondering, uploaded it by mistake), set your name, the name of the AI and adjust its personality prompt.
Then just run `python main.py chat` to start chatting with your own agent.
`python main.py graph` opens the graph view in the browser (is updated every write, just reload the page)
`python main.py query` launches an interactive graph query. Just type a concept, name or question and press enter. You will get exactly what LOUIS sees too.
`python main.py write` launches and interactive write mode. Type a fact in VERY simple language to write to the graph. The extractor LLM easily misinterprets stuff, so try to stick to one fact per sentence. Facts should be rephrasable to the form: `subj --- relation --> object`. This is what the graph stores internally.

## What makes LOUIS special

Aside from the fact, that it uses a semantic network as its main memory system, LOUIS also features a custom interaction loop:

1. The user sends input
2. The agent decides which tool to use. If none is selected go to step 6
3. The tool gets executed.
4. The results get added to the messages
5. Go to step 2
6. The user is prompted for their next message

This alone may not be the most uncommon loop. What is uncommon, however are the available tools:

- msg: The message tool allows the agent to communicate with the user. It is the only way the agent can send output to the user. It can be used between other tool calls, enabling it to give regular status updates. It can also be used to ask the user a question and pause the execution until an answer is received. This allows it to ask for clarification instead of guessing.
- mem_get: Querries the memory graph
- mem_write: Writes facts to the memory
- mem_delete: Delete wrong/old nodes and relations for memory
- exec: Execute shell commands


## Capabilities

LOUIS uses a differrent approach than OpenClaw, when it comes to adding features.

We have 'capabilities', which are markdown files, just like Skills in OpenClaw, containing usage information about different user- or system specific tools and workflows.
The agent is instructed to look throught the available capabilities before guessing how to execute an action.

Capabilities are **markdown files on disk** and **never injected into context**, unless the agent decides to read one using the exec tool.
This is the major difference to OpenClaw, which exposes all available skills and tools every turn, regardless of the task. Our approach reduces token cost **immensly**.
On a day of heavy testing, LOUIS used about 700k tokens, while OpenClaw used between 5 and 20 MILLION tokens.


## History

### Beginnings
LOUIS originally started out as an attempt to create an aritifical intelligence by "modelling the human brain into a database". This was a stupid attempt of me, thinking I came up with something new.
Turns out, there is already something like this: semantic networks with spread activation. 

### How the memory works
You take a database (in this case SQLite but mostly Graph based), add nodes as neurons or concepts and edges between the nodes (relations, synapses, however you want to call them). Now for retrieving, you activate some nodes, if their activation crosses the threshold, they propagate some of their activation to connected nodes, based on the relation strength. Afterwards, you take the most activated nodes and the strongest relations, and there you go: the graph just retrieved information similar to how the brain would. Writing works similar, but if a relation successfully activates the target node, it gets stronger, otherwise weaker. Also, relations decay over time, that means if they are not activated often enough, they will get very weak after some time (we're talking years here). In the inital prototypese, I hooked up some LLMs for converting natural language to usable input and output back into language. This of course produced weird and unstable results.

### Memory!
When I realized, that this alone wasn't going to produce any form of 'intelligent' output, I decided to convert it to a memory backend for AIs.
In this stage I added the inital chat interface, the CLI commands and the graph view.

### OpenClaw
At that time, I was testing OpenClaw, I had already experimented with it for weeks, even bought 5$ worth of API credits on an inference provider platform, and was hitting the main problem of OpenClaw:
> Its token inefficiency

OpenClaw is a **great** tool, and I think those people that can use it properly, have a great agent at their side, but for me, it was not worth the effort. It has some problems, like being designed for MacOS, which means half the plugins (especially voice interaction) are made for Mac only, the regular updates tend to break stuff, the documentation that includes unsuported keys or does NOT include needed ones and especially the huge amount of tokens it uses. Running it on free models is almost impossible. And for paid ones, it can get too expensive for students like me to keep up. The system prompt alone is **16k** of tokens with more or less default setup. I could crunch it down to 9k, but it was still too expensive and burning lots of tokens every turn.

### LOUIS is back!
The missing Linux support for voice interactions (yes, I can use dictation mode, which somehow works even worse than sending voice messages over matrix to the same stt provider, but it doesn't even speak the responses out loud) and the token problem led to me wanting to create my own agent system. Something simpler, using less tokens, less built-in tools, more externalized "skill"-like reference files and a custom 
interaction loop. That is why I started to convert LOUIS back into a full-flegged AI assistant. This time, with Mistral API integration, using the graph as a memory backend.


### AI work on this project

I used my OpenClaw agent "JARVIS" (yes, very generic, I know) to create two and a half pull requests for this project. The last one, a refactor task, failed during the work on it. I then had to manually clean it up (ok, I also used an AI chat in my IDE to do it, but a lot of work was manual too). 
