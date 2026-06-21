import json
import logging
import hashlib
import os
import sqlite3
import traceback
from datetime import datetime
from Node import Node
from Relation import Relation
from pathlib import Path
from pyvis.network import Network

class Model:
    """The core cognitive model — manages nodes, relations, activation spreading, and persistence.

    Nodes represent concepts, relations represent weighted connections between them.
    Activation spreads through the network via strengthening or inhibiting relations.
    """

    def __init__(self, name: str, production: bool):
        self.name = name
        self.production = production
        self.nodes = {}
        self.fired_nodes = []
        self.stack = set()
        self.threshold = 0.5
        self.hop_limit = 2

        self.setup_logging()
        self.setup_db()

        #self.discover()
        self.update_known()
        self.decay_relations()
        self.reduce_activation()

    def setup_logging(self):
        """Initialize logging to timestamped files under logs/."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{log_dir}/{timestamp}.log"
        
        handlers = [logging.FileHandler(log_filename)]
        if self.production == False:
            handlers.append(logging.StreamHandler())

        logging.basicConfig(
            level=logging.DEBUG,
            format='[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=handlers
        )

        self.logger = logging.getLogger(__name__)

    def setup_db(self):
        """Initialize the temporary SQLite database for relation persistence.

        Recreates the database file on each run to ensure a clean slate.
        """
        db_path = "database.sqlite"
        self.db = sqlite3.connect(db_path)
        self.db.isolation_level = None
        self.cursor = self.db.cursor()

        self.cursor.execute("""CREATE TABLE IF NOT EXISTS nodes (
            name VARCHAR(100) NOT NULL,
            known BOOLEAN NOT NULL,
            confidence DOUBLE NOT NULL,
            activation DOUBLE NOT NULL
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
                result["known"] = line.removeprefix("Known: ") == "True"
            
            elif "Confidence: " in line:
                result["confidence"] = float(line.removeprefix("Confidence: "))
            elif "Activation: " in line:
                result["activation"] = float(line.removeprefix("Activation: "))
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

        required = ["name", "known", "confidence", "activation", "relations"]
        for prop in required:
            if prop not in result:
                raise RuntimeError(f"Missing required node property '{prop}' in markdown.")

        return result

    def get_parent_node(self, node: Node) -> Node | None:
        """Walk direct is_a relations to find the parent (superclass) node."""
        name = node.get_name()
        results = self.cursor.execute(
            "SELECT subj, obj FROM relations WHERE type == 'is_a' AND (subj == ? OR obj == ?);",
            (name, name)
        ).fetchall()
        for row in results:
            subj = row[0]
            obj = row[1]
            parent_name = obj if subj == name else subj
            return self.get_node(parent_name)
        return None

    def get_inherited_relations(self, node: Node) -> list[Relation]:
        """Walk the is_a chain and collect inherited relations with decaying weight per hop.

        Inherited relations are virtual — they are not stored or strengthened.
        Relations of type 'is_a' are never inherited.
        """
        inherited_relations = []
        hop = 1
        current = node
        visited = {node.get_name()}

        while current:
            parent = self.get_parent_node(current)
            if parent is None or parent.get_name() in visited:
                break
            visited.add(parent.get_name())
            discount = 0.8 ** hop
            parent_rels = self.get_direct_relations(parent)
            for rel in parent_rels:
                if rel.get_rel_type() == "is_a":
                    continue
                inherited_rel = Relation(
                    rel.get_subj(), rel.get_name(), rel.get_obj(),
                    round(rel.get_weight() * discount, 4),
                    rel.get_rel_type(), rel.get_last_fired()
                )
                inherited_relations.append(inherited_rel)
            current = parent
            hop += 1

        return inherited_relations

    def discover(self):
        """Scan the knowledge directory and load all markdown files as nodes."""
        self.nodes = {}

        for row in self.cursor.execute("SELECT * FROM nodes;").fetchall():
            node = Node.fromJSON({"name": row[0], "known": row[1] == "True", "confidence": row[2], "activation": row[3], "relations": []})
            for rel in self.get_direct_relations(node):
                node.add_relation(rel)
            self.nodes[node.get_name()] = node
            
    def get_node(self, name: str) -> Node:
        """Retrieve a node by name, creating it if it doesn't exist."""
        query_result = self.cursor.execute("SELECT * FROM nodes WHERE name == ?;", (name,)).fetchone()
        if name in self.nodes:
            return self.nodes[name]
        elif query_result != None:
            node = Node.fromJSON({"name": query_result[0], "known": query_result[1] == "True", "confidence": query_result[2], "activation": query_result[3], "relations": []})
            self.nodes[name] = node
            return node
        self.warn(f"Node '{name}' not found, creating new node.")
        return self.add_node(name)

    def add_node(self, name: str) -> Node:
        """Create a new node with default properties and persist it."""
        node = Node(name)
        self.nodes[name] = node
        self.cursor.execute("INSERT INTO nodes (name, known, confidence, activation) VALUES (?, ?, ?, ?);", (name, False, 0.0, 0.0))
        self.save_node(name)
        return node

    def decay_relations(self) -> None:
        """Apply exponential decay to all relation weights based on time since last decayed."""
        for name in self.nodes:
            node = self.get_node(name)
            for rel in self.get_relations(node):
                last_dec = rel.get_last_decayed()
                delta = datetime.now() - datetime.fromisoformat(last_dec)
                modifier = 0.999 ** delta.days
                rel.set_weight(rel.get_weight() * modifier)
                rel.set_last_decayed(datetime.now())
                self.save_relation(rel)

    def reduce_activation(self) -> None:
        """Dampen all node activations to 20% of their current value."""
        """for name in self.cursor.execute("SELECT name FROM nodes;").fetchall():
            node = self.get_node(name[0])
            #node.set_activation(node.get_activation() * 0.3)
            node.set_activation(0.0)
            self.save_node(node.get_name())"""
        self.cursor.execute("UPDATE nodes SET activation = 0;")

    def save_relation(self, rel: Relation) -> None:
        """Persist a relation's weight and last_fired to DB, sync to Node's in-memory list, then write markdown."""
        try:
            self.cursor.execute(
                "UPDATE relations SET weight = ?, last_fired = ?, last_decayed = ? WHERE subj == ? AND name == ? AND obj == ?;",
                (rel.get_weight(), rel.get_last_fired(), rel.get_last_decayed(), rel.get_subj(), rel.get_name(), rel.get_obj())
            )
            # Sync the relation back into the source Node's in-memory list
            for node_name in (rel.get_subj(), rel.get_obj()):
                    node = self.get_node(node_name)
                    for existing in node.get_relations():
                        if (existing.get_subj() == rel.get_subj()
                                and existing.get_name() == rel.get_name()
                                and existing.get_obj() == rel.get_obj()):
                            existing.set_weight(rel.get_weight())
                            existing.set_last_fired(rel.get_last_fired())
                            existing.set_last_decayed(rel.get_last_decayed())
                            break
            self.save_node(rel.get_subj())
            self.save_node(rel.get_obj())
        except Exception as e:
            self.err(f"Failed to save relation {rel.get_name()} ({rel.get_subj()} -> {rel.get_obj()}): {e}")

    def save_node(self, name: str) -> None:
        """Write a node's state to the database."""
        try:
            node = self.nodes[name]
            self.cursor.execute(
                "UPDATE nodes SET known = ?, confidence = ?, activation = ? WHERE name == ?;",
                (node.get_known(), node.get_confidence(),
                 node.get_activation(), node.get_name())
            )
        except Exception as e:
            self.err(f"Unexpected error while writing node '{name}': {e}")

    def get_relation_by_id(self, relation_id: int) -> Relation:
        """Retrieve a relation by its database ID."""
        raw = self.cursor.execute("SELECT * FROM relations WHERE id == ?;", (relation_id,)).fetchone()
        if raw is None:
            raise ValueError(f"Relation with id {relation_id} not found.")
        if len(raw) < 8:
            raise ValueError(f"Invalid relation data for id {relation_id}. Expected 8 columns, got {len(raw)}.")
        data = {
            "subj": raw[1], "name": raw[2], "obj": raw[3], "weight": raw[4],
            "type": raw[5], "last_fired": datetime.fromisoformat(raw[6]),
            "last_decayed": datetime.fromisoformat(raw[7])
        }
        return Relation.fromJSON(data)

    def get_direct_relations(self, node: Node) -> list[Relation]:
        """Return only direct (non-inherited) relations for a node from the database."""
        name = node.get_name()
        results = self.cursor.execute(
            "SELECT id FROM relations WHERE subj == ? OR obj == ?;", (name, name)
        ).fetchall()
        return [self.get_relation_by_id(row[0]) for row in results]

    def get_relations(self, node: Node) -> list[Relation]:
        """Return all relations for a node — direct and inherited."""
        rels = self.get_direct_relations(node)
        rels.extend(self.get_inherited_relations(node))
        return rels

    def add_relation(self, subj: str, action: str, obj: str, rel_type: str = "ACTIVATES") -> None:
        """Create a new relation between two nodes and persist it."""
        now = datetime.now().isoformat()
        rel = Relation(subj, action, obj, 0.5, rel_type, now, now)
        self.cursor.execute(
            "INSERT INTO relations (subj, name, obj, weight, type, last_fired, last_decayed) VALUES (?, ?, ?, ?, ?, ?, ?);",
            (subj, action, obj, 0.5, rel_type, now, now)
        )
        self.get_node(subj).add_relation(rel)
        self.save_relation(rel)
        
    def add_activation(self, name: str, activation_amount: float, erase: bool = True, intent: str = "UNKNOWN"):
        """Spread activation energy through the network via relations based on intent.

        Args:
            name: Starting node name.
            activation_amount: Activation amount to add.
            erase: Whether to clear existing stack and reset activations first.
            intent: The intent to guide activation spreading (WHO, WHAT, WHY, HOW, RELATE).
        """
        self.log(f"Activating {name}")

        if erase:
            self.stack = set()

        self.stack.add((name, activation_amount, 0))
        processed_nodes = set()

        while self.stack:
            current_name, current_act, current_hop = self.stack.pop()

            if current_hop > self.hop_limit:
                self.log("Max hop limit reached. Skipping node")
                continue

            if current_name in processed_nodes:
                self.log("Node already processed")
                continue
            processed_nodes.add(current_name)

            node = self.get_node(current_name)
            node.set_activation(node.get_activation() + current_act)
            self.save_node(current_name)

            if node.get_activation() >= self.threshold:
                self.direct_keys = {
                    (rel.get_subj(), rel.get_name(), rel.get_obj())
                    for rel in self.get_direct_relations(node)
                }

                self.seen_relations = set()
                for rel in self.get_relations(node):
                    self.log(f"Processing {str(rel)}")
                    # Filter relations based on intent
                    if intent == "WHO" and rel.get_name() != "is_a":
                        continue  # Only follow "is_a" relations for identity/hierarchy
                    elif intent == "WHAT" and rel.get_name() not in ("has", "has_property", "is_a"):
                        continue  # Only follow "has" or "has_property" relations for definitions/attributes
                    elif intent == "WHY" and rel.get_name() not in ("causes", "supports"):
                        continue  # Only follow "causes" or "supports" relations for causal/supporting edges
                    elif intent == "HOW" and current_hop >= 2:
                        continue  # Limit to multi-hop paths (e.g., 2 hops)
                    elif intent == "RELATE" and rel.get_name() in ("is_a", "has", "has_property", "causes", "supports"):
                        continue  # Focus on direct relations for shortest path search

                    self.strengthen_relation(node, rel, current_hop)

                self.save_node(current_name)

    def strengthen_relation(self, node: Node, rel: Relation, current_hop: int) -> None:
        """Propagate activation through a relation and optionally strengthen/weaken it.

        Args:
            node: The source node.
            rel: The relation to propagate through.
            current_hop: Current hop count.
        """
        self.log(f"Strenthening {str(rel)}")

        rel_key = (rel.get_subj(), rel.get_name(), rel.get_obj())
        if rel_key in self.seen_relations:
            return
        self.seen_relations.add(rel_key)

        is_inherited = rel_key not in self.direct_keys

        if rel.get_subj() == node.get_name():
            target_name = rel.get_obj()
        else:
            target_name = rel.get_subj()

        if rel.get_rel_type() == "ACTIVATES":
            target_act = round(node.get_activation() * rel.get_weight(), 4)
        else:
            target_act = round(node.get_activation() * rel.get_weight() * -1, 4)

        self.log(f"Propagating activation to {target_name}: {target_act}")
        self.stack.add((target_name, target_act, current_hop + 1))

        if not is_inherited:
            target = self.get_node(target_name)
            target_new_act = target.get_activation() + target_act
            self.log(f"Updating activation for {target_name}: {target.get_activation()} -> {target_new_act}")

            if rel.get_rel_type() == "ACTIVATES" or rel.get_rel_type() == "ACTIVATE":
                strengthened = target_new_act >= self.threshold
            else:
                strengthened = target_new_act < target.get_activation() * 0.8

            rel.set_weight(round(rel.get_weight() * (1.005 if strengthened else 0.995), 4))
            rel.set_last_fired(datetime.now())
            self.save_relation(rel)

    def get_output(self) -> list[Node]:
        """Return the top 25 most activated nodes (activation > 0.6), sorted descending."""
        rows = self.cursor.execute(
            "SELECT name FROM nodes WHERE activation > 0.5 ORDER BY activation DESC LIMIT 10;"
        ).fetchall()
        return [self.get_node(row[0]) for row in rows]

    def feed_input(self, subj: str, rel: str, obj: str, rel_type: str = "ACTIVATES", intent: str = "UNKNOWN") -> None:
        """Inject an input triple into the model and activate related nodes based on intent."""
        self.info("Feeding input...")
        #self.reduce_activation()

        subj = subj.lower().strip()
        rel = rel.lower().strip()
        obj = obj.lower().strip()
        rel_type = rel_type.upper().strip()

        self.stack.add((subj, 1.0, 0))
        self.stack.add((rel, 1.0, 0))
        self.add_activation(obj, 1.0, False, intent)
        self.nodes[subj].set_activation(1.0)
        self.nodes[obj].set_activation(1.0)

        row = self.cursor.execute(
            "SELECT id FROM relations WHERE subj = ? AND name = ? AND obj = ? AND type = ?;",
            (subj, rel, obj, rel_type)
        ).fetchone()

        if row == None:
            self.add_relation(subj, rel, obj, rel_type)
            relation_id = self.cursor.lastrowid
        else:
            relation_id = row[0]

        self.strengthen_relation(self.get_node(subj), self.get_relation_by_id(relation_id), 0)
        self.update_known()

    def parse_json(self, data: str) -> int:
        """Parse input from the InputLLM and feed it into the model.

        Returns 0 on success, -1 on failure.
        """
        self.log(data)
        
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                parsed = [parsed] 
            for entry in parsed:
                self.feed_input(
                    entry.get("subject", "").lower(),
                    entry.get("relation", "").lower(),
                    entry.get("object", "").lower()
                )
        except Exception as e:
            self.err(f"Failed to parse JSON - {e}\n{traceback.format_exc()}")
            return -1
        
        return 0

    def update_known(self) -> None:
        for node_name in self.nodes:
            node = self.get_node(node_name)
            if not node_name in ["is_a", "causes", "has", "has_property", "is_for", "inhibits"]:
                if len(self.get_relations(node)) > 0:
                    node.set_known(True)
                else:
                    node.set_known(False)
                node.set_confidence(min(len(self.get_relations(node)) / 5, 5.0))
            else:
                node.set_known(True)
                node.set_confidence(1.0)

            self.save_node(node_name)

    def generate_graph_view(self, limit=2000):
        net = Network(height="900px", width="100%", directed=True,  bgcolor = "#222222", font_color = "white", select_menu=True, filter_menu=True)
        
        nodes = self.cursor.execute(
            "SELECT name, activation FROM nodes ORDER BY activation DESC LIMIT ?", 
            (limit,)
        ).fetchall()
        
        edges = self.cursor.execute(
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
        
        net.save_graph("graph.html")
    
    def parse_intent(self, q: str) -> str:
        ql = q.lower()

        if ql.startswith("who is") or "who is" in ql:
            return "WHO"

        if ql.startswith("what is") or "define" in ql:
            return "WHAT"

        if ql.startswith("why"):
            return "WHY"

        if ql.startswith("how"):
            return "HOW"

        if "related" in ql or "relation" in ql:
            return "RELATE"

        return "UNKNOWN" 

    def query(self, text: str):
        text = text.lower()
        
        intent = self.parse_intent(text)
        nodes = self.parse_nodes(text)
        
        self.log(f"Detected {intent} intent.")
        
        if len(nodes) == 0:
            return []
    
        
        for node in nodes[1:]:
            self.stack.add((node, 1.0, 0))
        
        self.add_activation(nodes[0], 1.0, False, intent)
    
    def parse_nodes(self, text: str) -> list[str]:
        text = text.lower()
        nodes = []

        for word in text.split(" "):
            for node in self.cursor.execute("SELECT name FROM nodes WHERE name == ?;", (word,)).fetchall():
                nodes.append(node[0]) 
        
        return nodes

    def generate_context(self) -> str:
        output_nodes = self.get_output()

        output_relations = set()
        for node in output_nodes:
            for rel in self.get_relations(node):
                subj_node = self.get_node(rel.get_subj())
                obj_node = self.get_node(rel.get_obj())
                
                rel_text = f"{rel.get_subj()} --> {rel.get_name()} --> {rel.get_obj()} ({rel.get_rel_type()})" 
                if rel_text not in output_relations and (subj_node in output_nodes and obj_node in output_nodes):
                    output_relations.add(rel_text)

        context = (
            f"Nodes: {[n.get_name() for n in output_nodes]}\n"
            f"Relations: {output_relations}\n"
        )
        self.log(context) 
        
        return context
