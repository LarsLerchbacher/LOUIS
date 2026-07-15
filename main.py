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
import queue
import sys

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
from State import State
from cron import CronManager

global graph, input_llm, logger, config, agentLLM, waitForUser, running_process, tui, api, state
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
    """Clean up old files in the specified directory, keeping only the 20 most recent files.
    
    Args:
        directory (str): The directory to clean up.
        extension (str): The file extension to filter by. Defaults to '*' (all files).
    """
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

def write(fact: str) -> None:
    """Write a fact to the graph.
    
    Args:
        fact (str): The fact to write to the graph.
    """
    global graph, input_llm, config
    
    try:
        graph.write(fact)
    except KeyboardInterrupt:
        print("Ctrl + C detected. Stopping program")

def query(question: str) -> None:
    """Query the graph for information related to the question.
    
    Args:
        question (str): The question to query the graph with.
    """
    global graph, input_llm
    try:
        graph.query(question)
        
        print("Results:")
        print(graph.generate_context())
    except KeyboardInterrupt:
        print("Ctrl + C detected. Stopping program")

def delete(mode: str, subj: str, relation: str = None, obj: str = None) -> None:
    """Delete a node or relation from the graph.
    
    Args:
        mode (str): The mode of deletion ('node' or 'relation').
        subj (str): The subject node.
        relation (str, optional): The relation to delete (required for 'relation' mode).
        obj (str, optional): The object node (required for 'relation' mode).
    """
    global graph
    try:
        if mode == "node":
            if subj not in graph.nodes:
                print("This node does not exist!")
                return
            
            graph.cursor.execute("DELETE FROM nodes WHERE name == ?; DELETE FROM relations WHERE subj == ? OR obj == ?;", (subj, subj, subj))
            graph.db.commit()
            
            print("Successfullly deleted node!")
        
        else:
            if not subj in graph.nodes:
                print("The subject node does not exist!")
                return
            
            if not obj in graph.nodes:
                print("The object node does not exist!")
                return
            
            if len(graph.cursor.execute("SELECT id FROM relations WHERE subj == ? AND obj == ?;", (subj, obj)).fetchall()) == 0:
                print("There is not relation between these two nodes!")
                return
            
            rel = graph.cursor.execute("SELECT id FROM relations WHERE subj == ? AND name == ? AND obj == ?;", (subj, relation, obj)).fetchall()
            if not rel:
                print("This relation does not exist!")
                return
            else:
                graph.cursor.execute("DELETE FROM relations WHERE subj == ? AND name == ? AND obj == ?;", (subj, relation, obj))
                graph.db.commit()
                print("Sucessfully deleted relation.")
    
    except Exception as e:
        logger.error("Something went wrong...")
        logger.error(e)

def user(self, message, *args, **kwargs):
    """Log a user message.
    
    Args:
        message (str): The message to log.
    """
    self.log(26, "\r" + message, *args, **kwargs)

def assistant(self, message, *args, **kwargs):
    """Log an assistant message.
    
    Args:
        message (str): The message to log.
    """
    self.log(27, "\r" + message, *args, **kwargs)

def tool(self, message, *args, **kwargs):
    """Log a tool message.
    
    Args:
        message (str): The message to log.
    """
    self.log(25, "\r" + message, *args, **kwargs)


def setup_logging(verbose: bool = False):
    """Initialize logging to timestamped files under XDG_STATE_HOME/louis/logs/.
    
    Args:
        verbose (bool): Whether to enable verbose logging.
    """
    global logger, session_logger, config
    xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    log_dir = os.path.join(xdg_state_home, "louis", "logs")
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
    """Start logging for the current session."""
    global logger, session_logger, config
    
    session_logger = logging.getLogger("session")
    
    xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    log_dir = os.path.join(xdg_state_home, "louis", "sessions")
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
    """Run the API server."""
    global config, logger, session_logger, api, state
    start_session_log()
    api = API(host="0.0.0.0", port=8000, config=config, logger=logger, session_logger=session_logger, state=state)
    api.run()

def run_tui():
    """Run the Text User Interface."""
    global config, logger, session_logger, tui, state
    start_session_log()
    tui = TUI(logger, session_logger, config, state)

