from __future__ import annotations
from typing import TYPE_CHECKING

class Node():
    """Represents a neuron"""
    def __init__(self, name: str, known: bool = False, flagged: bool = True, confidence: float = 0.0, activation: float = 0.0, relations: list[Relation] = []):
        self.name = name
        self.known = known
        self.flagged = flagged
        self.confidence = confidence
        self.activation = activation
        self.relations = relations

    def fromJSON(json: str) -> Node:
        return Node(json["name"], json["known"], json["flagged"], json["confidence"], json["activation"], json["relations"])
    
    def setName(self, name: str) -> None:
        self.name = name
    
    def setKnown(self, known: bool) -> None:
        self.known = known
    
    def setFlagged(flagged: bool) -> None:
        self.flagged = flagged
    
    def setConfidence(confidence: float) -> None:
        self.confidence = confidence

    def getName(self) -> str:
        return self.name
    
    def getKnown(self) -> bool:
        return self.knwon
    
    def getFlagged(self) -> bool:
        return self.flagged

    def getConfidence(self) -> float:
        return self.confidence
    
    def getRelations(self) -> list[Relation]:
        return self.relations
    
    def addRelation(rel: Relation) -> None:
        self.relations.add(rel)

    def renderRelations(self) -> str:
        result = ""
        for rel in self.relations:
            result += str(rel)
            result += "\n"
        
        return result
        
    def __str__(self):
        return f"# {self.name}:\n\nKnown: {self.known}\nConfidence: {self.confidence}\nFlagged: {self.flagged}\nActivation: {self.activation}\n\n|Relation|Target|Weight|Type|\n|---|---|---|---|\n" + self.renderRelations()


