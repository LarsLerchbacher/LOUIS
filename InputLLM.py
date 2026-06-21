from ollama import chat, ChatResponse

class InputLLM():
    """Parses natural language input into structured JSON relations for the model.

    The system prompt instructs the LLM to extract explicit relations only,
    lemmatize verbs, and output JSON suitable for Model.parseJSON().
    """

    def __init__(self, model: str):
        self.model = model
        self.prompt = """
You are a graph extraction system.

Your task is to convert a sentence into a complete set of directed triples.

INPUT:

* One sentence (original text)
* A set of lemmatized tokens from the sentence

OUTPUT:

* A list of triples: (subject, relation, object)

RULES:

1. All elements (subject, relation, object) MUST come from the provided token set.

2. Tokens may function as nouns, verbs, adjectives, or relations.

3. You MUST identify and enumerate ALL valid relationships present in the sentence.

4. Do NOT stop after finding the first relation.
   Continue until every possible explicit relationship has been extracted.

5. Treat this as an exhaustive enumeration task, not a single-answer task.

6. Each distinct semantic relationship must appear as a separate triple.

7. Relations are not restricted to a fixed set.
   Any token may be used as a relation.

8. Do NOT infer facts not present in the sentence.

9. Do NOT omit relationships that are explicitly or structurally implied.

10. Do NOT summarize the sentence.

PRONOUN RESOLUTION RULE:

If a token is a pronoun (e.g. he, she, him, her, they, it), attempt to resolve it using ONLY other tokens in the same sentence.
Resolution rules:
Prefer nearest preceding noun or named entity in the sentence.
If multiple candidates exist, choose the most recent valid subject.
If no valid resolution exists, DO NOT use the pronoun in output (skip that triple).
Do NOT introduce external knowledge.
Do NOT resolve pronouns beyond the current sentence context.

OUTPUT FORMAT:
[
{
"subject": "<token>",
"relation": "<token>",
"object": "<token>"
}
]

""" 

    def send(self, message: str) -> str:
        """Send a message to the LLM and return the text response."""
        response: ChatResponse = chat(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.prompt},
                {'role': 'user', 'content': message},
            ],
            options={"temperature": 0.0, "think": False}
        )
        return response.message.content 