if __name__ == "__main__":
    global graph, input_llm, logger, config, agentLLM, tui, api, cron_manager, state
    
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
    query_parser.add_argument("question")
    write_parser = graph_subparsers.add_parser("write", help="Write structured facts to the agents memory")
    write_parser.add_argument("fact")
    delete_parser = graph_subparsers.add_parser("delete", help="Delete either nodes or relations from the memory")
    delete_mode_parser = delete_parser.add_subparsers(dest="delete_mode", metavar="DELETION_MODE")
    delete_mode_parser.required = True

    delete_node_parser = delete_mode_parser.add_parser("node", help="Delete a node and all of its relations from the graph")
    delete_node_parser.add_argument("node")

    delete_relation_parser = delete_mode_parser.add_parser("relation", help="Delete a relation from the graph")
    delete_relation_parser.add_argument("subj")
    delete_relation_parser.add_argument("relation")
    delete_relation_parser.add_argument("obj")
    show_parser = graph_subparsers.add_parser("show", help="Show the memory of the agent as a graph in your webbrowser")
    
    cron_parser = subparsers.add_parser("cron", help="Manage automated prompts using OpenWebUI's automations API")
    cron_subparser = cron_parser.add_subparsers(dest="cron_command", metavar="CRON_COMMAND")
    cron_subparser.required = True
    
    cron_list_parser = cron_subparser.add_parser("list", help="List all existing automations")
    cron_add_parser = cron_subparser.add_parser("add", help="Add a new automation")
    cron_add_parser.add_argument("name", help="The name of the automation")
    cron_add_parser.add_argument("prompt", help="The prompt that the model should execute when the automation is run") 
    cron_add_parser.add_argument("rrule", help="The RRULE defining when to run the automation. See RFC 5545 for details.")
    
    cron_update_parser = cron_subparser.add_parser("update", help="Update an automation selected by its ID")
    cron_update_parser.add_argument("id", help="The ID of the automation to update")
    cron_update_parser.add_argument("name", help="The name of the automation")
    cron_update_parser.add_argument("prompt", help="The prompt that the model should execute when the automation is run") 
    cron_update_parser.add_argument("rrule", help="The RRULE defining when to run the automation. See RFC 5545 for details.")
    cron_update_parser.add_argument("is_active", help="Should the automation be run when it's RRULE's requirements are met")
    
    cron_run_parser = cron_subparser.add_parser("run", help="Run an automation selected by its ID")
    cron_run_parser.add_argument("id", help="The ID of the automation to run")
    
    cron_delete_parser = cron_subparser.add_parser("delete", help="Delete an automation selected by its ID")
    cron_delete_parser.add_argument("id", help="The ID of the automation to delete")
    
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    print("""
██╗         ██████╗    ██╗   ██╗   ██╗   ███████╗    
██║        ██╔═══██╗   ██║   ██║   ██║   ██╔════╝    
██║        ██║   ██║   ██║   ██║   ██║   ███████╗    
██║        ██║   ██║   ██║   ██║   ██║   ╚════██║    
███████╗██╗╚██████╔╝██╗╚██████╔╝██╗██║██╗███████║██╗
╚══════╝╚═╝ ╚═════╝ ╚═╝ ╚═════╝ ╚═╝╚═╝╚═╝╚══════╝╚═╝
     Lars Optimized Usefull Intelligent System
                                                """)
    print(random.choice(fun_messages))
    print("-" * 80)
    
    config = Config(logger)
    
    if config.load() != 0:
        quit(1)
    
    state = State(logger)
    if state.load() != 0:
        quit(1)
    
    xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    log_dir = os.path.join(xdg_state_home, "louis", "logs")
    session_dir = os.path.join(xdg_state_home, "louis", "sessions")
    
    cleanup_old_files(log_dir)
    cleanup_old_files(session_dir)
    
    graph = Graph(config.get_value("name"), logger, config)
    
    try:
        match args.command:
            case "chat":
                run_tui()
            
            case "api":
                run_api()
                
            case "graph":
                match args.graph_command:
                    case "write":
                        write(args.fact)
                    case "query":
                        query(args.question)
                    case "delete":
                        if args.delete_mode == "node":
                            delete("node", args.node)
                        else:
                            delete("relation", args.subj, args.relation, args.obj)
                    case "show":
                        graph.generate_graph_view()

                        xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share/")
                        data_dir = os.path.join(xdg_data_home, "louis")
                        os.makedirs(data_dir, exist_ok=True)

                        webbrowser.open(os.path.join("graph.html", data_dir))
            
            case "cron":
                cron_manager = CronManager(logger, config)
                try:
                    match args.cron_command:
                        case "list":
                            print(cron_manager.list_automations())
                        case "add":
                            cron_manager.create_automation(args.name, args.prompt, config.get_value("name"), args.rrule, True)
                            print("New automation has been created!")
                        case "update":
                            cron_manager.update_automation(args.id, args.name, args.prompt, config.get_value("name"), args.rrule, args.is_active)
                            print("Automation has been updated!")
                        case "delete":
                            cron_manager.delete_automation(args.id)
                            print("Successfully deleted automation!")
                        case "run":
                            cron_manager.run_automation(args.id)
                            print("Automation is now running!")
                
                except Exception as e:
                    print(e)

            case default:
                print("Unknown subcommand!")

    except (KeyboardInterrupt, asyncio.exceptions.CancelledError) as e:
        print("\nCtrl + C detected. Shutting down immediately...")
        
        # Forcefully terminate the TUI and API threads
        if 'tui' in globals() and tui:
            tui.stop_event.set()
            if hasattr(tui, 'task') and tui.task:
                tui.task.cancel()
            if hasattr(tui, 'chat_thread') and tui.chat_thread:
                # Do not join the thread to avoid waiting
                pass
        
        if 'api' in globals() and api:
            api.done.set()
            if hasattr(api, 'task') and api.task:
                api.task.cancel()
        
        print("Shutdown complete.")
        quit(0)
