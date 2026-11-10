"""
	This file is part of LOUIS
	LOUIS is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
	LOUIS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details
	
	You should have received a copy of the GNU Affero General Public License along with LOUIS. If not, see <https://www.gnu.org/licenses/>.
"""
 
import json
import logging
import hashlib
import os
import sqlite3
import spacy
import traceback
from threading import local
from Config import Config
from contextlib import contextmanager
from datetime import datetime
from InputLLM import InputLLM
from Node import Node
from Relation import Relation
from pathlib import Path
from pyvis.network import Network


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Graph(metaclass=Singleton):
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
        if hasattr(self, 'initialized'):
            return
        self.initialized = True

        self.name = name
        self.nodes = {}
        self.logger = logger
        self.config = config
        self.fired_nodes = []
        self.stack = set()
        self.threshold = 0.5
        self.hop_limit = 2
        self.nlp = spacy.load("en_core_web_sm")
        
        self.thread_local = local()


        self.setup_db()
        #self.ensure_nodes()
        self.decay_relations()
        self.reduce_activation()
    
    def init_db(self):
        """Initialize the database connection and cursor for the current thread."""
        if not hasattr(self.thread_local, 'db'):
            xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
            data_dir = os.path.join(xdg_data_home, "louis")
            os.makedirs(data_dir, exist_ok=True)

            self.thread_local.db = sqlite3.connect(
                os.path.join(data_dir, "graph.sqlite"),
                check_same_thread=False,
                isolation_level=None
            )
            self.thread_local.cursor = self.thread_local.db.cursor()
        
    def close_db(self):
        """Close the database connection and cursor for the current thread."""
        if hasattr(self.thread_local, 'db'):
            self.thread_local.db.commit()
            self.thread_local.cursor.close()
            self.thread_local.db.close()
            del self.thread_local.db
            del self.thread_local.cursor
    
    @contextmanager
    def db_session(self):
        """Context manager for thread-safe database operations."""
        self.init_db()  # Ensure the connection is initialized for this thread
        try:
            yield self.thread_local.cursor
            self.thread_local.db.commit()
        except Exception as e:
            self.thread_local.db.rollback()
            self.err(f"Database operation failed: {e}")
            raise
        finally:
            self.close_db()

    def setup_db(self):
        """Initialize the temporary SQLite database for relation persistence.

        Recreates the database file on each run to ensure a clean slate.
        """
        
        with self.db_session() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                activation DOUBLE NOT NULL
            );""")
            
            cursor.execute("""CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subj VARCHAR(100) NOT NULL,
                name VARCHAR(100) NOT NULL,
                obj VARCHAR(100) NOT NULL,
                weight DOUBLE NOT NULL,
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

    def get_parent_node(self, node: Node) -> Node | None:
        """Walk direct is_a relations to find the parent (superclass) node."""
        
        with self.db_session() as cursor:
            name = node.get_name()
            results = cursor.execute(
                "SELECT subj, obj FROM relations WHERE name == 'is_a' AND (subj == ? OR obj == ?);",
                (name, name)
            ).fetchall()

        for row in results:
            subj = row[0]
            obj = row[1]
            parent_name = obj if subj == name else subj
            return self.get_node(parent_name)
        return None
    
    def ensure_nodes(self) -> None:
        """Ensure all nodes referenced in relations exist in the nodes table."""
        # Fetch all unique subj and obj values from relations that don't exist in nodes
        with self.db_session() as cursor:
            cursor.execute("""
                SELECT DISTINCT subj AS node_name FROM relations
                LEFT JOIN nodes ON relations.subj = nodes.name
                UNION
                SELECT DISTINCT obj AS node_name FROM relations
                LEFT JOIN nodes ON relations.obj = nodes.name
            """)
            nodes = [row[0] for row in cursor.fetchall()]

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
                )
                inherited_relations.append(inherited_rel)
            current = parent
            hop += 1
        
        return inherited_relations
            
    def get_node(self, name: str) -> Node:
        """Retrieve a node by name, creating it if it doesn't exist."""
        
        if name in self.nodes:
            return self.nodes[name]

        else:
            with self.db_session() as cursor:
                query_result = cursor.execute("SELECT name, activation FROM nodes WHERE name == ?;", (name,)).fetchone()
                
            if query_result != None:
                node = Node.fromJSON({"name": query_result[0], "activation": query_result[1], "relations": []})
                self.nodes[name] = node
                return node

        self.log(f"Node '{name}' not found, creating new node.")
        return self.add_node(name)

    def add_node(self, name: str) -> Node:
        """Create a new node with default properties and persist it."""
        node = Node(name)
        self.nodes[name] = node
        
        with self.db_session() as cursor:
            cursor.execute("INSERT INTO nodes (name, activation) VALUES (?, ?);", (name, 0.0))

        self.save_node(name)
        return node

    def decay_relations(self) -> None:
        """Apply exponential decay to all relation weights based on time since last decayed."""
        with self.db_session() as cursor:
            cursor.execute("UPDATE relations SET weight = weight * POW(0.999, julianday('now') - julianday(COALESCE(DATETIME(last_decayed), 'now'))), last_decayed = datetime('now');")

    def reduce_activation(self) -> None:
        """Dampen all node activations to 20% of their current value."""
        with self.db_session() as cursor:
            cursor.execute("UPDATE nodes SET activation = activation * 0.5;")

    def save_relation(self, rel: Relation) -> None:
        """Persist a relation's weight and last_decayed value to DB, sync to Node's in-memory list, then write markdown."""
        try:
            with self.db_session() as cursor:
                cursor.execute(
                    "UPDATE relations SET weight = ? WHERE subj == ? AND name == ? AND obj == ?;",
                    (rel.get_weight(), rel.get_subj(), rel.get_name(), rel.get_obj())
                )

            # Sync the relation back into the source Node's in-memory list
            for node_name in (rel.get_subj(), rel.get_obj()):
                    node = self.get_node(node_name)
                    for existing in node.get_relations():
                        if (existing.get_subj() == rel.get_subj()
                                and existing.get_name() == rel.get_name()
                                and existing.get_obj() == rel.get_obj()):
                            existing.set_weight(rel.get_weight())
                            break
            self.save_node(rel.get_subj())
            self.save_node(rel.get_obj())
        except Exception as e:
            self.err(f"Failed to save relation {rel.get_name()} ({rel.get_subj()} -> {rel.get_obj()}): {e}")

    def save_relations_batch(self, relations: list[Relation]) -> None:
        """Persist a list of relations to the database in a batch operation."""
        if not relations:
            return
        
        with self.db_session() as cursor:
            try:
                for rel in relations:
                    cursor.execute(
                        "UPDATE relations SET weight = ? WHERE subj == ? AND name == ? AND obj == ?;",
                        (rel.get_weight(), rel.get_subj(), rel.get_name(), rel.get_obj())
                    )
            except Exception as e:
                self.err(f"Failed to save relations batch: {e}")
                raise

    def save_nodes_batch(self, node_names: list[str]) -> None:
        """Persist a list of nodes to the database in a batch operation."""
        if not node_names:
            return
        
        with self.db_session() as cursor:
            try:
                for name in node_names:
                    node = self.get_node(name)
                    cursor.execute(
                        "UPDATE nodes SET activation = ? WHERE name == ?;",
                        (node.get_activation(), node.get_name())
                    )
            except Exception as e:
                self.err(f"Failed to save nodes batch: {e}")
                raise

    def save_node(self, name: str) -> None:
        """Write a node's state to the database."""
        try:
            node = self.get_node(name)

            with self.db_session() as cursor:
                cursor.execute(
                    "UPDATE nodes SET activation = ? WHERE name == ?;",
                    (node.get_activation(), node.get_name())
                )
        except Exception as e:
            self.err(f"Unexpected error while writing node '{name}': {e}")

    def get_relation_by_id(self, relation_id: int) -> Relation:
        """Retrieve a relation by its database ID."""
        with self.db_session() as cursor:
            raw = cursor.execute("SELECT subj, name, obj, weight FROM relations WHERE id == ?;", (relation_id,)).fetchone()

        if raw is None or raw == []:
            raise ValueError(f"Relation with id {relation_id} not found.")
        if len(raw) < 4:
            raise ValueError(f"Invalid relation data for id {relation_id}. Expected 4 columns, got {len(raw)}.")
        data = {
            "subj": raw[0], "name": raw[1], "obj": raw[2], "weight": raw[3],
        }
        return Relation.fromJSON(data)

    def get_direct_relations(self, node: Node) -> list[Relation]:
        """Return only direct (non-inherited) relations for a node from the database."""
        name = node.get_name()
        
        with self.db_session() as cursor:
            results = cursor.execute(
                "SELECT id FROM relations WHERE subj == ? OR obj == ? ORDER BY weight DESC;", (name, name)
            ).fetchall()

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
        
        with self.db_session() as cursor:
            cursor.execute(
                "INSERT INTO relations (subj, name, obj, weight, last_decayed) VALUES (?, ?, ?, ?, DATETIME('now'));",
                (subj, action, obj, 0.5)
            )

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
        relations_to_save = []

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

                    self.strengthen_relation(node, rel, current_hop, relations_to_save)

        # Save all relations in a batch
        if relations_to_save:
            self.save_relations_batch(relations_to_save)

        # Save all nodes in a batch
        if processed_nodes:
            self.save_nodes_batch(list(processed_nodes))

    def strengthen_relation(self, node: Node, rel: Relation, current_hop: int, relations_to_save: list) -> None:
        """Propagate activation through a relation and optionally strengthen/weaken it.

        Args:
            node: The source node.
            rel: The relation to propagate through.
            current_hop: Current hop count.
            relations_to_save: List to collect relations for batch saving.
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
            relations_to_save.append(rel)

    def get_output(self) -> list[Node]:
        """Return the top 25 most activated nodes (activation > 0.5), sorted descending."""

        with self.db_session() as cursor:
            rows = cursor.execute(
                "SELECT name FROM nodes WHERE activation >= 0.5 ORDER BY activation DESC LIMIT 10;"
            ).fetchall()

        return [self.get_node(row[0]) for row in rows]

    def feed_input(self, subj: str, rel: str, obj: str, intent: str = "DEFAULT") -> None:
        subj = subj.lower().strip()
        rel = rel.lower().strip()
        obj = obj.lower().strip()

        self.stack.add((subj, 1.0, 0))
        self.stack.add((rel, 1.0, 0))
        self.add_activation(obj, 1.0, False, intent)

        with self.db_session() as cursor:
            row = cursor.execute(
                "SELECT id FROM relations WHERE subj = ? AND name = ? AND obj = ?;",
                (subj, rel, obj)
            ).fetchone()

            if row is None:
                cursor.execute(
                    "INSERT INTO relations (subj, name, obj, weight, last_decayed) VALUES (?, ?, ?, ?, DATETIME('now'));",
                    (subj, rel, obj, 0.5)
                )
                relation_id = cursor.lastrowid
            else:
                relation_id = row[0]

        relations_to_save = []
        self.strengthen_relation(self.get_node(subj), self.get_relation_by_id(relation_id), 0, relations_to_save)
        if relations_to_save:
            self.save_relations_batch(relations_to_save)

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

    def generate_graph_view(self):
        net = Network(height="900px", width="100%", directed=True,  bgcolor = "#222222", font_color = "white", select_menu=False, filter_menu=False)
        
        with self.db_session() as cursor:
            nodes = cursor.execute(
                """SELECT DISTINCT subj AS node_name FROM relations
                LEFT JOIN nodes ON relations.subj = nodes.name
                UNION
                SELECT DISTINCT obj AS node_name FROM relations
                LEFT JOIN nodes ON relations.obj = nodes.name;""").fetchall()
            
            edges = cursor.execute(
                """SELECT e.subj, e.name, e.obj, e.weight 
                   FROM relations e
                   WHERE e.subj IN (SELECT name FROM nodes ORDER BY activation DESC)
                   AND e.obj IN (SELECT name FROM nodes ORDER BY activation DESC)""",
            ).fetchall()
        
        for name in [row[0] for row in nodes]:
            net.add_node(name, label=name, title=name)
        
        for src, relation, tgt, weight in edges:
            net.add_edge(src, tgt, label=relation, title=f"weight: {weight:.3f}")
        
        xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share/")
        data_dir = os.path.join(xdg_data_home, "louis")
        os.makedirs(data_dir, exist_ok=True)

        net.save_graph(os.path.join(data_dir, "graph.html"))
    
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
        
        nodes = [node.replace(' ', '_') for node in nodes]
        
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
        
        with self.db_session() as cursor:
            for word in names:
                for node in cursor.execute("SELECT name FROM nodes WHERE name == ?;", (word,)).fetchall():
                    nodes.append(node[0]) 
        
        return nodes

    def write(self, text: str):
        text = text.lower()
        
        doc = self.nlp(text)
        
        for sentence in doc.sents:
            self.log(f"Processing sentence '{sentence.text}'")
            nodes = []
            
            for token in sentence:
                # Skip lemmatization for named entities (e.g., names, organizations, locations)
                if token.ent_type_:
                    nodes.append(token.text)
                else:
                    nodes.append(token.lemma_ if token.pos_ not in ("PROPN", "NOUN") else token.text)
            
            json_data = InputLLM(self.config.get_value("graph-model"), self.config.get_value("api_key"), self.config.get_value("base_url")).send(f"Source Text: {sentence}\nLemmatized words: {nodes}")
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

    def delete_relation(self, subj, name, obj):
        """
        Deletes a relation between two nodes form the graph
        Parameters:
            - subj: the subj of the relation
            - name: the name of the relation (eg, is_a, teaches, etc)
            - obj: the obj of the relation
        """
        with db_session() as cursor:
            cursor.execute("DELETE FROM relations WHERE subj == ? AND name == ? AND obj == ?;", (subj, rel, obj))


    def delete_node(self, name):
        """
        Deletes a node and all it's relations from the graph
        Parameters:
            - name: the name of the node to delete
        """
        with db_session() as cursor:
            cursor.execute("DELETE FROM nodes WHERE name == ?;", (name,))
            cursor.execute("DELETE FROM relations WHERE subj == ? OR obj == ?;", (name, name))
