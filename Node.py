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

    def setName(self, name: str) -> None:
        self.name = name

    def setKnown(self, known: bool) -> None:
        self.known = known

    def setFlagged(self, flagged: bool) -> None:
        self.flagged = flagged

    def setConfidence(self, confidence: float) -> None:
        """Set confidence, clamped to [0.0, 1.0]."""
        self.confidence = round(min(1.0, max(0.0, confidence)), 4)

    def setActivation(self, activation: float) -> None:
        """Set activation, clamped to [0.0, 1.0]."""
        self.activation = round(min(1.0, max(0.0, activation)), 4)

    def setThreshold(self, threshold: float) -> None:
        """Set firing threshold, clamped to [0.0, 1.0]."""
        self.threshold = round(min(1.0, max(0.0, threshold)), 4)

    # --- Getters ---

    def getName(self) -> str:
        return self.name

    def getKnown(self) -> bool:
        return self.known

    def getFlagged(self) -> bool:
        return self.flagged

    def getConfidence(self) -> float:
        return self.confidence

    def getRelations(self) -> list[Relation]:
        return self.relations

    def getActivation(self) -> float:
        return self.activation

    def getThreshold(self) -> float:
        return self.threshold

    def addRelation(self, rel: Relation) -> None:
        """Append a relation to this node's list."""
        self.relations.append(rel)

    def renderRelations(self) -> str:
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
        return header + self.renderRelations()


