from ollama import chat, ChatResponse

class LLM():
        def __init__(self, model: str, name: str):
                self.name = name
                self.model = model
                self.prompt = ""
        
        def send(self, message: str) -> str:
                response: ChatResponse = chat(model=self.model, messages=[
                  {
                    'role': 'system',
                    'content': self.prompt
                  },
                  {
                    'role': 'user',
                    'content': message,
                  },
                ],
                options={
                  "temperature": 0.0
                })
                
                return response.message.content