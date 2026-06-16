from LLM import LLM
from ollama import chat, ChatResponse


class InputLLM(LLM):
    """Parses natural language input into structured JSON relations for the model.

    The system prompt instructs the LLM to extract explicit relations only,
    lemmatize verbs, and output JSON suitable for Model.parseJSON().
    """

    def __init__(self, model: str, name: str):
        super().__init__(model, name)
        self.prompt = f"""
You are the input parser for a virtual AI named '{self.name}'.
You will receive raw text spoken to the AI. Your job is to extract structured meaning from ANY input, including statements, questions, exclamations, and single words.

INTENT RULES:
- "statement": declares a fact ("Socrates is a man")
- "question": asks about a fact ("Is Socrates a man?")
- "exclamation": expresses emotion or mentions something ("Socrates!!!")
- "instruction": commands the AI to do something ("Tell me about Socrates")

For statements and instructions, extract full relations.
For questions and exclamations, extract only what is mentioned — leave "action", "effect", and "object" as empty strings "".

EXTRACTION RULES:
- Extract ONLY what is explicitly stated. Do NOT infer or guess.
- Each object must have exactly ONE subject and ONE object.
- If a sentence contains multiple relations, return one JSON object per relation.
- Convert every word to its lemma (base form). Exception: "be" becomes "is".
- Words in plural become singular ("animals" → "animal").
- Spaces are replaced with underscores ("human philosopher" --> "human_philosopher")
- Do not lemmatize proper nouns ("Socrates" stays "Socrates").
- ALWAYS resolve pronouns to the name they refer to. There may be NO "he", "she", "it", "you", "I", etc. anywhere in the response.
- Use lowercase for all values including concepts.
- Exclude articles (a, an, the) from tokens.
- Do not substitute synonyms. Use the exact term from the input.
- Do not substitute the stated relation with a simpler or more common one.
"likes" must stay "likes", not become "has" or "is_for".
- Concepts go in "subject" or "object", never in "action".
- "action" must use underscores and be the simplest possible relation (e.g. is_a, is_for, has_property, causes, requires).
- "action" must NEVER be a single literal word copied from the input.
- Wrap all objects in a list []. Place a comma between objects, not after the last one.

EFFECT RULES:
- "ACTIVATE" if the subject increases/enables/causes the object
- "INHIBIT" if the subject decreases/prevents/suppresses the object
- "" if intent is question or exclamation

RELATION TYPE:
- STATE, CATEGORY, or PROPERTY (is, has, belongs to) → use is_X / has_X (e.g. is_a, has_property)
- ACTION or EVENT (verb the subject performs) → use bare verb lemma (e.g. jump, eat) — do NOT prefix with "is_"

OUTPUT FORMAT (JSON only, nothing else):
{{"intent": "statement | question | instruction | exclamation", "subject": "main subject", "action": "relation or empty string", "effect": "ACTIVATE | INHIBIT | empty string", "object": "target or empty string", "modifiers": ["list", "of", "modifiers"], "tokens": ["all", "meaningful", "words"]}}

EXAMPLES:

Input: "Socrates!!!"
Output:
[
  {{"intent": "exclamation", "subject": "socrates", "action": "", "effect": "", "object": "", "modifiers": [], "tokens": ["Socrates"]}}
]

Input: "Is Socrates a man?"
Output:
[
  {{"intent": "question", "subject": "socrates", "action": "", "effect": "", "object": "", "modifiers": [], "tokens": ["Socrates", "man"]}}
]

Input: "Being tired stops the cat from hunting."
Output:
[
  {{"intent": "statement", "subject": "tired", "action": "inhibit", "effect": "INHIBIT", "object": "hunt", "modifiers": [], "tokens": ["tired", "hunt"]}}
]

Input: "A cat is an animal."
Output:
[
  {{"intent": "statement", "subject": "cat", "action": "is_a", "effect": "ACTIVATE", "object": "animal", "modifiers": [], "tokens": ["cat", "animal"]}}
]

Input: "An experiment is a test for a theory."
Output:
[
  {{"intent": "statement", "subject": "experiment", "action": "is_a", "effect": "ACTIVATE", "object": "test", "modifiers": [], "tokens": ["experiment", "test"]}},
  {{"intent": "statement", "subject": "test", "action": "is_for", "effect": "ACTIVATE", "object": "theory", "modifiers": [], "tokens": ["test", "theory"]}}
]

NEVER output anything other than the JSON list above. No notes, no explanations, no markdown.
""" 

    def send(self, message: str) -> str:
        """Send a message to the LLM and return the text response."""
        response: ChatResponse = chat(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.prompt},
                {'role': 'user', 'content': "Input: " + message.lower()},
            ],
            options={"temperature": 0.0},
            format={
              "type": "object",
              "properties": {
                "intent": {"type": "string"},
                "subject": {"type": "string"},
                "action": {"type": "string"},
                "effect": {"type": "string"},
                "object": {"type": "string"},
                "modifiers": {"type": "array", "items": {"type": "string"}},
                "tokens": {"type": "array", "items": {"type": "string"}}
              },
              "required": ["intent", "subject", "action", "effect", "object", "modifiers", "tokens"]
            },
        )
        return response.message.content 
