from datetime import datetime

class Relation():
    """Represents a synapse, a connection between two neurons or, in this case, Nodes"""
    def __init__(self, subj: str, name: str, obj: str, weight: float, rel_type: str, last_fired: datetime):
        self.subj = subj 
        self.name = name 
        self.obj = obj 
        self.weight = weight
        self.rel_type = rel_type
        self.last_fired = last_fired 

    @staticmethod
    def fromJSON(json) -> 'Relation':
        return Relation(json["subj"], json["name"], json["obj"], json["weight"], json["type"], json["last_fired"])
    
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
        return self.last_fired.isoformat() if isinstance(self.last_fired, datetime) else self.last_fired
    
    def setSubj(self, subj: str) -> None:
        self.subj = subj
    
    def setName(self, name: str) -> None:
        self.name = name
    
    def setObj(self, obj: str) -> None:
        self.obj = obj

    def setWeight(self, weight: float) -> None:
        # Sets weight in the range of 0.0 - 1.0
        self.weight = round(min(1.0, max(0.0, weight)), 4)

    def setRelType(self, rel_type: str) -> None:
        self.rel_type = rel_type

    def setLastFired(self, last_fired: datetime) -> None:
        self.last_fired = last_fired

    def __str__(self):
        return f"|{self.name}|[[{self.obj}]]|{self.weight}|{self.rel_type}|{self.last_fired}|"
