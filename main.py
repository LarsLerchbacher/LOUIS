import argparse
import json
import os
import logging
import sqlite3

from datetime import datetime
from InputLLM import InputLLM
from Node import Node
from Model import Model
from Relation import Relation

global model, input_llm

def main() -> None:
    global model, input_llm

    message = input("> ")
    raw_facts = input_llm.send(message)
    
    if model.parse_json(normalized_facts) == 0:
        context = model.generate_context() 
        model.generate_graph_view()
        print(context)
    else:
        print("=====>>> The program ran into an error while processing your request. Please check the logs for more details! <<<=====")
        
def query() -> None:
    global model, input_llm

    message = input("> ") 
    model.query(message)
    
    print(model.generate_context())

if __name__ == "__main__":
    global model, input_llm, output_llm, learn_llm, normalizer_llm
    model = Model("test", False)
    input_llm = InputLLM("lfm2.5", model.name)

    parser = argparse.ArgumentParser(
        prog="louis",
        description="L.O.U.I.S. project CLI. A program to interact with LOUIS based AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    write_parser = subparsers.add_parser("write", help="Write structured facts to the graph")
    query_parser = subparsers.add_parser("query", help="Query the graph about a question/concept")
    graph_parser = subparsers.add_parser("graph", help="View a graph representation of the AI models memory")
    
    args = parser.parse_args()
    
    if args.command == "write":
        main()
    elif args.command == "query":
        query()
    elif args.command == "graph":
        model.generate_graph_view()
        os.open("graph.html")


