from Relation import Relation

class Node():
    """Represents a neuron"""
    def __init__(self, name: str, known: bool = False, flagged: bool = True, confidence: float = 0.0, activation: float = 0.0, threshold: float = 0.5, relations: list = None):
        self.name = name
        self.known = known
        self.flagged = flagged
        self.confidence = confidence
        self.activation = activation
        self.relations = relations if relations is not None else []
        self.threshold = threshold

    @staticmethod
    def fromJSON(json) -> 'Node':
        return Node(json["name"], json["known"], json["flagged"], json["confidence"], json["activation"], json["threshold"], json["relations"])
    
    def setName(self, name: str) -> None:
        self.name = name
    
    def setKnown(self, known: bool) -> None:
        self.known = known
    
    def setFlagged(self, flagged: bool) -> None:
        self.flagged = flagged
    
    def setConfidence(self, confidence: float) -> None:
        # Sets confidence in the range of 0.0 - 1.0
        self.confidence = round(min(1.0, max(0.0, confidence)), 4)
        
    def setActivation(self, activation: float) -> None:
        # Sets activation in the range of 0.0 - 1.0
        self.activation = round(min(1.0, max(0.0, activation)), 4)
    
    def setThreshold(self, threshold: float) -> None:
        # Sets threshold in the range of 0.0 - 1.0
        self.threshold = round(min(1.0, max(0.0, threshold)), 4)

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
        self.relations.append(rel)

    def renderRelations(self) -> str:
        result = ""
        for rel in self.relations:
            result += str(rel)
            result += "\n"
        
        return result
        
    def __str__(self):
        return f"# {self.name}\n\nKnown: {self.known}\nConfidence: {self.confidence}\nFlagged: {self.flagged}\nActivation: {self.activation}\nThreshold: {self.threshold}\n\n|Relation|Target|Weight|Type|Last Activated|Last Decayed|\n|---|---|---|---|---|---|\n" + self.renderRelations()


