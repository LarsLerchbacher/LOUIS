from datetime import datetime
import json
from InputLLM import InputLLM
import os
import logging
from OutputLLM import OutputLLM
import sqlite3

from Node import Node
from Relation import Relation


class Model:
    """The core cognitive model — manages nodes, relations, activation spreading, and persistence.

    Nodes represent concepts, relations represent weighted connections between them.
    Activation spreads through the network via strengthening or inhibiting relations.
    """

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
        """Initialize logging to timestamped files under logs/."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)

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
        """Initialize the temporary SQLite database for relation persistence.

        Recreates the database file on each run to ensure a clean slate.
        """
        db_path = "tmp.db"
        if os.path.exists(db_path):
            os.remove(db_path)
        self.db = sqlite3.connect(db_path)
        self.db.isolation_level = None
        self.cursor = self.db.cursor()

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
        """Log an informational debug message."""
        self.logger.debug(text)

    def warn(self, text: str) -> None:
        """Log a warning."""
        self.logger.warning(text)

    def err(self, text: str) -> None:
        """Log an error."""
        self.logger.error(text)
    
    def parse_markdown(self, markdown: str) -> dict:
        """Parse a markdown node file into a dictionary of node properties and relations.

        Expected format:
            # NodeName
            Known: True
            Flagged: False
            Confidence: 0.5
            Activation: 0.0
            Threshold: 0.5

            |Relation|Target|Weight|Type|Last Activated|Last Decayed|
            |---|---|---|---|---|---|
            |is_a|[[human]]|0.8|ACTIVATES|2025-01-01T00:00:00|2025-01-01T00:00:00|

        Raises RuntimeError if any required property is missing.
        """
        result = {}
        lines = [line.strip() for line in markdown.split("\n") if line.strip()]

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
            # Skip table header and separator rows
            elif "|Relation|Target|Weight|Type|Last Activated|Last Decayed|" in line:
                continue
            elif "|---|---|---|---|---|---|" in line:
                continue
            else:
                rel = {}
                line = line.removeprefix("|").removesuffix("|")
                parts = [p.strip() for p in line.split("|")]

                if len(parts) < 5:
                    self.err(f"Invalid relation at line {i}. Skipping.")
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
                        self.err(f"Invalid relation weight at line {i}. Skipping.")
                    elif "isoformat" in str(e):
                        self.err(f"Invalid relation timestamp at line {i}. Skipping.")
                    else:
                        self.err(f"Unexpected error parsing relation at line {i}: {e}")

        required = ["name", "known", "flagged", "confidence", "activation", "threshold", "relations"]
        for prop in required:
            if prop not in result:
                raise RuntimeError(f"Missing required node property '{prop}' in markdown.")

        return result

    
    def get_parent_node(self, node: Node) -> Node | None:
        """Walk direct is_a relations to find the parent (superclass) node."""
        name = node.getName()
        results = self.cursor.execute(
            "SELECT subj, obj FROM relations WHERE type == 'is_a' AND (subj == ? OR obj == ?);",
            (name, name)
        ).fetchall()
        for subj, obj in results:
            parent_name = obj if subj == name else subj
            return self.getNode(parent_name)
        return None

    def get_inherited_relations(self, node: Node) -> list[Relation]:
        """Walk the is_a chain and collect inherited relations with decaying weight per hop.

        Inherited relations are virtual — they are not stored or strengthened.
        Relations of type 'is_a' are never inherited.
        """
        inherited = []
        hop = 1
        current = node
        visited = {node.getName()}

        while current:
            parent = self.get_parent_node(current)
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
        """Scan the knowledge directory and load all markdown files as nodes.

        Each file is parsed into a Node and its relations are inserted into the database.
        Nodes are stored in memory and persisted to the SQLite database.
        """
        self.nodes = {}

        for filename in os.listdir(self.name):
            if filename.startswith("."):
                continue
            filepath = os.path.join(self.name, filename)
            try:
                with open(filepath, encoding="utf-8") as file:
                    content = file.read()
                try:
                    data = self.parse_markdown(content)
                    node = Node.fromJSON(data)
                    self.nodes[node.getName()] = node
                    for rel in node.getRelations():
                        self.cursor.execute(
                            "INSERT INTO relations (subj, name, obj, weight, type, last_fired, last_decayed) VALUES (?, ?, ?, ?, ?, ?, ?);",
                            (rel.getSubj(), rel.getName(), rel.getObj(), rel.getWeight(),
                             rel.getRelType(), rel.getLastFired(), rel.getLastDecayed())
                        )
                    self.cursor.execute(
                        "INSERT INTO nodes (name, known, flagged, confidence, activation, threshold) VALUES (?, ?, ?, ?, ?, ?);",
                        (node.getName(), node.getKnown(), node.getFlagged(),
                         node.getConfidence(), node.getActivation(), node.getThreshold())
                    )
                    self.log(f"Loaded node: {node.getName()}")
                except RuntimeError as e:
                    self.err(f"Failed to parse {filename}: {e}")
            except Exception as e:
                self.err(f"Failed to read {filename}: {e}")
    

    def getNode(self, name: str) -> Node:
        """Retrieve a node by name, creating it if it doesn't exist."""
        if name in self.nodes:
            return self.nodes[name]
        self.warn(f"Node '{name}' not found, creating new node.")
        return self.addNode(name)

    def addNode(self, name: str) -> Node:
        """Create a new node with default properties and persist it."""
        node = Node(name)
        self.nodes[name] = node
        self.saveNode(name)
        return node

    def decayRelations(self) -> None:
        """Apply exponential decay to all relation weights based on time since last decayed."""
        for name in self.nodes:
            node = self.getNode(name)
            for rel in self.getRelations(node):
                last_dec = rel.getLastDecayed()
                delta = datetime.now() - datetime.fromisoformat(last_dec)
                modifier = 0.999 ** delta.days
                rel.setWeight(rel.getWeight() * modifier)
                rel.setLastDecayed(datetime.now())
                self.saveRelation(rel)

    def reduceActivation(self) -> None:
        """Dampen all node activations to 20% of their current value."""
        for name in self.nodes:
            node = self.getNode(name)
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
        """Write a node's state to its markdown file and update the database."""
        try:
            node = self.nodes[name]
            with open(os.path.join(self.name, name + ".md"), "w", encoding="utf-8") as file:
                file.write(str(node))

            self.cursor.execute(
                "UPDATE nodes SET known = ?, flagged = ?, confidence = ?, activation = ?, threshold = ? WHERE name == ?;",
                (node.getKnown(), node.getFlagged(), node.getConfidence(),
                 node.getActivation(), node.getThreshold(), node.getName())
            )
        except Exception as e:
            self.err(f"Unexpected error while writing node '{name}': {e}")

    def getRelation(self, relation_id: int) -> Relation:
        """Retrieve a relation by its database ID."""
        raw = self.cursor.execute("SELECT * FROM relations WHERE id == ?;", (relation_id,)).fetchone()
        if raw is None:
            raise ValueError(f"Relation with id {relation_id} not found.")
        data = {
            "subj": raw[1], "name": raw[2], "obj": raw[3], "weight": raw[4],
            "type": raw[5], "last_fired": datetime.fromisoformat(raw[6]),
            "last_decayed": datetime.fromisoformat(raw[7])
        }
        return Relation.fromJSON(data)

    def getDirectRelations(self, node: Node) -> list[Relation]:
        """Return only direct (non-inherited) relations for a node from the database."""
        name = node.getName()
        results = self.cursor.execute(
            "SELECT id FROM relations WHERE subj == ? OR obj == ?;", (name, name)
        ).fetchall()
        return [self.getRelation(row[0]) for row in results]

    def getRelations(self, node: Node) -> list[Relation]:
        """Return all relations for a node — direct and inherited."""
        rels = self.getDirectRelations(node)
        rels.extend(self.get_inherited_relations(node))
        return rels

    def addRelation(self, subj: str, action: str, obj: str, rel_type: str = "ACTIVATES") -> None:
        """Create a new relation between two nodes and persist it."""
        now = datetime.now().isoformat()
        rel = Relation(subj, action, obj, 0.5, rel_type, now, now)
        self.cursor.execute(
            "INSERT INTO relations (subj, name, obj, weight, type, last_fired, last_decayed) VALUES (?, ?, ?, ?, ?, ?, ?);",
            (subj, action, obj, 0.5, rel_type, now, now)
        )
        self.getNode(subj).addRelation(rel)
        self.saveRelation(rel)
        

    def addActivation(self, name: str, act: float, erase: bool = True):
        """Spread activation energy through the network via relations.

        Starts from a named node, walks activating/inhibiting connections,
        and strengthens or weakens direct relations based on whether their
        targets reach threshold.

        Args:
            name: Starting node name.
            act: Activation amount to add.
            erase: Whether to clear existing stack and reset activations first.
        """
        if erase:
            self.stack = set()
            self.reduceActivation()

        self.stack.add((name, act))
        processed_nodes = set()

        while self.stack:
            current_name, current_act = self.stack.pop()

            if current_name in processed_nodes:
                continue
            processed_nodes.add(current_name)

            node = self.getNode(current_name)
            node.setActivation(node.getActivation() + current_act)

            if node.getActivation() >= node.getThreshold():
                self.direct_keys = {
                    (rel.getSubj(), rel.getName(), rel.getObj())
                    for rel in self.getDirectRelations(node)
                }

                self.seen_rels = set()
                for rel in self.getRelations(node):
                    self._strengthen_rel(node, rel)

                node.setActivation(node.getActivation() * 0.8)
                self.saveNode(current_name)

    def _strengthen_rel(self, node: Node, rel: Relation) -> None:
        """Propagate activation through a relation and optionally strengthen/weaken it.

        Inherited relations propagate activation but are never strengthened.
        """
        rel_key = (rel.getSubj(), rel.getName(), rel.getObj())
        if rel_key in self.seen_rels:
            return
        self.seen_rels.add(rel_key)

        is_inherited = rel_key not in self.direct_keys

        if rel.getSubj() == node.getName():
            target_name = rel.getObj()
        else:
            target_name = rel.getSubj()

        if rel.getRelType() == "ACTIVATES":
            target_act = round(node.getActivation() * rel.getWeight(), 4)
        else:
            target_act = round(node.getActivation() * rel.getWeight() * -1, 4)

        self.stack.add((target_name, target_act))

        if not is_inherited:
            target = self.getNode(target_name)
            target_new_act = target.getActivation() + target_act

            if rel.getRelType() == "ACTIVATES":
                strengthened = target_new_act >= target.getThreshold()
            else:
                strengthened = target_new_act < target.getActivation() * 0.8

            rel.setWeight(round(rel.getWeight() * (1.005 if strengthened else 0.995), 4))
            rel.setLastFired(datetime.now())
            self.saveRelation(rel)

    def getOutput(self) -> list[Node]:
        """Return the top 25 most activated nodes (activation > 0.6), sorted descending."""
        rows = self.cursor.execute(
            "SELECT name FROM nodes WHERE activation > 0.6 ORDER BY activation DESC LIMIT 25;"
        ).fetchall()
        return [self.getNode(row[0]) for row in rows]

    def feedInput(self, subj: str, rel: str, obj: str, rel_type: str = "ACTIVATES") -> None:
        """Inject an input triple into the model and activate related nodes."""
        self.stack.add((subj, 1.0))
        self.stack.add((rel, 1.0))
        self.addActivation(obj, 1.0, False)

        row = self.cursor.execute(
            "SELECT id FROM relations WHERE subj = ? AND name = ? AND obj = ? AND type = ?;",
            (subj, rel, obj, rel_type)
        ).fetchone()

        if row is None:
            self.addRelation(subj, rel, obj, rel_type)
            relation_id = self.cursor.lastrowid
        else:
            relation_id = row[0]

        self._strengthen_rel(self.getNode(subj), self.getRelation(relation_id))

    def parseJSON(self, data: str) -> int:
        """Parse input from the InputLLM and feed it into the model.

        Returns 0 on success, -1 on failure.
        """
        self.log(data)
        parsed = json.loads(data)

        try:
            for mod in parsed.get("modifiers", []):
                if mod not in (parsed["subject"], parsed["action"], parsed["object"]):
                    self.stack.add((mod, 0.5))
            for token in parsed.get("tokens", []):
                if token not in (parsed["subject"], parsed["action"], parsed["object"]):
                    self.stack.add((token, 0.3))

            self.feedInput(parsed["subject"], parsed["action"], parsed["object"], parsed["effect"])
            return 0
        except KeyError as e:
            self.err(f"Failed to parse JSON data — missing key: {e}")
            return -1


if __name__ == "__main__":
    message = "Socratese is a Human."

    model = Model("base", False)
    input_llm = InputLLM("lfm2.5", model.name)
    output_llm = OutputLLM("lfm2.5", model.name)

    if model.parseJSON(input_llm.send(message)) == 0:
        output_nodes = model.getOutput()

        output_relations = []
        for node in output_nodes:
            for rel in model.getRelations(node):
                subj_node = model.getNode(rel.getSubj())
                obj_node = model.getNode(rel.getObj())
                if subj_node in output_nodes and obj_node in output_nodes:
                    output_relations.append(
                        f"{rel.getSubj()} --> {rel.getName()} --> {rel.getObj()} ({rel.getRelType()})"
                    )

        context = (
            f"Input: {message}\n"
            f"Activated concepts: {[n.getName() for n in output_nodes]}\n"
            f"Relations between concepts: {output_relations}"
        )
        model.log(context)
        response = output_llm.send(context)
        print(response)
