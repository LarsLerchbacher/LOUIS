from LLM import LLM
from ollama import chat, ChatResponse

class InputLLM(LLM):
    """Parses natural language input into structured JSON relations for the model.

    The system prompt instructs the LLM to extract explicit relations only,
    lemmatize verbs, and output JSON suitable for Model.parseJSON().
    """

    def __init__(self, model: str, name: str):
        super().__init__(model, name)
        self.prompt = """
You are an information extraction system.

Goal:

Extract EVERY explicitly stated fact from the input text.

Rules:

Extract only facts directly stated in the text.
Do NOT infer new facts.
Do NOT use background knowledge.
Do NOT summarize.
Do NOT merge facts.
Missing a fact is an error.
If multiple facts are present, output one JSON object per fact.
If a sentence contains "and", "or", commas, or lists, split them into separate facts whenever the same relation applies.
Prefer duplicate facts over omitted facts.
Keep subject, relation, and object as close as possible to the wording in the text.
Output ONLY valid JSON.
Return an empty list if no factual statement is present.

Output format:

[
  {
    "subject": "...",
    "relation": "...",
    "object": "..."
  }
]

Before producing output, internally check:

Did I extract every explicitly stated fact?
Did I split all conjunctions?
Did I split all lists?
Did I avoid inference?
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
            #},"""
        )
        return response.message.content 

