import argparse
from datetime import datetime
import json
from InputLLM import InputLLM
import os
import logging
from OutputLLM import OutputLLM
import sqlite3

from Node import Node
from Model import Model
from Relation import Relation
from NormalizerLLM import NormalizerLLM

global model, input_llm, output_llm, learn_llm, normalizer_llm


def main() -> None:
    global model, input_llm, output_llm, learn_llm, normalizer_llm

    message = input("> ")
    while message != "/exit":
        response = turn(message)
        print(response)
        message = input("> ")

def turn(message: str) -> str:
    global model, input_llm, output_llm, learn_llm, normalizer_llm

    # Step 1: Extract raw facts using InputLLM
    raw_facts = input_llm.send(message)
    
    # Step 2: Normalize the extracted facts using NormalizerLLM
    normalized_facts = normalizer_llm.send(raw_facts)
    
    # Step 3: Parse and feed the normalized facts into the model
    if model.parse_json(normalized_facts) == 0:
        output_nodes = model.get_output()

        output_relations = set()
        for node in output_nodes:
            for rel in model.get_relations(node):
                subj_node = model.get_node(rel.get_subj())
                obj_node = model.get_node(rel.get_obj())
                
                rel_text = f"{rel.get_subj()} --> {rel.get_name()} --> {rel.get_obj()} ({rel.get_rel_type()})" 
                if rel_text not in output_relations and (subj_node in output_nodes and obj_node in output_nodes):
                    output_relations.add(rel_text)

        context = (
            f"Nodes: {[n.get_name() for n in output_nodes]}\n"
            f"Relations: {output_relations}\n"
            f"User: {message}\n"
        )
        model.log(context)
        response = output_llm.send(context)
        model.generate_graph_view()
        print(context)
        return response
    else:
        return "=====>>> The program ran into an error while processing your request. Please check the logs for more details! <<<====="



if __name__ == "__main__":
    global model, input_llm, output_llm, learn_llm, normalizer_llm
    model = Model("test", True)
    input_llm = InputLLM("lfm2.5", model.name)
    normalizer_llm = NormalizerLLM("lfm2.5", model.name)
    output_llm = OutputLLM("lfm2.5", model.name)

    parser = argparse.ArgumentParser(
        prog="louis",
        description="L.O.U.I.S. project CLI. A program to interact with LOUIS based AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    chat_parser = subparsers.add_parser("chat", help="Start a chat with the AI model in the terminal")
    graph_parser = subparsers.add_parser("graph", help="View a graph representation of the AI models memory")
    
    args = parser.parse_args()
    
    if args.command == "chat":
        main()
    elif args.command == "graph":
        model.generate_graph_view()
        os.open("graph.html")
