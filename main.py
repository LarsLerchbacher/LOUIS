import argparse
import json
import os
import logging
import sqlite3
import webbrowser

from AgentLLM import AgentLLM
from Config import Config
from datetime import datetime
from InputLLM import InputLLM
from Graph import Graph 
from Node import Node
from ollama import Message
from Relation import Relation

global graph, input_llm, logger, config, agentLLM, waitForUser

def write() -> None:
    global graph, input_llm, config
    
    try:
        message = input("> ")
        graph.write(message)
        
        context = graph.generate_context() 
        graph.generate_graph_view()
        print(context)
    except KeyboardInterrupt:
        print("Ctrl + C detected. Stopping program")
        
def query() -> None:
    global graph, input_llm
    try:

        message = input("> ") 
        graph.query(message)
        
        print(graph.generate_context())
    except KeyboardInterrupt:
        print("Ctrl + C detected. Stopping program")

def chat() -> None:
    global logger, agentLLM, config, askUser 
    
    tools = [ 
        {
            "name": "message", "description": "send a message to the user",
            "parameters": {
                "type": "object", 
                "properties": {
                    "content": {"type": "string", "description": "The message content"},
                    "waitForUser": {"type": "boolean", "description": "Does the user need to enter new input to continue?"}
                },
                "required": ["content", "waitForUser"]
            }
        },
        {
            "name": "memory_get", "description": "retrieve knowledge from your memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": { "type": "string", "description": "The term to search for"},
                    "intent": { "type": "string", "description": "The retrival mode (changes search behaviour in the memory). Can be WHO, WHAT, HOW, WHY or RELATE. Is optional."}
                },
                "required": ["text"]
            }
        },
        {
            "name": "memory_write", "description": "Store memory in your long term memory. Use this tool, whenever you learned new information that is worth keeping across sessions. This tool only ADDS information. It never EDITS or DELETES information. Use the memory_delete tool for those actions (delete and add new for editing)",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": { "type": "string", "description": "The facts to store. Only store facts (statements), never questions or exclamations. PHRASE THE FACTS EXTREMLY SIMPLE AND ONE PER SENTENCE IF POSSIBLE!"},
                },
                "required": ["text"]
            }
        },
        {
            "name": "memory_write", "description": "Remove wrong/old nodes or relations from memory. TREAT WITH EXTREM CAUTION! THIS IS AN IRREVERSIBLE ACTION!",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": { "type": "string", "description": "The type of object to delete. Can either be NODE or RELATION"},
                    "subj": { "type": "string", "description": "Either the name of the node to delete (if deleting a node) or the subject of the relation to delete."},
                    "rel": { "type": "string", "description": "The name (kind) of the relation to delete (is_a for example)"},
                    "obj": { "type": "string", "description": "The object of the relation to delte"},
                },
                "required": ["mode", "subj"]
            }
        }
        
    ]

    agentLLM = AgentLLM(config.get_value("chat-model"), config, tools)

    funcs = {
        "message": send_message,
        "memory_get": memory_get,
        "memory_write": memory_write,
        "memory_delete": memory_delete
    }
    
    if len(funcs) != len(tools):
        logger.error("YOU FORGOT TO ADD A NEW TOOL TO THE FUNCS MAP AGAIN! REMEMBER IT ALREADY!")
        quit(1)
    
    askUser = True

    while True:
        
        if askUser:
            print("-" * 50)
            message = input("> ")
            print("-" * 50)
            print()

            if message == "/exit":
                break
            
            askUser = False
        else:
            message = "Tool results are in. (Auto generated message, do not respond to this, just process your tool results)"
    
        response = agentLLM.send(message)
        
        if response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls
            for call in tool_calls:
                try:
                    response = funcs[call.function.name](**json.loads(call.function.arguments))
                except KeyError:
                    response = "Tool not found!"

                agentLLM.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": response
                })

def send_message(content: str, waitForUser: bool = False) -> str:
    global askUser 
    askUser = waitForUser 
    print(content)
    return "delivered"

def memory_get(text: str, intent: str = None) -> str:
    global graph
    graph.query(text, intent)
    return graph.generate_context()

def memory_write(text: str) -> str:
    global graph
    graph.write(text)
    return "Successfully wrote to memory"

def memory_delete(mode: str = "node", subj: str = "", rel: str = None, obj: str = None):
    global graph
    if mode == "NODE":
        graph.cursor.execute("DELETE FROM nodes WHERE name == ?;", (subj,))
        graph.db.commit()
        return f"Deleted '{subj}'"
    elif mode == "RELATION":
        if not subj or not rel or not obj:
            return "ERROR: One of the required parameters for relation deletion (subj, rel, obj) was not provided! Please try again with all correct parameters."

        graph.cursor.execute("DELETE FROM relations WHERE subj == ? AND name == ? AND obj == ?;", (subj, rel, obj))
        graph.db.commit()
        return "Deleted relation"
    else:
        return "Unknown deletion mode"

def setup_logging(debug: bool = False):
    global logger
    """Initialize logging to timestamped files under logs/."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/{timestamp}.log"
    
    streamHandler = logging.StreamHandler()
    if debug:
        streamHandler.setLevel(logging.DEBUG)
    else:
        streamHandler.setLevel(logging.WARN)

    handlers = [logging.FileHandler(log_filename), streamHandler]
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )

    logger = logging.getLogger(__name__)

if __name__ == "__main__":
    global graph, input_llm, logger, config, agentLLM

    parser = argparse.ArgumentParser(
        prog="louis",
        description="L.O.U.I.S. project CLI. A program to interact with LOUIS based AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    chat_parser = subparsers.add_parser("chat", help="Start a TUI chat with a LOUIS based model")
    write_parser = subparsers.add_parser("write", help="Write structured facts to the graph")
    query_parser = subparsers.add_parser("query", help="Query the graph about a question/concept")
    graph_parser = subparsers.add_parser("graph", help="View a graph representation of the AIs memory")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    config = Config(logger)
    
    if config.load() != 0:
        quit(1)

    graph = Graph(config.get_value("name"), logger, config, args.verbose)
    
    if args.command == "write":
        write()
    elif args.command == "query":
        query()
    elif args.command == "chat":
        chat()
    elif args.command == "graph":
        graph.generate_graph_view()
        webbrowser.open("graph.html")
