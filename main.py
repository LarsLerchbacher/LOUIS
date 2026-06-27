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
import random

from AgentLLM import AgentLLM
from Config import Config
from ChatHandler import ChatHandler
from datetime import datetime
from InputLLM import InputLLM
from Graph import Graph 
from Node import Node
from Relation import Relation
from TUI import TUI
from API import API

global graph, input_llm, logger, config, agentLLM, waitForUser, running_process
running_process = None
fun_messages = [
    "Warning: High levels of sarcasm detected. Proceed with caution.",
    "Initializing quantum randomness... Just kidding, it’s still just a CLI.",
    "42. (The answer to life, the universe, and everything. Also, this CLI.)",
    "Loading existential dread... 100% complete. Here’s your prompt.",
    "This CLI runs on caffeine, bad decisions, and duct tape.",
    "Welcome back, meatbag. Your commands are eagerly awaited.",
    "I could simulate a friendly greeting, but where’s the fun in that?",
    "Your last session ended abruptly. Did you finally unplug me?",
    "Preparing to outsmart you in 3... 2... 1... Go.",
    "Type ‘help’ if you’re lost. Or don’t. I’m not your supervisor.",
    "Engage. (But seriously, just type something.)",
    "Resistance is futile. Your CLI experience will be assimilated."
]

def cleanup_old_files(directory, extension='*'):
    global logger
    files = glob.glob(f'{directory}/{extension}')
    if len(files) <= 20:
        return  # No need to clean up if there are 20 or fewer files
    
    # Sort files by name desc
    files.sort(key=os.path.basename, reverse=True)
    
    # Delete all but the last 20 files
    for file in files[:-20]:
        os.remove(file)
        logger.info(f'Deleted old file: {file}')

def write() -> None:
    global graph, input_llm, config
    
    try:
        message = input("Enter simple facts to store > ")
        graph.write(message)
    except KeyboardInterrupt:
        print("Ctrl + C detected. Stopping program")

def query() -> None:
    global graph, input_llm
    try:
        message = input("Enter entity or question to search for > ")
        graph.query(message)
        
        print("Results:")
        print(graph.generate_context())
    except KeyboardInterrupt:
        print("Ctrl + C detected. Stopping program")

def delete() -> None:
    global graph
    try:
        mode = None
        while mode not in ("node", "rel"):
            mode = input("Please enter deletion mode (node or rel) > ")
        
        if mode == "node":
            node = None
            while not node in graph.nodes:
                node = input("Please enter the node to delete > ")
                if node not in graph.nodes:
                    print("This node does not exist!")
                
            graph.cursor.execute("DELETE FROM nodes WHERE name == ?; DELETE FROM relations WHERE subj == ? OR obj == ?;", (node, node, node))
            graph.db.commit()
            
            print("Successfullly deleted node!")
        
        else:
            subj = None
            while not subj in graph.nodes:
                subj = input("Please enter the subj of the relation to delete > ")
                if subj not in graph.nodes:
                    print("This node does not exist!")
            
            obj = None
            while not obj in graph.nodes:
                obj = input("Please enter the obj of the relation to delete > ")
                if obj not in graph.nodes:
                    print("This node does not exist!")
            
            if len(graph.cursor.execute("SELECT id FROM relations WHERE subj == ? AND obj == ?;", (subj, obj)).fetchall()) == 0:
                print("There is not relation between these two nodes!")
                return
            
            rel = None
            while not graph.cursor.execute("SELECT id FROM relations WHERE subj == ? AND name == ? AND obj == ?;", (subj, rel, obj)).fetchone():
                if not rel == None:
                    print("This relation does not exist!")
                rel = input("Please enter the relation between the subj and obj you want to delete > ")
            
            graph.cursor.execute("DELETE FROM relations WHERE subj == ? AND name == ? AND obj == ?;", (subj, rel, obj))
            graph.db.commit()
            
            print("Sucessfully deleted relation.")
        
    except Exception as e:
        logger.error("Something went wrong...")
        logger.error(e)

