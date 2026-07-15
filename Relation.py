from datetime import datetime


class Relation:
    """Represents a directed weighted connection between two nodes.

    Analogous to a synapse. Relations can be activating (ACTIVATES) or
    inhibiting (INHIBITS). Inherited relations (from is_a chains) have
    reduced weight but are never strengthened directly.
    """

    def __init__(self, subj: str, name: str, obj: str, weight: float,
                 last_fired: datetime,
                 last_decayed: datetime = None):
        """Initialize a Relation with a subject, name, object, weight, and timestamps.
        
        Args:
            subj (str): The subject of the relation.
            name (str): The name of the relation.
            obj (str): The object of the relation.
            weight (float): The weight of the relation.
            last_fired (datetime): The last time the relation was fired.
            last_decayed (datetime, optional): The last time the relation was decayed.
        """
        self.subj = subj
        self.name = name
        self.obj = obj
        self.weight = weight
        self.last_fired = last_fired
        self.last_decayed = last_decayed

    @staticmethod
    def fromJSON(json_dict: dict) -> 'Relation':
        """Create a Relation from a parsed dictionary.
        
        Args:
            json_dict (dict): A dictionary containing the relation data.
            
        Returns:
            Relation: A Relation object created from the dictionary.
        """
        return Relation(
            json_dict["subj"], json_dict["name"], json_dict["obj"],
            json_dict["weight"],
            json_dict["last_fired"], json_dict["last_decayed"]
        )

    # --- Getters ---

    def get_subj(self) -> str:
        return self.subj

    def get_name(self) -> str:
        return self.name

    def get_obj(self) -> str:
        return self.obj

    def get_weight(self) -> float:
        return self.weight

    def get_last_fired(self) -> str:
        """Return last_fired as ISO string."""
        return self.last_fired.isoformat() if isinstance(self.last_fired, datetime) else self.last_fired

    def get_last_decayed(self) -> str:
        """Return last_decayed as ISO string."""
        return self.last_decayed.isoformat() if isinstance(self.last_decayed, datetime) else self.last_decayed

    # --- Setters ---

    def set_subj(self, subj: str) -> None:
        self.subj = subj

    def set_name(self, name: str) -> None:
        self.name = name

    def set_obj(self, obj: str) -> None:
        self.obj = obj

    def set_weight(self, weight: float) -> None:
        """Set weight, clamped to [0.0, 1.0]."""
        self.weight = round(min(1.0, max(0.1, weight)), 4)

    def set_last_fired(self, last_fired: datetime) -> None:
        self.last_fired = last_fired

    def set_last_decayed(self, last_decayed: datetime) -> None:
        self.last_decayed = last_decayed

    def __str__(self) -> str:
        return f"{self.subj} --- {self.name} --> {self.obj}"

