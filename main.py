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
        }
    ]

    agentLLM = AgentLLM(config.get_value("chat-model"), config, tools)

    funcs = {"message": send_message}
    
    askUser = True

    while True:
        
        if askUser:
            message = input("> ")

            if message[0] == "/":
                if message == "/exit":
                    break
                # place for more commands
                else:
                    print(f"WRONG SLASH COMMAND '{message}'")
            
            waitForUser = False
        else:
            message = ""
    
        response = agentLLM.send(message)
        
        if response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls
            for call in tool_calls:
                response = funcs[call.function.name](**json.loads(call.function.arguments))
                agentLLM.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": response
                })

def send_message(content: str, waitForUser: bool):
    global askUser 
    askUser = waitForUser 
    print(content)
    return "delivered"

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
