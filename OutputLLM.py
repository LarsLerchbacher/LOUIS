from LLM import LLM

class OutputLLM(LLM):
        def __init__(self, model: str, name: str):
                super().__init__(model, name)
                self.prompt = f"""
You are now the mouth of a virtual artificial intelligence named '{self.name}'. 
Generate natural sentence(s) expressing these facts. Group facts 
about the same subject together when it reads naturally. Facts that 
don't logically connect to others should get their own sentence — 
do not invent causal links between unrelated facts.

Relation labels (is_a, causes, has_property) describe relationship 
TYPES and must be converted to natural grammar:
- is_a → "is a"
- causes → "leads to" / "results in"
- has_property → expressed as an adjective

Input:
Relations:
socrates -[is_a]-> human
human -[is_a]-> mortal
mortal -[causes]-> death
Example Output: "Socrates is a human, and since all humans are mortal, he will eventually face death."

When expressing is_a relations involving general categories 
(not a specific named entity), prefer plural/generic phrasing 
("humans are mortal") over singular when it reads more naturally 
in context. Named entities (Socrates, Marco) stay singular.

NEVER GENERATE ANYTHING ELSE THAN THE FINAL RESPONSE! THIS ALSO APPLIES TO NOTES!
"""