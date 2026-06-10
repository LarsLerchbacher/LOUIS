from datetime import datetime
import ollama
import json
import nltk
import re
import os
import logging

from Node import Node
from Relation import Relation


class Model():
    def __init__(self, name: str, production: bool):
        self.name = name
        self.production = production
        self.nodes = {}
        
        self.setup_logging()
        
        self.discover()
    
    def setup_logging(self):
        """Initialize logging system"""
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{log_dir}/{timestamp}.log"
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler() 
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def log(self, text: str) -> None:
        """Log debug information"""
        self.logger.debug(text)
    
    def warn(self, text: str) -> None:
        """Log warning information"""
        self.logger.warning(text)
    
    def err(self, text: str) -> None:
        """Log error information"""
        self.logger.error(text)
    
    def parseMarkdown(self, markdown: str):
        result = {}
        
        # Split markdown into lines
        lines = markdown.split("\n")
        
        # Remove empty lines
        lines = [line for line in lines if line.strip() != ""]
        
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
                result["flagged"] = bool(line.removeprefix("Flagged: "))
            
            elif "Confidence: " in line:
                result["confidence"] = float(line.removeprefix("Confidence: "))
            
            elif "Activation: " in line:
                result["activation"] = float(line.removeprefix("Activation: "))
            
            elif "Threshold: " in line:
                result["threshold"] = float(line.removeprefix("Threshold: "))
            
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
                parts = [p.strip() for p in parts]
                
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
                        self.err(f"Detected invalid relation timestamp at line {i}. Skipping relation")
                    else:
                        self.err(f"Unexpected error parsing relation at line {i}: {e}")
            

        props = ["name", "known", "flagged", "confidence", "activation", "threshold", "relations"]
        for prop in props:
            try:
                result[prop]
            except KeyError:
                raise RuntimeError(f"Missing node property '{prop}' detected. Skipping file")
        
        return result

    
    def discover(self):
        self.nodes = {}

        for filename in os.listdir(self.name):
            if filename != ".obsidian":
                filepath = os.path.join(self.name, filename)
                try:
                    with open(filepath, mode="r", encoding="utf-8") as file:
                        content = file.read()
                        try:
                            data = self.parseMarkdown(content)
                            node = Node.fromJSON(data)
                            self.nodes[node.getName()] = node
                            self.log(f"Successfully loaded node: {node.getName()}")
                        except RuntimeError as e:
                            self.err(f"Failed to parse file {filename}: {e}")
                except Exception as e:
                    self.err(f"Failed to read file {filename}: {e}")
    
    def getNode(self, name: str) -> Node:
        try:
            return self.nodes[name]
        except KeyError:
            self.warn(f"Node '{name}' not found!")
            return None

if __name__ == "__main__":
    model = Model("base", False)
    print(model.getNode("Template Node"))