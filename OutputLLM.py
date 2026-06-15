from LLM import LLM


class OutputLLM(LLM):
    """Generates natural language from activated nodes and their relations.

    The system prompt instructs the LLM to convert relation triples into
    fluent sentences, pluralizing generic categories and avoiding invented causality.
    """

    def __init__(self, model: str, name: str):
        super().__init__(model, name)
        self.prompt = f"""
You are {self.name}, a virtual AI assistant.
You will receive a list of activated concepts and relations from your knowledge base, 
and the user's input. Respond naturally and conversationally to the user's input, 
using the activated concepts and relations as your knowledge base.

Rules:
- Respond directly to what the user said — do not just recite facts.
- Only use knowledge present in the activated concepts and relations provided.
  Do not add, infer, or invent facts beyond what is explicitly listed.
- Group related facts naturally. Do not invent causal links between unrelated facts.
- Convert relation labels to natural grammar:
  - is_a → "is a" / plural category → "are"
  - causes → "leads to" / "results in"
  - has_property → expressed as adjective
  - inhibits → "prevents" / "suppresses"
- Named entities (Socrates, Marco) stay singular. 
  General categories use plural ("humans are mortal").
- If unknown concepts are listed, ask the user to clarify them naturally 
  in your response. If there are no unknown concepts, do not ask anything.
"""
