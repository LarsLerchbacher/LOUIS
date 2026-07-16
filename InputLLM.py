"""
	This file is part of LOUIS
	LOUIS is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
	LOUIS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details
	
	You should have received a copy of the GNU Affero General Public License along with LOUIS. If not, see <https://www.gnu.org/licenses/>.
"""
 
from mistralai.client import Mistral

class InputLLM():
    """Parses natural language input into structured JSON relations for the model.

    The system prompt instructs the LLM to extract explicit relations only,
    lemmatize verbs, and output JSON suitable for Model.parseJSON().
    """

    def __init__(self, model: str, api_key: str):
        """Initialize the InputLLM with a model and API key.
        
        Args:
            model (str): The model to use for parsing.
            api_key (str): The API key for the Mistral client.
        """
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

LIST RULES

NEVER use conjunctions (and, or, but) as relation names.
Consolidate list items — "a classmate and friend" means two separate is_a relations, 
not a chain through "and".

PRONOUN RESOLUTION RULE:

If a token is a pronoun (e.g. he, she, him, her, they, it), attempt to resolve it using ONLY other tokens in the same sentence.
Resolution rules:
Prefer nearest preceding noun or named entity in the sentence.
If multiple candidates exist, choose the most recent valid subject.
If no valid resolution exists, DO NOT use the pronoun in output (skip that triple).
Do NOT introduce external knowledge.
Do NOT resolve pronouns beyond the current sentence context.

PREPOSITION RULES

When a relation contains a preposition (friend OF, part OF, member OF), 
fold the preposition into the relation name:
"is a friend of" → is_friend_of
"is a part of" → is_part_of
"is a member of" → is_member_of
Never use bare prepositions (of, for, in) as standalone relation names.

OUTPUT FORMAT:
[
{
"subject": "<token>",
"relation": "<token>",
"object": "<token>"
}
]

Your answer should not be encased in a markdown syntax block!

""" 
        self.messages = [{"role": "system", "content": self.prompt}]
        self.client = Mistral(api_key=api_key)

    def send(self, message: str) -> str:
        """Send a message to the LLM and return the text response.
        
        Args:
            message (str): The message to send to the LLM.
            
        Returns:
            str: The text response from the LLM.
        """
        self.messages.append({"role": "user", "content": message})

        response = self.client.chat.complete(
            model=self.model,
            messages=self.messages,
            temperature=0.0,
        )

        # Extract the assistant's message
        assistant_message = response.choices[0].message
        
        # Append the assistant's message to the messages list
        self.messages.append({
            "role": "assistant",
            "content": assistant_message.content,
        })
        
        return assistant_message.content
