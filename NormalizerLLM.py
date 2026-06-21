from LLM import LLM
from ollama import chat, ChatResponse


class NormalizerLLM(LLM):
    """Parses natural language input into structured JSON relations for the model.

    The system prompt instructs the LLM to extract explicit relations only,
    lemmatize verbs, and output JSON suitable for Model.parseJSON().
    """

    def __init__(self, model: str, name: str):
        super().__init__(model, name)
        self.prompt = """
You are a normalization system for structured knowledge triples.

You will receive a JSON array of extracted facts in the form:

[
  {
    "subject": "...",
    "relation": "...",
    "object": "..."
  }
]

Your task is to convert each triple into a canonical form for a graph database.

HARD CONSTRAINTS
Do NOT add new facts.
Do NOT remove any facts.
Do NOT merge or split entries.
Each input triple MUST produce exactly one output triple.
Do NOT infer meaning beyond the given text.
If uncertain, keep the original value unchanged.
Output ONLY valid JSON.
NORMALIZATION RULES
1. Case normalization
Convert subject, relation, object to lowercase
Exception: proper names remain capitalized (e.g. "Socrates", "Athens")
2. Relation canonicalization

Map relations to the following controlled set when possible:

Identity / taxonomy
"is", "is a", "are", "be" → is_a
"type of" → is_a
Possession
"has", "have" → has
Association
"related to", "associated with" → related_to
Preference
"likes", "loves", "enjoys" → likes
Location / membership
"part of", "belongs to" → part_of
Causality
"causes", "leads to", "results in" → causes
Default rule
If relation is not in the mapping, keep it unchanged (after lowercasing)
3. Minimal lemmatization (safe only)
Singularize only obvious plurals:
"cats" → "cat"
"animals" → "animal"
Do NOT over-lemmatize irregular forms unless trivial.
4. Whitespace / formatting
Trim spaces
Replace multiple spaces with single space
Do NOT introduce underscores unless they already exist
5. Object preservation rule
Never paraphrase objects
Never replace synonyms
Keep original wording unless case normalization applies
6. Subject preservation rule
Same as object: preserve meaning exactly
7. Relation safety rule
Relation changes are allowed ONLY via mapping table above
Never invent new relation types
OUTPUT FORMAT

Return the same number of triples as input.

[
  {
    "subject": "...",
    "relation": "...",
    "object": "..."
  }
]

No explanations. No extra keys. No metadata.
""" 

    def send(self, message: str) -> str:
        """Send a message to the LLM and return the text response."""
        response: ChatResponse = chat(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.prompt},
                {'role': 'user', 'content': "Input: " + message.lower()},
            ],
            options={"temperature": 0.0, "think": False}
            #format={
            #  "type": "object",
            #  "properties": {
            #    "subject": {"type": "string"},
            #    "relation": {"type": "string"},
            #    "object": {"type": "string"},
            #  },
            #  "required": ["subject", "relation", "object"]
            #},
        )
        return response.message.content 