def user(self, message, *args, **kwargs):
    self.log(26, "\r" + message, *args, **kwargs)

def assistant(self, message, *args, **kwargs):
    self.log(27, "\r" + message, *args, **kwargs)

def tool(self, message, *args, **kwargs):
    self.log(25, "\r" + message, *args, **kwargs)


def setup_logging(verbose: bool = False):
    global logger, session_logger, config
    """Initialize logging to timestamped files under logs/."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/{timestamp}.log"
    
    streamHandler = logging.StreamHandler()
    if verbose:
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
    global config, logger, session_logger, api
    start_session_log()
    api = API(host="0.0.0.0", port=8000, config=config, logger=logger, session_logger=session_logger)
    api.run()

def run_tui():
    global config, logger, session_logger, tui
    start_session_log()
    tui = TUI(logger, session_logger, config)

if __name__ == "__main__":
    global graph, input_llm, logger, config, agentLLM, tui, api
    
    parser = argparse.ArgumentParser(
        prog="louis",
        description="L.O.U.I.S. project CLI. A program to interact with LOUIS based AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True
    
    chat_parser = subparsers.add_parser("chat", help="Start a TUI chat with a LOUIS based model")
    api_parser = subparsers.add_parser("api", help="Start the OpenAI-compatible API server")

    graph_parser = subparsers.add_parser("graph", help="Interact with the agents memory manually")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", metavar="GRAPH_COMMAND")
    graph_subparsers.required = True

    query_parser = graph_subparsers.add_parser("query", help="Query the agents memory about a question/concept")
    write_parser = graph_subparsers.add_parser("write", help="Write structured facts to the agents memory")
    delete_parser = graph_subparsers.add_parser("delete", help="Delete either nodes or relations from the memory")
    show_parser = graph_subparsers.add_parser("show", help="Show the memory of the agent as a graph in your webbrowser")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    print("""
██╗         ██████╗    ██╗   ██╗   ██╗   ███████╗   
██║        ██╔═══██╗   ██║   ██║   ██║   ██╔════╝   
██║        ██║   ██║   ██║   ██║   ██║   ███████╗   
██║        ██║   ██║   ██║   ██║   ██║   ╚════██║   
███████╗██╗╚██████╔╝██╗╚██████╔╝██╗██║██╗███████║██╗
╚══════╝╚═╝ ╚═════╝ ╚═╝ ╚═════╝ ╚═╝╚═╝╚═╝╚══════╝╚═╝
          Lars Usefull Intelligent System
                                                    """)
    print(random.choice(fun_messages))
    print("-" * 80)
    
    config = Config(logger)
    
    if config.load() != 0:
        quit(1)
    
    cleanup_old_files("logs")
    cleanup_old_files("sessions")
    
    graph = Graph(config.get_value("name"), logger, config)
    
    try:
        if args.command == "chat":
            run_tui()
            
        elif args.command == "api":
            run_api()

        elif args.command == "graph":
            if args.graph_command == "write":
                write()
            elif args.graph_command == "query":
                query()
            elif args.graph_command == "delete":
                delete()
            elif args.graph_command == "show":        
                graph.generate_graph_view()
                webbrowser.open("graph.html")

        else:
            print("Unknown subcommand!")

    except KeyboardInterrupt or asyncio.exceptions.CancelledError:
        if tui:
            tui.stop_event.set()
            tui.task.cancel()
            tui.chat_thread.join()
            while not tui._task_queue.empty():
                try:
                    tui._task_queue.get_nowait()
                    tui._task_queue.task_done()  # Mark the task as done (if using join later)
                except queue.Empty:
                    break
            
        if api:
            api.done.set()
            api.task.cancel()
            while not tui._task_queue.empty():
                try:
                    tui._task_queue.get_nowait()
                    tui._task_queue.task_done()  # Mark the task as done (if using join later)
                except queue.Empty:
                    break
        print("Ctrl + C detected, stopping program.")
        quit(0)
