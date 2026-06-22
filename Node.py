from Relation import Relation


class Node:
    """Represents a conceptual node in the knowledge graph.

    Each node has activation energy, and a set of
    relations connecting it to other nodes. Comparable to a neuron.
    """

    def __init__(self, name: str, known: bool = False,
                 confidence: float = 0.0, activation: float = 0.0,
                relations: list = None):
        self.name = name
        self.known = known
        self.confidence = confidence
        self.activation = activation
        self.relations = relations if relations is not None else []

    @staticmethod
    def fromJSON(json_dict: dict) -> 'Node':
        """Create a Node from a parsed dictionary (e.g. from markdown parsing)."""
        return Node(
            json_dict["name"], json_dict["known"],
            json_dict["confidence"], json_dict["activation"],
            json_dict["relations"]
        )

    # --- Setters ---

    def set_name(self, name: str) -> None:
        self.name = name

    def set_known(self, known: bool) -> None:
        self.known = known

    def set_confidence(self, confidence: float) -> None:
        """Set confidence, clamped to [0.0, 1.0]."""
        self.confidence = round(min(1.0, max(0.0, confidence)), 4)

    def set_activation(self, activation: float) -> None:
        """Set activation, clamped to [0.0, 1.0]."""
        self.activation = round(min(1.0, max(0.0, activation)), 4)

    # --- Getters ---

    def get_name(self) -> str:
        return self.name

    def get_known(self) -> bool:
        return self.known

    def get_confidence(self) -> float:
        return self.confidence

    def get_relations(self) -> list[Relation]:
        return self.relations

    def get_activation(self) -> float:
        return self.activation

    def add_relation(self, rel: Relation) -> None:
        """Append a relation to this node's list."""
        self.relations.append(rel)

    def __str__(self) -> str:
       return f"{self.name} ({self.confidence} confidence)"


