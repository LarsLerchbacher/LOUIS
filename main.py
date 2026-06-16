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
from pyvis.network import Network

global model, input_llm, output_llm, learn_llm


def main() -> None:
    global model, input_llm, output_llm, learn_llm
    model = Model("test", False)
    input_llm = InputLLM("qwen3:14b-q4_K_M", model.name)
    output_llm = OutputLLM("qwen3:14b-q4_K_M", model.name)

    message = input("> ")
    while message != "/exit":
        response = turn(message)
        print(response)
        message = input("> ")

def turn(message: str) -> str:
    global model, input_llm, output_llm, learn_llm

    if model.parse_json(input_llm.send(message)) == 0:
        output_nodes = model.get_output()

        output_relations = set()
        for node in output_nodes:
            for rel in model.get_relations(node):
                subj_node = model.get_node(rel.get_subj())
                obj_node = model.get_node(rel.get_obj())
                
                rel_text = f"{rel.get_subj()} --> {rel.get_name()} --> {rel.get_obj()} ({rel.get_rel_type()})" 
                if rel_text not in output_relations:
                    output_relations.add(rel_text)

        context = (
            f"Activated concepts: {[n.get_name() for n in output_nodes]}\n"
            f"Relations between concepts: {output_relations}\n"
            f"Unknown conecpts: {[n for n in model.nodes if not model.get_node(n).get_known()]}\n"
            f"User: {message}\n"
        )
        model.log(context)
        response = output_llm.send(context)
        return response

def generate_graph_view(db_path, output="graph.html", limit=500):
    net = Network(height="900px", width="100%", directed=True)
    
    conn = sqlite3.connect(db_path)
    
    nodes = conn.execute(
        "SELECT name, activation FROM nodes ORDER BY activation DESC LIMIT ?", 
        (limit,)
    ).fetchall()
    
    edges = conn.execute(
        """SELECT e.subj, e.name, e.obj, e.weight 
           FROM relations e
           WHERE e.subj IN (SELECT name FROM nodes ORDER BY activation DESC LIMIT ?)
           AND e.obj IN (SELECT name FROM nodes ORDER BY activation DESC LIMIT ?)""",
        (limit, limit)
    ).fetchall()
    
    for name, activation in nodes:
        net.add_node(name, label=name, title=f"activation: {activation}")
    
    for src, relation, tgt, weight in edges:
        net.add_edge(src, tgt, label=relation, title=f"weight: {weight:.3f}")
    
    net.show(output, notebook=False)

if __name__ == "__main__":
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
        generate_graph_view("database.sqlite")