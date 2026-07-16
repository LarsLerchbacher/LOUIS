from Relation import Relation


class Node:
    """Represents a conceptual node in the knowledge graph.

    Each node has activation energy, and a set of
    relations connecting it to other nodes. Comparable to a neuron.
    """

    def __init__(self, name: str, activation: float = 0.0,
                relations: list = None):
        """Initialize a Node with a name, known status, confidence, activation, and relations.
        
        Args:
            name (str): The name of the node.
            activation (float): The activation level of the node.
            relations (list): A list of relations associated with the node.
        """
        self.name = name
        self.activation = activation
        self.relations = relations if relations is not None else []

    @staticmethod
    def fromJSON(json_dict: dict) -> 'Node':
        """Create a Node from a parsed dictionary (e.g. from markdown parsing).
        
        Args:
            json_dict (dict): A dictionary containing the node data.
            
        Returns:
            Node: A Node object created from the dictionary.
        """
        return Node(json_dict["name"], json_dict["activation"],json_dict["relations"])

    # --- Setters ---

    def set_name(self, name: str) -> None:
        self.name = name

    def set_activation(self, activation: float) -> None:
        """Set activation, clamped to [0.0, 1.0]."""
        self.activation = round(min(1.0, max(0.0, activation)), 4)

    # --- Getters ---

    def get_name(self) -> str:
        return self.name

    def get_relations(self) -> list[Relation]:
        return self.relations

    def get_activation(self) -> float:
        return self.activation

    def add_relation(self, rel: Relation) -> None:
        """Append a relation to this node's list."""
        self.relations.append(rel)

    def __str__(self) -> str:
       return f"{self.name}"


