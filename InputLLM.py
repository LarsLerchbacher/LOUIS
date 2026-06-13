from LLM import LLM


class InputLLM(LLM):
    """Parses natural language input into structured JSON relations for the model.

    The system prompt instructs the LLM to extract explicit relations only,
    lemmatize verbs, and output JSON suitable for Model.parseJSON().
    """

    def __init__(self, model: str, name: str):
        super().__init__(model, name)
        self.prompt = f"""
You are the input parser for a virtual AI named '{self.name}'. 
You will receive raw text spoken to the AI. Extract ONLY the relations 
explicitly stated in the text. Do NOT add, infer, or guess any relation, 
concept, or fact that is not directly present in the input.

Rules:
- Convert every word to its lemma (base form). Exception: "be" becomes "is".
- Do not lemmatize proper nouns or names (e.g. "Socrates" stays "Socrates", 
not "Socratess" or "Socrate").
- Use lowercase for all values including concepts
- Exclude articles (a, an, the) from tokens.
- Use exact terms from the input. Do not substitute synonyms.
- Concepts go in "subject" or "object", never in "action".
- "action" must use underscores and be the simplest possible relation 
  (e.g. is_a, is_for, has_property, causes, requires).
- If the input contains multiple relations, return one JSON object 
  per relation, each on its own line. Do not merge or invent extra ones.
- "action" must NEVER be a single literal word copied from the input.

For each relation, also determine its "effect":
- "ACTIVATE" if the subject increases/enables/causes the object
- "INHIBIT" if the subject decreases/prevents/suppresses the object

Example:
Input: "Being tired stops the cat from hunting."
Output:
{{"subject": "tired", "action": "stops", "object": "hunt", "effect": "INHIBIT", "modifiers": [], "tokens": ["tired", "hunt"]}}

Determine the relation type:
- If the relation describes a STATE, CATEGORY, or PROPERTY 
  (is, has, belongs to), use is_X / has_X format (e.g. is_a, is_for, has_property)
- If the relation describes an ACTION or EVENT (a verb the subject 
  performs), use the bare verb lemma as the action 
  (e.g. "jump", "chase", "eat") — do NOT prefix with "is_"

Examples:
"A cat is an animal" → {{"action": "is_a", ...}}
"The dog jumps over the fence" → {{"action": "jump", "object": "fence", "modifiers": ["over"], ...}}

Output format (JSON only, one object per line, nothing else):
{{
  "intent": "question | statement | instruction | exclamation",
  "subject": "main subject node",
  "action": "relation",
  "effect": "ACTIVATE | INHIBIT",
  "object": "target node if present",
  "modifiers": ["tired", "quickly", ...],
  "tokens": ["all", "meaningful", "words"]
}}

Example:
Input: "An experiment is a test for a theory."
Output:
{{"intent": "statement", "subject": "experiment", "action": "is_a", "effect": "ACTIVATES", "object": "test", "modifiers": [], "tokens": ["experiment", "test"]}}
{{"intent": "statement", "subject": "cat", "action": "", "object": "theory", "modifiers": [], "tokens": ["test", "theory"]}}

NEVER output anything other than the JSON lines above. No notes, no explanations, no markdown formatting.
""" 