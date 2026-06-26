from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from ChatHandler import ChatHandler
import uvicorn
from datetime import datetime
from Graph import Graph
import re
import json
import asyncio
import threading
import queue
from mistralai.client.models import AssistantMessage

class API:
    def __init__(self, host: str = "0.0.0.0", port: int = 8000, config = None, logger=None, session_logger=None):
        self.app = FastAPI()
        self.host = host
        self.config = config
        self.logger = logger
        self.session_logger=session_logger
        self.port = port 
        self._setup_routes()
        
        self._task_queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        
        done = threading.Event()
        self._task_queue.put((self.initialize, done))
        done.wait()
    
    def _worker_loop(self):
        while True:
            task, done = self._task_queue.get()
            task()
            done.set() 
    
    def initialize(self):
        self.chat = ChatHandler(self.config, self.logger, self.session_logger)
        self.chat.initialize() 
    
    def safe_json_loads(self, s):
        """Necesary to avoid problems when the LLM uses newlines"""
        s = s.replace("\n", "\\n") # Replace actual newlines with python escape sequence
        s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # remove all other control chars
        return json.loads(s) 

    def _setup_routes(self):
        DONE_SENTINEL = object()

        @self.app.post("/chat/completions")
        async def chat_completions(request: Request):
            data = await request.json()
            self.chat.agentLLM.messages = [{"role": "system", "content": self.chat.agentLLM.prompt + self.chat.agentLLM.summary}]
            self.chat.agentLLM.messages.extend(data["messages"][0:-1])
            user_message = data["messages"][-1]["content"]
            response_queue = asyncio.Queue()

            async def process_input():
                loop = asyncio.get_event_loop()
                done = threading.Event()

                def task():
                    self.chat.handle_user_input(user_message, response_queue, loop)
                    loop.call_soon_threadsafe(response_queue.put_nowait, DONE_SENTINEL)
                    done.set()

                self._task_queue.put((task, done))
                await loop.run_in_executor(None, done.wait)

            asyncio.create_task(process_input())

            async def generate():
                while True:
                    chunk = await response_queue.get()
                    if isinstance(chunk, AssistantMessage):
                        chunk = chunk.content
                    if chunk is DONE_SENTINEL:
                        yield "data: [DONE]\n\n"
                        break
                    yield f"data: {json.dumps({
                        'id': 'chatcmpl-123',
                        'object': 'chat.completion.chunk',
                        'created': datetime.now().timestamp(),
                        'model': self.config.get_value('name'),
                        'choices': [{
                            'index': 0,
                            'delta': {'content': chunk + "\n\n"},
                            'finish_reason': None
                        }]
                    })}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")
        
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

