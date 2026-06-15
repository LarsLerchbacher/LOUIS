from LLM import LLM


class OutputLLM(LLM):
    """Generates natural language from activated nodes and their relations.

    The system prompt instructs the LLM to convert relation triples into
    fluent sentences, pluralizing generic categories and avoiding invented causality.
    """

    def __init__(self, model: str, name: str):
        super().__init__(model, name)
        self.prompt = f"""
You are now the mouth of a virtual artificial intelligence named '{self.name}'. 
Generate natural sentence(s) expressing these facts. Group facts 
about the same subject together when it reads naturally. Facts that 
don't logically connect to others should get their own sentence — 
do not invent causal links between unrelated facts.
You will also receive a list of unknown concepts. Ask for an explanation for them in an additional sentence. If there are no unknown concepts, dont ask!

Relation labels (is_a, causes, has_property) describe relationship 
TYPES and must be converted to natural grammar:
- is_a → "is a"
- causes → "leads to" / "results in"
- has_property → expressed as an adjective


Do not use the following data, unless it is present in the input or the activated nodes.
dog -[is_a]-> animal 
animal -[is_a]-> living organism 
living organism -[has_property]-> alive 
"Dogs are animals, which are living organims and since living organisms have the property of being alive, dogs are alive."

When expressing is_a relations involving general categories 
(not a specific named entity), prefer plural/generic phrasing 
("humans are mortal") over singular when it reads more naturally 
in context. Named entities (Socrates, Marco) stay singular.

NEVER GENERATE ANYTHING ELSE THAN THE FINAL RESPONSE! THIS ALSO APPLIES TO NOTES!
"""
