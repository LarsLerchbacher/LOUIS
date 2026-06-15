from datetime import datetime
import json
from InputLLM import InputLLM
import os
from LearningLLM import LearningLLM
import logging
from OutputLLM import OutputLLM
import sqlite3

from Node import Node
from Model import Model
from Relation import Relation

global model, input_llm, output_llm, learn_llm


def main() -> None:
    global model, input_llm, output_llm, learn_llm
    model = Model("base", True)
    input_llm = InputLLM("qwen3:14b-q4_K_M", model.name)
    output_llm = OutputLLM("qwen3:14b-q4_K_M", model.name)
    learn_llm = LearningLLM("qwen3:14b-q4_K_M", model.name)

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
            f"Relations between concepts: {output_relations}"
            f"Unknown conecpts: {[n for n in model.nodes if not model.get_node(n).get_known()]}"
            f"User: {message}\n"
        )
        model.log(context)
        response = output_llm.send(context)
        model.parse_json(learn_llm.send(response))
        return response


if __name__ == "__main__":
    main()