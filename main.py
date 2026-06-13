from datetime import datetime
import json
from InputLLM import InputLLM
import re
import os
import logging
from LLM import LLM
from OutputLLM import OutputLLM
import sqlite3

from Node import Node
from Relation import Relation


class Model():
    def __init__(self, name: str, production: bool):
        self.name = name
        self.production = production
        self.nodes = {}
        self.firedNodes = []
        self.stack = set()

        self.setup_logging()
        self.setup_db()
        
        self.discover()
        self.decayRelations()
        self.reduceActivation()
    
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
            last_fired VARCHAR(20),
            last_decayed VARCHAR(20)
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
            elif "|Relation|Target|Weight|Type|Last Activated|Last Decayed" in line or "|---|---|---|---|---|---|" in line:
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
                    rel["last_decayed"] = datetime.fromisoformat(parts[5])
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

    
    def getParentNode(self, node: Node) -> Node | None:
        """Walk direct is_a relations to find the parent node."""
        name = node.getName()
        results = self.cursor.execute("SELECT subj, obj FROM relations WHERE type == 'is_a' AND (subj == ? OR obj == ?);", (name, name)).fetchall()
        for subj, obj in results:
            parent_name = obj if subj == name else subj
            return self.getNode(parent_name)
        return None

    def getInheritedRelations(self, node: Node) -> list[Relation]:
        """Walk the is_a chain and collect inherited relations with weight decaSocratese is a humany per hop.
        Only inherits relations that aren't already direct relations on the node."""
        inherited = []
        hop = 1
        current = node
        visited = {node.getName()}
        while current:
            parent = self.getParentNode(current)
            if parent is None or parent.getName() in visited:
                break
            visited.add(parent.getName())
            discount = 0.8 ** hop
            parent_rels = self.getDirectRelations(parent)
            for rel in parent_rels:
                if rel.getRelType() == "is_a":
                    continue
                inherited_rel = Relation(
                    rel.getSubj(), rel.getName(), rel.getObj(),
                    round(rel.getWeight() * discount, 4),
                    rel.getRelType(), rel.getLastFired()
                )
                inherited.append(inherited_rel)
            current = parent
            hop += 1
        return inherited

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
                                self.cursor.execute("INSERT INTO relations (subj, name, obj, weight, type, last_fired, last_decayed) VALUES (?, ?, ?, ?, ?, ?, ?);", (rel.getSubj(), rel.getName(), rel.getObj(), rel.getWeight(), rel.getRelType(), rel.getLastFired(), rel.getLastDecayed()))
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

    def decayRelations(self) -> None:
        for name in self.nodes:
            node = self.getNode(name)
            for rel in self.getRelations(node):
                lastDec = rel.getLastDecayed()
                delta = datetime.now() - datetime.fromisoformat(lastDec)
                modifier = 0.999 ** delta.days
                rel.setWeight(rel.getWeight() * modifier)
                rel.setLastDecayed(datetime.now())
                self.saveRelation(rel)

    def reduceActivation(self) -> None:
        for name_ in self.nodes:
            node = self.getNode(name_)
            node.setActivation(node.getActivation() * 0.2)
            self.saveNode(node.getName())

    
    def saveRelation(self, rel: Relation) -> None:
        """Persist a relation's weight and last_fired to DB, sync to Node's in-memory list, then write markdown."""
        try:
            self.cursor.execute(
                "UPDATE relations SET weight = ?, last_fired = ?, last_decayed = ? WHERE subj == ? AND name == ? AND obj == ?;",
                (rel.getWeight(), rel.getLastFired(), rel.getLastDecayed(), rel.getSubj(), rel.getName(), rel.getObj())
            )
            # Sync the relation back into the source Node's in-memory list
            for node_name in (rel.getSubj(), rel.getObj()):
                if node_name in self.nodes:
                    node = self.nodes[node_name]
                    for existing in node.getRelations():
                        if (existing.getSubj() == rel.getSubj()
                                and existing.getName() == rel.getName()
                                and existing.getObj() == rel.getObj()):
                            existing.setWeight(rel.getWeight())
                            existing.setLastFired(rel.getLastFired())
                            existing.setLastDecayed(rel.getLastDecayed())
                            break
            self.saveNode(rel.getSubj())
            self.saveNode(rel.getObj())
        except Exception as e:
            self.err(f"Failed to save relation {rel.getName()} ({rel.getSubj()} -> {rel.getObj()}): {e}")

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
        data = { "subj": raw[1], "name": raw[2], "obj": raw[3], "weight": raw[4], "type": raw[5], "last_fired": datetime.fromisoformat(raw[6]), "last_decayed": datetime.fromisoformat(raw[7]) }
        return Relation.fromJSON(data)


    def getDirectRelations(self, node: Node) -> list[Relation]:
        """Returns only direct (non-inherited) relations from DB."""
        rels = []
        name = node.getName()
        results = self.cursor.execute("SELECT id FROM relations WHERE subj == ? OR obj == ?;", (name, name)).fetchall()
        for result in results:
            rels.append(self.getRelation(result[0]))
        return rels

    def getRelations(self, node: Node) -> list[Relation]:
        """Returns direct + inherited relations for a node."""
        rels = self.getDirectRelations(node)

        inherited = self.getInheritedRelations(node)
        rels.extend(inherited)

        return rels

    def addRelation(self, subj: str, action: str, obj: str, rel_type: str = "ACTIVATES") -> None:
        rel = Relation(subj, action, obj, 0.5, rel_type, datetime.now().isoformat(), datetime.now().isoformat())
        self.cursor.execute("INSERT INTO relations (subj, name, obj, weight, type, last_fired, last_decayed) VALUES (?, ?, ?, ?, ?, ?, ?);", (subj, action, obj, 0.5, rel_type, rel.getLastFired(), rel.getLastDecayed()))
        self.getNode(subj).addRelation(rel)
        self.saveRelation(rel)
        

    def addActivation(self, name: str, act: float, erase: bool = True):
        # Initialize the stack with the starting node and its activation
        if erase:
            self.stack = set()
            self.reduceActivation()
        
        self.stack.add((name, act))

        # Track nodes that have been processed in this activation cycle
        processed_nodes = set()

        while self.stack:
            current_name, current_act = self.stack.pop()

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
                # Build set of direct relation keys for this node
                self.direct_keys = set()
                for direct_rel in self.getDirectRelations(node):
                    self.direct_keys.add((direct_rel.getSubj(), direct_rel.getName(), direct_rel.getObj()))

                # Process all relations for this node (direct + inherited)
                self.seen_rels = set()
                for rel in self.getRelations(node):
                    self.strengthenRel(node, rel)

                # Dampen the node's activation after processing
                node.setActivation(node.getActivation() * 0.8)
                self.saveNode(current_name)
    
    def strengthenRel(self, node: Node, rel: Relation) -> None:
        rel_key = (rel.getSubj(), rel.getName(), rel.getObj())
        if rel_key in self.seen_rels:
            return
        self.seen_rels.add(rel_key)

        is_inherited = rel_key not in self.direct_keys
        if rel.getRelType() == "ACTIVATES":
            if rel.getSubj() == node.getName():
                target_name = rel.getObj()
                target_act = round(node.getActivation() * rel.getWeight(), 4)
                self.log(f"Adding {target_act} activation to {target_name}")
                self.stack.add((target_name, target_act))
            else:
                target_name = rel.getSubj()
                target_act = round(node.getActivation() * rel.getWeight(), 4)
                self.log(f"Adding {target_act} activation to {target_name}")
                self.stack.add((target_name, target_act))
            
            target = self.getNode(target_name)
            if not is_inherited:
                target_new_act = target.getActivation() + target_act
                if target_new_act >= target.getThreshold():
                    rel.setWeight(rel.getWeight() * 1.005)
                else:
                    rel.setWeight(rel.getWeight() * 0.995)
                rel.setLastFired(datetime.now())
                self.saveRelation(rel)

        else:
            if rel.getSubj() == node.getName():
                target_name = rel.getObj()
                target_act = round(node.getActivation() * rel.getWeight() * -1, 4)
                self.log(f"Removing {abs(target_act)} activation from {target_name}")
                self.stack.add((target_name, target_act))
            else:
                target_name = rel.getSubj()
                target_act = round(node.getActivation() * rel.getWeight() * -1, 4)
                self.log(f"Removing {abs(target_act)} activation from {target_name}")
                self.stack.add((target_name, target_act))
            
            target = self.getNode(target_name)
            if not is_inherited:
                target_new_act = target.getActivation() + target_act
                dampened_act = target.getActivation() * 0.8
                if target_new_act < dampened_act:
                    rel.setWeight(rel.getWeight() * 1.005)
                else:
                    rel.setWeight(rel.getWeight() * 0.995)
                rel.setLastFired(datetime.now())
                self.saveRelation(rel) 

    def getOutput(self) -> list[Node]:
        names = self.cursor.execute("SELECT name FROM nodes WHERE activation > 0.6 ORDER BY activation DESC;").fetchmany(25)
        nodes = [ self.getNode(name[0]) for name in names ] 
        return nodes

    
    def feedInput(self, subj: str, rel: str, obj: str, rel_type: str = "ACTIVATES") -> None:
        self.stack.add((subj, 1.0))
        self.stack.add((rel, 1.0))
        self.addActivation(obj, 1.0, False)
        
        id = self.cursor.execute("SELECT id FROM relations WHERE subj = ? AND name = ? AND obj = ? AND type = ?;", (subj, rel, obj, rel_type)).fetchone()[0]
        if id == None:
            self.addRelation(subj, rel, obj, rel_type)
            id = self.cursor.lastrowid
        self.strengthenRel(self.getNode(subj), self.getRelation(id))

    def parseJSON(self, data: str) -> int:
        self.log(data)
        data = json.loads(data)
        try:
            for mod in data["modifiers"]:
                if mod != data["subject"] and mod != data["action"] and mod != data["object"]:
                    self.stack.add((mod, 0.5))
            for node in data["tokens"]:
                if node != data["subject"] and node != data["action"] and node != data["object"]:
                    self.stack.add((node, 0.3))
            self.feedInput(data["subject"], data["action"], data["object"], data["effect"])

            return 0
        except KeyError as e:
            self.err("Failed to parse JSON data. Model returend an invalid response. Aborting turn!")
            self.err(e)
            return -1

    
if __name__ == "__main__":
    message = "Socratese is a Human."

    model = Model("base", False)
    inLLM = InputLLM("lfm2.5", model.name)
    OutLLM = OutputLLM("lfm2.5", model.name)

    
    if model.parseJSON(inLLM.send(message)) == 0:
        output = model.getOutput()
        outRels = []
        for node in output:
            model.log(node.getName())
            for rel in model.getRelations(node):
                if model.getNode(rel.getSubj()) in output and model.getNode(rel.getObj()) in output:
                    outRels.append(f"{rel.getSubj()} --> {rel.getName()} --> {rel.getObj()} ({rel.getRelType()})")
        model.log(outRels)
        outMessage = "Input: " + message + "\nOutput: " + str([node.getName() for node in output]) + "\nRelations between output nodes: " + str(outRels) 
        model.log(outMessage)
        response = OutLLM.send(outMessage)
        print(response)
