from datetime import datetime
import ollama
import json
import re
import os
import logging
import sqlite3

from Node import Node
from Relation import Relation


class Model():
    def __init__(self, name: str, production: bool):
        self.name = name
        self.production = production
        self.nodes = {}
        self.firedNodes = []

        self.setup_logging()
        self.setup_db()
        
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
    
    def setup_db(self):
        """Initialize tempomary database"""
        
        os.system("rm tmp.db")
        self.db = sqlite3.connect("tmp.db")
        self.cursor = sqlite3.Cursor(self.db)

        self.cursor.execute("""CREATE TABLE IF NOT EXISTS nodes (
            name VARCHAR(100) NOT NULL,
            known BOOLEAN NOT NULL,
            flagged BOOLEAN NOT NULL,
            confidence DOUBLE NOT NULL,
            activation DOUBLE NOT NULL,
            threshold DOUBLE NOT NULL
        );""")
        
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subj VARCHAR(100) NOT NULL,
            name VARCHAR(100) NOT NULL,
            obj VARCHAR(100) NOT NULL,
            weight DOUBLE NOT NULL,
            type VARCHAR(8) NOT NULL,
            last_fired VARCHAR(20) 
        );""")
    
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
                result["relations"] = []
            
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
                            for rel in node.getRelations():
                                self.cursor.execute("INSERT INTO relations (subj, name, obj, weight, type, last_fired) VALUES (?, ?, ?, ?, ?, ?);", (rel.getSubj(), rel.getName(), rel.getObj(), rel.getWeight(), rel.getRelType(), rel.getLastFired()))
                            self.cursor.execute("INSERT INTO nodes (name, known, flagged, confidence, activation, threshold) VALUES (?, ?, ?, ?, ?, ?);", (node.getName(), node.getKnown(), node.getFlagged(), node.getConfidence(), node.getActivation(), node.getThreshold()))
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
            return self.addNode(name)
    
    def addNode(self, name: str) -> Node:
        node = Node(name)
        self.nodes[name] = (node)
        self.saveNode(name)
        return node
    
    def saveNode(self, name: str) -> None:
        try:
            node = self.nodes[name]
            with open(os.path.join(self.name, name + ".md"), mode="w") as file:
                file.write(str(node))
                
            self.cursor.execute("UPDATE nodes SET known = ?, flagged = ?, confidence = ?, activation = ?, threshold = ? WHERE name == ?;", (node.getKnown(), node.getFlagged(), node.getConfidence(), node.getActivation(), node.getThreshold(), node.getName()))
            
        except Exception as e:
            self.err(f"Unexpected error while writing node '{name}': {e}")
        

    def getRelation(self, id: int) -> Relation:
        raw = self.cursor.execute("SELECT * FROM relations WHERE id == ?;", (id, )).fetchone()
        data = { "subj": raw[1], "name": raw[2], "obj": raw[3], "weight": raw[4], "type": raw[5], "last_fired": datetime.fromisoformat(raw[6]) }
        return Relation.fromJSON(data)


    def getRelations(self, node: Node) -> list[Relation]:
        rels = []
        name = node.getName()
        results = self.cursor.execute("SELECT id FROM relations WHERE subj == ? OR obj == ?;", (name, name)).fetchall()
        for result in results:
            rels.append(self.getRelation(result[0]))

        return rels
        

    def addActivation(self, name: str, act: float):
        for name_ in self.nodes:
            node = self.getNode(name_)
            node.setActivation(0.0)
            self.saveNode(node.getName())

        # Initialize the stack with the starting node and its activation
        stack = []
        stack.append((name, act))

        # Track nodes that have been processed in this activation cycle
        processed_nodes = set()

        while stack:
            current_name, current_act = stack.pop()

            # Skip if the node has already been processed in this cycle
            if current_name in processed_nodes:
                continue

            # Mark the node as processed
            processed_nodes.add(current_name)

            # Get or create the node
            node = self.getNode(current_name)

            # Update the node's activation
            node.setActivation(node.getActivation() + current_act)
            self.log(f"Updated activation for {current_name}: {node.getActivation()}")

            # Check if the node's activation exceeds its threshold
            if node.getActivation() >= node.getThreshold():
                # Process all relations for this node
                for rel in self.getRelations(node):
                    if rel.getRelType() == "ACTIVATES":
                        if rel.getSubj() == node.getName():
                            target_name = rel.getObj()
                            target_act = node.getActivation() * rel.getWeight()
                            self.log(f"Adding {target_act} activation to {target_name}")
                            stack.append((target_name, target_act))
                        else:
                            target_name = rel.getSubj()
                            target_act = node.getActivation() * rel.getWeight()
                            self.log(f"Adding {target_act} activation to {target_name}")
                            stack.append((target_name, target_act))
                    else:
                        if rel.getSubj() == node.getName():
                            target_name = rel.getObj()
                            target_act = node.getActivation() * rel.getWeight() * -1
                            self.log(f"Removing {abs(target_act)} activation from {target_name}")
                            stack.append((target_name, target_act))
                        else:
                            target_name = rel.getSubj()
                            target_act = node.getActivation() * rel.getWeight() * -1
                            self.log(f"Removing {abs(target_act)} activation from {target_name}")
                            stack.append((target_name, target_act))

                # Dampen the node's activation after processing
                node.setActivation(node.getActivation() * 0.8)
                self.saveNode(current_name)
    
    def getOutput(self) -> list[Node]:
        names = self.cursor.execute("SELECT name FROM nodes WHERE activation > 0.6 ORDER BY activation DESC;").fetchmany(25)
        nodes = [ self.getNode(name[0]) for name in names ] 
        return nodes

    
if __name__ == "__main__":
    model = Model("base", False)
    model.addActivation("Socratese", 1.0)
    for node in model.getOutput():
        print(node.getName())
