from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

class Relation():
    """Represents a synapse, a connection between two neurons or, in this case, Nodes"""
    def __init__(self, subj: Node, name: str, obj: Node, weight: float, rel_type: str, last_fired: datetime):
        self.subj = subj 
        self.name = name 
        self.obj = obj 
        self.weight = weight
        self.rel_type = rel_type
        self.last_fired = last_fired 

    def fromJSON(json) -> Relation:
        return Relation(json["subj"], json["name"], json["obj"], json["weight"], json["type"], json["last_fired"])
    
    def getSubj(self) -> Node:
        return self.subj
    
    def getName(self) -> str:
        return self.name

    def getObj(self) -> Node:
        return self.obj
    
    def getWeight(self) -> float:
        return self.weight
        
    def getRelType(self) -> str:
        return self.rel_type

    def getLastFired(self) -> datetime:
        return self.last_fired.isoformat()
    
    def setSubj(self, subj: Node) -> None:
        self.subj = subj
    
    def setName(self, name: str) -> None:
        self.name = name
    
    def setObj(self, obj: Node) -> None:
        self.obj = obj

    def setWeight(self, weight: float) -> None:
        # Sets threshold in the range of 0.0 - 1.0
        self.weight = min(1.0, max(0.0, weight)) 

    def setRelType(self, rel_type: str) -> None:
        self.rel_type = rel_type

    def setLastFired(self, last_fired: datetime) -> None:
        self.last_fired = last_fired

    def __str__(self):
        return f"|{self.name}|[[{self.obj}]]|{self.weight}|{self.rel_type}|{self.last_fired}|"
