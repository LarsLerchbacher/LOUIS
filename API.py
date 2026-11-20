"""
	This file is part of LOUIS
	LOUIS is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
	LOUIS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details
	
	You should have received a copy of the GNU Affero General Public License along with LOUIS. If not, see <https://www.gnu.org/licenses/>.
"""
 
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from ChatHandler import ChatHandler
import uvicorn
from datetime import datetime
from Graph import Graph
import re
import json
import asyncio
import os
import threading
import traceback
import queue
import sqlite3
import requests
from openai.types.chat import ChatCompletionMessage

class API:
    """OpenAI-compatible API server for interacting with the AI.
    
    This class provides an API interface for the AI, allowing external applications
    to interact with the AI model via HTTP requests.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8000, config = None, logger=None, session_logger=None, state=None):
        """Initialize the API with a host, port, configuration, and loggers.
        
        Args:
            host (str): The host address to bind the API server to.
            port (int): The port to bind the API server to.
            config (Config): The configuration object for the application.
            logger (logging.Logger): The logger for logging messages.
            session_logger (logging.Logger): The logger for session-specific logging.
            state (State): The state object for managing state data.
        """
        self.app = FastAPI()
        self.host = host
        self.config = config
        self.logger = logger
        self.session_logger=session_logger
        self.state = state
        self.port = port 
        self._setup_routes()
        
        self._task_queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        
        self.done = threading.Event()
        self._task_queue.put((self.initialize, self.done))
        self.done.wait()
    
    def _worker_loop(self):
        while True:
            task, self.done = self._task_queue.get()
            task()
            self.done.set() 
    

    def init_db(self):
        xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        data_dir = os.path.join(xdg_data_home, "louis")
        os.makedirs(data_dir, exist_ok=True)
        
        db = sqlite3.connect(os.path.join(data_dir, "chats.sqlite"))
        cursor = sqlite3.Cursor(db)
        
        return db, cursor

    def close_db(self, db, cursor):
        db.commit()
        cursor.close()
        db.close()
    
    def initialize(self):
        
        self.chat = ChatHandler(self.config, self.logger, self.session_logger, self.state)
        self.chat.initialize() 
        
        db, cursor = self.init_db()
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier STRING NOT NULL,
            messages STRING,
            summary STRING
        );""")
        
        self.close_db(db, cursor)
        
        """self.base_url = str(self.config.get_value("openwebui_url")) + "/api/v1"
        self.token = self.config.get_value('openwebui_token')
        self.ca_cert = self.config.get_value("openwebui_ca_cert")
        if not self.token:
            self.logger.error("Could not load Open WebUI token from config. Please make sure to include it in 'openwebui_token'.")
            quit(1)"""
        
    
    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
    }

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
            response_queue = asyncio.Queue()
            has_user_message = True
            self.chat.agentLLM.messages = data["messages"][0:-1]
            user_message = data["messages"][-1]["content"]

            welcome_text = f"Hello! I'm {self.config.get_value("name")}, your token-efficient AI assistant based on the LOUIS project. My source code is available under the AGPL license: https://github.com/LarsLerchbacher/LOUIS" 
            try:
                if not welcome_text in data["messages"][1]["content"]:
                    await response_queue.put(welcome_text)
            except IndexError:
                await response_queue.put(welcome_text)

            async def process_input():
                loop = asyncio.get_event_loop()
                self.done = threading.Event()

                def task():
                    self.chat.handle_user_input(user_message, response_queue, loop)
                    loop.call_soon_threadsafe(response_queue.put_nowait, DONE_SENTINEL)
                    self.done.set()

                self._task_queue.put((task, self.done))
                await loop.run_in_executor(None, self.done.wait)

            if has_user_message:
                self.task = asyncio.create_task(process_input())

            finished = False
            async def generate():
                while True:
                    chunk = await response_queue.get()
                    if isinstance(chunk, ChatCompletionMessage):
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
                            'delta': {'content': chunk + "\n\n" if type(chunk) != object else ""},
                            'finish_reason': None
                        }]
                    })}\n\n"
                
                """if not is_reset:
                    db, cursor = self.init_db()
                    cursor.execute("UPDATE chats SET messages = ? WHERE identifier == ?;", (str(self.chat.agentLLM.messages), chat_id))
                    self.close_db(db, cursor)"""

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
        """Run the Uvicorn server with a shorter timeout for faster shutdown."""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            timeout_keep_alive=5,  # Reduce keep-alive timeout
            timeout_graceful_shutdown=2  # Reduce graceful shutdown timeout
        )

if __name__ == "__main__":
    # This block is just for testing; actual usage is through main.py
    pass

