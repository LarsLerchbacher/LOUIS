from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ChatHandler import ChatHandler
import uvicorn
from datetime import datetime
import re
import json

class API:
    def __init__(self, host: str = "0.0.0.0", port: int = 8000, config=None, logger=None, session_logger=None, graph=None):
        self.app = FastAPI()
        self.host = host
        self.config = config
        self.logger = logger
        self.session_logger=session_logger
        self.graph = graph
        self.port = port
        self.chat = ChatHandler(self.config, self.logger, self.session_logger, self.graph)
        self.chat.initialize()
        self._setup_routes()
    
    def safe_json_loads(self, s):
        """Necesary to avoid problems when the LLM uses newlines"""
        s = s.replace("\n", "\\n") # Replace actual newlines with python escape sequence
        s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # remove all other control chars
        return json.loads(s) 

    def _setup_routes(self):
        @self.app.post("/chat/completions")
        async def chat_completions(request: Request):
            self.logger.info("Received request for chat completion")
            data = await request.json()
            self.chat.handle_user_input(data["messages"][-1]["content"])
            response_text = self.chat.response
            resp = self.chat.agentLLM.messages[-3]
            return JSONResponse(
                content={
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": datetime.now().timestamp(),
                    "model": self.config.get_value("name"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": response_text
                            },
                            "finish_reason": "stop"
                        }
                    ],
                }
            )
            return response
            """return JSONResponse(
                content={
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": 1677665699,
                    "model": self.config.get_value("name"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello! This is a mock response from the OpenAI-compatible endpoint."
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30
                    }
                }
            )"""

        @self.app.get("/models")
        async def list_models():
            self.logger.info("Received request for models list")
            return JSONResponse(
                content={
                    "object": "list",
                    "data": [
                        {
                            "id": self.config.get_value("name"),
                            "object": "model",
                            "created": 1677665699,
                            "owned_by": "system"
                        }
                    ]
                }
            )

    def run(self):
        uvicorn.run(self.app, host=self.host, port=self.port)

if __name__ == "__main__":
    # This block is just for testing; actual usage is through main.py
    pass
