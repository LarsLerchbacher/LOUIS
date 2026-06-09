from datetime import datetime
import ollama
import json
import nltk
import re
import os

from Node import Node
from Relation import Relation


class Model():
    def __init__(self, name: str, production: bool):
        self.name = name
        self.production = production
        self.nodes = []
    
    def log(self, text: str) -> None:
        print(text)
        # TODO: implement log

    def warn(self, text: str) -> None:
        print(text)
        # TODO: implement warn

    def err(self, text: str) -> None:
        print(text)
        # TODO: implement err
    
    def parseMarkdown(self, markdown: str):
        result = {}
        
        # Split markdown into lines
        lines = markdown.split("\n")
        
        # Remove empty lines
        for line in lines:
            if line == "":
                lines.remove(line)
        
        # Strip lines
        lines = [line.strip() for line in lines]
        

        i = -1
        while i < len(lines) - 1:
            i += 1

            line = lines[i]

            if line.startswith("# "):
                result["name"] = line.removeprefix("# ").strip()
            
            elif "Known: " in line:
                result["known"] = bool(line.removeprefix("Known: "))
            
            elif "Flagged: " in line:
                result["flagged"] = bool(lines[i].removeprefix("Flagged: "))
            
            elif "Confidence: " in line:
                result["confidence"] = float(lines[i].removeprefix("Confidence: "))
            
            elif "## Relations" in line:
                result["relations"] = []
            
            # Skip relation table start
            elif "|Relation|Target|Weight|Type|Last Activated|" in line or "|---|---|---|---|" in line:
                pass
            
            else:
                rel = {}

                # Remove the outer boundaries
                line = line.removeprefix("|").removesuffix("|")
                parts = line.split("|")
                parts = [ p.strip() for p in parts]
                
                if len(parts) < 5:
                    self.err(f"Detected invalid relation at line {i}. Skipping relation")
                    continue

                try:
                    rel["subj"] = result["name"]
                    rel["name"] = parts[0]
                    rel["obj"] = parts[1].removeprefix("[[").removesuffix("]]")
                    rel["weight"] = float(parts[2])
                    rel["type"] = parts[3] 
                    rel["last_fired"] = datetime.fromisoformat(parts[4])
                    result["relations"].append(Relation.fromJSON(rel))
                except ValueError as e:
                    if "float" in str(e):
                        self.err(f"Detected invalid relation weight at line {i}. Skipping relation")
                    elif "isoformat" in str(e):
                        self.err(f"Detected invalid relation weight at line {i}. Skipping relation")
                    else:
                        self.err(e)
            

        props = [ "name", "known", "flagged", "confidence", "relations", "relations"]
        for prop in props:
            try:
                result[prop]
            except:
                raise RuntimeError(f"Missing node property '{prop}' detected. Skipping file")
        
        return result

    
    def discover(self):
        for filename in os.listdir(self.name):
            with open(os.path.join(self.name, filename), mode="r") as file:
                content = file.read()
                try:
                    data = self.parseMarkdown(content)
                    node = Node.fromJSON(data)
                    self.nodes.append(node)
                except RuntimeError as e:
                    self.err(e)


if __name__ == "__main__":
    model = Model("base", False)
    model.discover()
    print(model.nodes[0])