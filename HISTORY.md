# Beginnings
LOUIS originally started out as an attempt to create an artificial intelligence by "modelling the human brain into a database". At that time I was thinking, I came up with something new.
Turns out, this already exists: semantic networks with spread activation. 

# How the memory works
You take a database (in this case SQLite but mostly Graph based), add nodes as neurons or concepts and edges between the nodes (relations, synapses, however you want to call them). Now for retrieving, you activate some nodes, if their activation crosses the threshold, they propagate some of their activation to connected nodes, based on the relation strength. Afterwards, you take the most activated nodes and the strongest relations, and there you go: the graph just retrieved information similar to how the brain would. Writing works similar, but if a relation successfully activates the target node, it gets stronger, otherwise weaker. Also, relations decay over time, that means if they are not activated often enough, they will get very weak after some time (we're talking years here). In the initial prototypes, I hooked up some LLMs for converting natural language to usable input and output back into language. This of course produced weird and unstable results.

# Memory!
When I realized, that this alone wasn't going to produce any form of 'intelligent' output, I decided to convert it to a memory backend for AIs.
In this stage I added the initial chat interface, the CLI commands and the graph view.

# OpenClaw
At that time, I was testing OpenClaw, I had already experimented with it for weeks, even bought 5$ worth of API credits on an inference provider platform, and was hitting the main problem of OpenClaw:
> Its token inefficiency

OpenClaw is a **great** tool, and I think those people that can use it properly, have a great agent at their side, but for me, it was not worth the effort. It has some problems, like being designed for MacOS, which means half the plugins (especially voice interaction) are made for Mac only, the regular updates tend to break stuff, the documentation that includes unsuported keys or does NOT include needed ones and especially the huge amount of tokens it uses. Running it on free models is almost impossible. And for paid ones, it can get too expensive for students like me to keep up. The system prompt alone is **16k** of tokens with more or less default setup. I could crunch it down to 9k, but it was still too expensive and burning lots of tokens every turn.

# LOUIS is back!
The missing Linux support for voice interactions (yes, I can use dictation mode, which somehow works even worse than sending voice messages over matrix to the same stt provider, but it doesn't even speak the responses out loud) and the token problem led to me wanting to create my own agent system. Something simpler, using less tokens, less built-in tools, more externalized "skill"-like reference files and a custom 
interaction loop. That is why I started to convert LOUIS back into a full-flegged AI assistant. This time, with Mistral API integration, using the graph as a memory backend.
