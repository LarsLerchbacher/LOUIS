from ollama import chat, ChatResponse


class LLM:
    """Base wrapper for Ollama-based LLM interaction.

    Subclasses set self.prompt to define system behavior.
    """

    def __init__(self, model: str, name: str):
        self.name = name
        self.model = model
        self.prompt = ""

    def send(self, message: str) -> str:
        """Send a message to the LLM and return the text response."""
        response: ChatResponse = chat(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.prompt},
                {'role': 'user', 'content': message},
            ],
            options={"temperature": 0.0}
        )
        return response.message.content