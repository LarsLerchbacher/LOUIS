from datetime import datetime


class Relation:
    """Represents a directed weighted connection between two nodes.

    Analogous to a synapse. Relations can be activating (ACTIVATES) or
    inhibiting (INHIBITS). Inherited relations (from is_a chains) have
    reduced weight but are never strengthened directly.
    """

    def __init__(self, subj: str, name: str, obj: str, weight: float,
                 rel_type: str, last_fired: datetime,
                 last_decayed: datetime = None):
        self.subj = subj
        self.name = name
        self.obj = obj
        self.weight = weight
        self.rel_type = rel_type
        self.last_fired = last_fired
        self.last_decayed = last_decayed

    @staticmethod
    def fromJSON(json_dict: dict) -> 'Relation':
        """Create a Relation from a parsed dictionary."""
        return Relation(
            json_dict["subj"], json_dict["name"], json_dict["obj"],
            json_dict["weight"], json_dict["type"],
            json_dict["last_fired"], json_dict["last_decayed"]
        )

    # --- Getters ---

    def getSubj(self) -> str:
        return self.subj

    def getName(self) -> str:
        return self.name

    def getObj(self) -> str:
        return self.obj

    def getWeight(self) -> float:
        return self.weight

    def getRelType(self) -> str:
        return self.rel_type

    def getLastFired(self) -> str:
        """Return last_fired as ISO string."""
        return self.last_fired.isoformat() if isinstance(self.last_fired, datetime) else self.last_fired

    def getLastDecayed(self) -> str:
        """Return last_decayed as ISO string."""
        return self.last_decayed.isoformat() if isinstance(self.last_decayed, datetime) else self.last_decayed

    # --- Setters ---

    def setSubj(self, subj: str) -> None:
        self.subj = subj

    def setName(self, name: str) -> None:
        self.name = name

    def setObj(self, obj: str) -> None:
        self.obj = obj

    def setWeight(self, weight: float) -> None:
        """Set weight, clamped to [0.0, 1.0]."""
        self.weight = round(min(1.0, max(0.0, weight)), 4)

    def setRelType(self, rel_type: str) -> None:
        self.rel_type = rel_type

    def setLastFired(self, last_fired: datetime) -> None:
        self.last_fired = last_fired

    def setLastDecayed(self, last_decayed: datetime) -> None:
        self.last_decayed = last_decayed

    def __str__(self) -> str:
        return f"|{self.name}|[[{self.obj}]]|{self.weight}|{self.rel_type}|{self.last_fired}|{self.last_decayed}|"
