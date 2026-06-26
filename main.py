import glob
import os
import argparse
import json
import logging
import re
import sqlite3
import subprocess
import webbrowser
import asyncio

from AgentLLM import AgentLLM
from Config import Config
from ChatHandler import ChatHandler
from datetime import datetime
from InputLLM import InputLLM
from Graph import Graph 
from Node import Node
from Relation import Relation
from TUI import TUI
from openai_endpoint import API

global graph, input_llm, logger, config, agentLLM, waitForUser, running_process
running_process = None

def cleanup_old_files(directory, extension='*'):
    global logger
    files = glob.glob(f'{directory}/{extension}')
    if len(files) <= 5:
        return  # No need to clean up if there are 5 or fewer files
    
    # Sort files by modification time, oldest first
    files.sort(key=os.path.getmtime)
    
    # Delete all but the last 5 files
    for file in files[:-5]:
        os.remove(file)
        logger.info(f'Deleted old file: {file}')

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

def user(self, message, *args, **kwargs):
    self.log(26, "\r" + message, *args, **kwargs)

def assistant(self, message, *args, **kwargs):
    self.log(27, "\r" + message, *args, **kwargs)

def tool(self, message, *args, **kwargs):
    self.log(25, "\r" + message, *args, **kwargs)


def safe_json_loads(s):
    """Necesary to avoid problems when the LLM uses newlines"""
    s = s.replace("\n", "\\n") # Replace actual newlines with python escape sequence
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # remove all other control chars
    return json.loads(s) 


def setup_logging(debug: bool = False):
    global logger, session_logger, config
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
    

def start_session_log():
    global logger, session_logger, config
    
    session_logger = logging.getLogger("session")
    
    log_dir = "sessions"
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/{timestamp}.log"
    
    streamHandler = logging.StreamHandler()
    streamHandler.setLevel(26)
    
    handlers = [logging.FileHandler(log_filename), streamHandler]
    
    # Add custom log levels
    logging.addLevelName(27, config.get_value("name").upper())
    logging.addLevelName(26, "USER")
    logging.addLevelName(25, "TOOL") 
    
    logging.Logger.user = user
    logging.Logger.assistant = assistant
    logging.Logger.tool = tool
    
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(message)s\n%(asctime)s - %(levelname)s\n" + "-" * 50))
        session_logger.addHandler(handler)  


def run_api():
    global config, logger, session_logger
    start_session_log()
    api = API(host="0.0.0.0", port=8000, config=config, logger=logger, session_logger=session_logger)
    api.run()

def run_tui():
    global config, logger, session_logger
    start_session_log()
    tui = TUI(logger, session_logger, config)

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
    api_parser = subparsers.add_parser("api", help="Start the OpenAI-compatible API server")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    config = Config(logger)
    
    if config.load() != 0:
        quit(1)
    
    cleanup_old_files("logs")
    cleanup_old_files("sessions")
    
    graph = Graph(config.get_value("name"), logger, config, args.verbose)
    
    if args.command == "write":
        write()
    elif args.command == "query":
        query()
    elif args.command == "chat":
        try:
            #chat()
            run_tui()
        except KeyboardInterrupt:
            print("Ctrl + C detected, stopping program.")
    elif args.command == "graph":
        graph.generate_graph_view()
        webbrowser.open("graph.html")
    elif args.command == "api":
        run_api()
    else:
        print("Unknown subcommand!")
