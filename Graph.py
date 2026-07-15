import json
import logging
import hashlib
import os
import sqlite3
import spacy
import traceback
from Config import Config
from datetime import datetime
from InputLLM import InputLLM
from Node import Node
from Relation import Relation
from pathlib import Path
from pyvis.network import Network

class Graph:
    """The core memory graph — manages nodes, relations, activation spreading, and persistence.

    Nodes represent concepts, relations represent weighted connections between them.
    Activation spreads through the network via strengthening or inhibiting relations.
    """

    def __init__(self, name: str, logger: logging.Logger, config: Config):
        """Initialize the Graph with a name, logger, and configuration.
        
        Args:
            name (str): The name of the graph.
            logger (logging.Logger): The logger for logging messages.
            config (Config): The configuration object for the application.
        """
        self.name = name
        self.nodes = {}
        self.fired_nodes = []
        self.stack = set()
        self.threshold = 0.5
        self.hop_limit = 2
        self.nlp = spacy.load("en_core_web_sm")

        self.setup_db()
        self.ensure_nodes()
        self.update_known()
        self.decay_relations()
        self.reduce_activation()
    
    def init_db(self):
        """Initialize the database connection and cursor."""
        xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        data_dir = os.path.join(xdg_data_home, "louis")
        os.makedirs(data_dir, exist_ok=True)
        
        self.db = sqlite3.connect(os.path.join(data_dir, "graph.sqlite"))
        self.db.isolation_level = None
        self.cursor = self.db.cursor()
        
    def close_db(self):
        """Close the database connection and cursor."""
        self.db.commit()
        self.cursor.close()
        self.db.close()

    def setup_db(self):
        """Initialize the temporary SQLite database for relation persistence.

        Recreates the database file on each run to ensure a clean slate.
        """
        
        self.init_db()

        self.cursor.execute("""CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            last_fired VARCHAR(20),
            last_decayed VARCHAR(20)
        );""")
        
        self.close_db()
    
    def log(self, text: str) -> None:
        """Log an informational debug message."""
        self.logger.debug(text)

    def warn(self, text: str) -> None:
        """Log a warning."""
        self.logger.warning(text)

    def err(self, text: str) -> None:
        """Log an error."""
        self.logger.error(text)

    def get_parent_node(self, node: Node) -> Node | None:
        """Walk direct is_a relations to find the parent (superclass) node."""
        
        self.init_db()

        name = node.get_name()
        results = self.cursor.execute(
            "SELECT subj, obj FROM relations WHERE name == 'is_a' AND (subj == ? OR obj == ?);",
            (name, name)
        ).fetchall()
        
        self.close_db()

        for row in results:
            subj = row[0]
            obj = row[1]
            parent_name = obj if subj == name else subj
            return self.get_node(parent_name)
        return None
    
    def ensure_nodes(self) -> None:
        """Ensure all nodes referenced in relations exist in the nodes table."""
        # Fetch all unique subj and obj values from relations that don't exist in nodes
        self.init_db()
        self.cursor.execute("""
            SELECT DISTINCT subj AS node_name FROM relations
            LEFT JOIN nodes ON relations.subj = nodes.name
            UNION
            SELECT DISTINCT obj AS node_name FROM relations
            LEFT JOIN nodes ON relations.obj = nodes.name
        """)
        nodes = [row[0] for row in self.cursor.fetchall()]
        
        self.close_db()

        # Create missing nodes
        for node_name in nodes:
            self.log(f"Loading node: {node_name}")
            self.get_node(node_name)

    def get_inherited_relations(self, node: Node) -> list[Relation]:
        """Walk the is_a chain and collect inherited relations with decaying weight per hop.

        Inherited relations are virtual — they are not stored or strengthened.
        Relations of name 'is_a' are never inherited.
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
                if rel.get_name() == "is_a":
                    continue
                inherited_rel = Relation(
                    rel.get_subj(), rel.get_name(), rel.get_obj(),
                    round(rel.get_weight() * discount, 4),
                    rel.get_last_fired()
                )
                inherited_relations.append(inherited_rel)
            current = parent
            hop += 1
        
        return inherited_relations

    def discover(self):
        """Scan the knowledge directory and load all markdown files as nodes."""
        self.nodes = {}
        self.init_db()

        for row in self.cursor.execute("SELECT * FROM nodes;").fetchall():
            node = Node.fromJSON({"name": row[0], "known": row[1] == "True", "confidence": row[2], "activation": row[3], "relations": []})
            for rel in self.get_direct_relations(node):
                node.add_relation(rel)
            self.nodes[node.get_name()] = node
        
        self.close_db()
            
    def get_node(self, name: str) -> Node:
        """Retrieve a node by name, creating it if it doesn't exist."""
        
        self.init_db()
        query_result = self.cursor.execute("SELECT name, known, confidence, activation FROM nodes WHERE name == ?;", (name,)).fetchone()
        self.close_db()

        if name in self.nodes:
            return self.nodes[name]

        elif query_result != None:
            node = Node.fromJSON({"name": query_result[0], "known": query_result[1] == "True", "confidence": query_result[2], "activation": query_result[3], "relations": []})
            self.nodes[name] = node
            return node

        self.log(f"Node '{name}' not found, creating new node.")
        return self.add_node(name)

    def add_node(self, name: str) -> Node:
        """Create a new node with default properties and persist it."""
        node = Node(name)
        self.nodes[name] = node
        
        self.init_db()
        self.cursor.execute("INSERT INTO nodes (name, known, confidence, activation) VALUES (?, ?, ?, ?);", (name, False, 0.0, 0.0))
        self.close_db()

        self.save_node(name)
        return node

    def decay_relations(self) -> None:
        """Apply exponential decay to all relation weights based on time since last decayed."""
        
        self.init_db()
        rows = self.cursor.execute("SELECT name FROM nodes;").fetchall()
        self.close_db()

        for row in rows:
            name = row[0]
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
            
        self.init_db()
        self.cursor.execute("UPDATE nodes SET activation = activation * 0.2;")
        self.close_db()

    def save_relation(self, rel: Relation) -> None:
        """Persist a relation's weight and last_fired to DB, sync to Node's in-memory list, then write markdown."""
        try:
            self.init_db()
            self.cursor.execute(
                "UPDATE relations SET weight = ?, last_fired = ?, last_decayed = ? WHERE subj == ? AND name == ? AND obj == ?;",
                (rel.get_weight(), rel.get_last_fired(), rel.get_last_decayed(), rel.get_subj(), rel.get_name(), rel.get_obj())
            )
            self.close_db()

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

            self.init_db()
            self.cursor.execute(
                "UPDATE nodes SET known = ?, confidence = ?, activation = ? WHERE name == ?;",
                (node.get_known(), node.get_confidence(),
                 node.get_activation(), node.get_name())
            )
        except Exception as e:
            self.err(f"Unexpected error while writing node '{name}': {e}")
        finally:
            self.close_db()

    def get_relation_by_id(self, relation_id: int) -> Relation:
        """Retrieve a relation by its database ID."""
        self.init_db()
        raw = self.cursor.execute("SELECT * FROM relations WHERE id == ?;", (relation_id,)).fetchone()
        self.close_db()

        if raw is None or raw == []:
            raise ValueError(f"Relation with id {relation_id} not found.")
        if len(raw) < 7:
            raise ValueError(f"Invalid relation data for id {relation_id}. Expected 7 columns, got {len(raw)}.")
        data = {
            "subj": raw[1], "name": raw[2], "obj": raw[3], "weight": raw[4],
            "last_fired": datetime.fromisoformat(raw[5]),
            "last_decayed": datetime.fromisoformat(raw[6])
        }
        return Relation.fromJSON(data)

    def get_direct_relations(self, node: Node) -> list[Relation]:
        """Return only direct (non-inherited) relations for a node from the database."""
        name = node.get_name()
        
        self.init_db()
        results = self.cursor.execute(
            "SELECT id FROM relations WHERE subj == ? OR obj == ? ORDER BY weight DESC;", (name, name)
        ).fetchall()
        self.close_db()

        rels = []
        for row in results:
            rels.append(self.get_relation_by_id(row[0]))

        return rels

    def get_relations(self, node: Node) -> list[Relation]:
        """Return all relations for a node — direct and inherited."""
        rels = self.get_direct_relations(node)
        rels.extend(self.get_inherited_relations(node))
        return rels

    def add_relation(self, subj: str, action: str, obj: str) -> None:
        """Create a new relation between two nodes and persist it."""
        now = datetime.now().isoformat()
        rel = Relation(subj, action, obj, 0.5, now, now)
        
        self.init_db()
        self.cursor.execute(
            "INSERT INTO relations (subj, name, obj, weight, last_fired, last_decayed) VALUES (?, ?, ?, ?, ?, ?);",
            (subj, action, obj, 0.5, now, now)
        )
        self.close_db()

        self.get_node(subj).add_relation(rel)
        self.save_relation(rel)
        
    def add_activation(self, name: str, activation_amount: float, erase: bool = True, intent: str = "DEFAULT"):
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
            self.log(f"Activation: {node.get_activation()}")
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
                    elif intent == "RELATE" and rel.get_name() not in ("is_a", "has", "has_property", "causes", "supports"):
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

        target_act = round(node.get_activation() * rel.get_weight(), 4)

        self.log(f"Propagating activation to {target_name}: {target_act}")
        self.stack.add((target_name, target_act, current_hop + 1))

        if not is_inherited:
            target = self.get_node(target_name)
            target_new_act = target.get_activation() + target_act
            self.log(f"Updating activation for {target_name}: {target.get_activation()} -> {target_new_act}")

            strengthened = target_new_act >= self.threshold

            rel.set_weight(round(rel.get_weight() * (1.005 if strengthened else 0.995), 4))
            rel.set_last_fired(datetime.now())
            self.save_relation(rel)

    def get_output(self) -> list[Node]:
        """Return the top 25 most activated nodes (activation > 0.5), sorted descending."""
        
        self.init_db()
        rows = self.cursor.execute(
            "SELECT name FROM nodes WHERE activation >= 0.5 ORDER BY activation DESC LIMIT 10;"
        ).fetchall()
        self.close_db()

        return [self.get_node(row[0]) for row in rows]

    def feed_input(self, subj: str, rel: str, obj: str, intent: str = "DEFAULT") -> None:
        subj = subj.lower().strip()
        rel = rel.lower().strip()
        obj = obj.lower().strip()

        self.stack.add((subj, 1.0, 0))
        self.stack.add((rel, 1.0, 0))
        self.add_activation(obj, 1.0, False, intent)

        self.init_db()
        row = self.cursor.execute(
            "SELECT id FROM relations WHERE subj = ? AND name = ? AND obj = ?;",
            (subj, rel, obj)
        ).fetchone()
        self.close_db()

        if row == None:
            self.add_relation(subj, rel, obj)
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

    def generate_graph_view(self):
        net = Network(height="900px", width="100%", directed=True,  bgcolor = "#222222", font_color = "white", select_menu=False, filter_menu=False)
        
        self.init_db()
        nodes = self.cursor.execute(
            """SELECT DISTINCT subj AS node_name FROM relations
            LEFT JOIN nodes ON relations.subj = nodes.name
            UNION
            SELECT DISTINCT obj AS node_name FROM relations
            LEFT JOIN nodes ON relations.obj = nodes.name;""").fetchall()
        
        edges = self.cursor.execute(
            """SELECT e.subj, e.name, e.obj, e.weight 
               FROM relations e
               WHERE e.subj IN (SELECT name FROM nodes ORDER BY activation DESC)
               AND e.obj IN (SELECT name FROM nodes ORDER BY activation DESC)""",
        ).fetchall()
        self.close_db()
        
        for name in [row[0] for row in nodes]:
            net.add_node(name, label=name, title=name)
        
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

        return "DEFAULT" 

    def query(self, text: str, intent: str = None):
        text = text.lower()
        
        if intent == None:
            intent = self.parse_intent(text)
        nodes = self.parse_nodes(text) or [text]
        
        self.log(f"Detected {intent} intent.")
        
        if len(nodes) == 0:
            return []
    
        for node in nodes[1:]:
            self.stack.add((node, 1.0, 0))
        
        self.add_activation(nodes[0], 1.0, False, intent)
        self.generate_graph_view()
    
    def parse_nodes(self, text: str) -> list[str]:
        text = text.lower()
        doc = self.nlp(text)
        nodes = []
        
        names = []
        for chunk in doc.noun_chunks:
            names.extend([token.text if token.ent_type_ or token.pos_ in ("PROPN", "NOUN") else token.lemma_  for token in doc])
        
        self.init_db()

        for word in names:
            for node in self.cursor.execute("SELECT name FROM nodes WHERE name == ?;", (word,)).fetchall():
                nodes.append(node[0]) 

        self.close_db()
        
        return nodes

    def write(self, text: str):
        text = text.lower()
        
        doc = self.nlp(text)
        
        for sentence in doc.sents:
            self.log(f"Processing sentence '{sentence.text}'")
            nodes = []
            
            for token in sentence:
                nodes.append(token.lemma_ if token.pos_ not in ("PROPN", "NOUN") and not token.ent_type_ else token.text)

            json_data = InputLLM(self.config.get_value("graph-model"), self.config.get_value("mistral_api_key")).send(f"Source Text: {sentence}\nLemmatized words: {nodes}")
            self.log(f"Extracted relations: {json_data}")
            self.parse_json(json_data)
        
        self.generate_graph_view()

    def generate_context(self) -> str:
        output_nodes = self.get_output()

        output_relations = set()
        for node in output_nodes:
            relations = sorted(self.get_relations(node), key=lambda x: x.get_weight(), reverse=True) if self.get_relations(node) else []
            for rel in relations:
                subj_node = self.get_node(rel.get_subj())
                obj_node = self.get_node(rel.get_obj())
                
                rel_text = f"{rel.get_subj()} --> {rel.get_name()} --> {rel.get_obj()}"
                if rel_text not in output_relations and rel.get_weight():
                    output_relations.add(rel_text)
                    
                if len(output_relations) == 10:
                    break

        context = (
            f"Nodes: {[n.get_name() for n in output_nodes]}\n"
            f"Relations: {output_relations}\n"
        )
        self.log(context) 
        
        return context
