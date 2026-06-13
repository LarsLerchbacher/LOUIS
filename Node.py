from Relation import Relation


class Node:
    """Represents a conceptual node in the knowledge graph.

    Each node has activation energy, a firing threshold, and a set of
    relations connecting it to other nodes. Comparable to a neuron.
    """

    def __init__(self, name: str, known: bool = False, flagged: bool = True,
                 confidence: float = 0.0, activation: float = 0.0,
                 threshold: float = 0.5, relations: list = None):
        self.name = name
        self.known = known
        self.flagged = flagged
        self.confidence = confidence
        self.activation = activation
        self.relations = relations if relations is not None else []
        self.threshold = threshold

    @staticmethod
    def fromJSON(json_dict: dict) -> 'Node':
        """Create a Node from a parsed dictionary (e.g. from markdown parsing)."""
        return Node(
            json_dict["name"], json_dict["known"], json_dict["flagged"],
            json_dict["confidence"], json_dict["activation"],
            json_dict["threshold"], json_dict["relations"]
        )

    # --- Setters ---

    def set_name(self, name: str) -> None:
        self.name = name

    def set_known(self, known: bool) -> None:
        self.known = known

    def set_flagged(self, flagged: bool) -> None:
        self.flagged = flagged

    def set_confidence(self, confidence: float) -> None:
        """Set confidence, clamped to [0.0, 1.0]."""
        self.confidence = round(min(1.0, max(0.0, confidence)), 4)

    def set_activation(self, activation: float) -> None:
        """Set activation, clamped to [0.0, 1.0]."""
        self.activation = round(min(1.0, max(0.0, activation)), 4)

    def set_threshold(self, threshold: float) -> None:
        """Set firing threshold, clamped to [0.0, 1.0]."""
        self.threshold = round(min(1.0, max(0.0, threshold)), 4)

    # --- Getters ---

    def get_name(self) -> str:
        return self.name

    def get_known(self) -> bool:
        return self.known

    def get_flagged(self) -> bool:
        return self.flagged

    def get_confidence(self) -> float:
        return self.confidence

    def get_relations(self) -> list[Relation]:
        return self.relations

    def get_activation(self) -> float:
        return self.activation

    def get_threshold(self) -> float:
        return self.threshold

    def add_relation(self, rel: Relation) -> None:
        """Append a relation to this node's list."""
        self.relations.append(rel)

    def render_relations(self) -> str:
        """Return all relations as a markdown table rows string."""
        return "\n".join(str(rel) for rel in self.relations) + "\n" if self.relations else ""

    def __str__(self) -> str:
        header = (
            f"# {self.name}\n\n"
            f"Known: {self.known}\n"
            f"Confidence: {self.confidence}\n"
            f"Flagged: {self.flagged}\n"
            f"Activation: {self.activation}\n"
            f"Threshold: {self.threshold}\n\n"
            f"## Relations\n"
            f"|Relation|Target|Weight|Type|Last Activated|Last Decayed|\n"
            f"|---|---|---|---|---|---|\n"
        )
        return header + self.render_relations()


