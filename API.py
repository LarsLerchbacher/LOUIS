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
import queue
import sqlite3
import requests
from mistralai.client.models import AssistantMessage, ToolCall, FunctionCall

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
        
        self.base_url = str(self.config.get_value("openwebui_url")) + "/api/v1"
        self.token = self.config.get_value('openwebui_token')
        self.ca_cert = self.config.get_value("openwebui_ca_cert")
        if not self.token:
            self.logger.error("Could not load Open WebUI token from config. Please make sure to include it in 'openwebui_token'.")
            quit(1)
        
    
    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
    }
    
    def get_chat_history(self, chat_id):
        msgs = []
        chat_content = requests.get(f"{self.base_url}/chats/{chat_id}", headers=self._get_headers(), verify=self.ca_cert).json()
        msg_id = chat_content["chat"]["history"]["currentId"]
        msg = chat_content["chat"]["history"]["messages"][msg_id]
        msg_id = msg["parentId"]
        while not msg_id == None:
            msg = chat_content["chat"]["history"]["messages"][msg_id]
            
            if msg["role"] != "assistant" or type(msg["content"]) == str:
                msgs.append({"role": msg["role"], "content": msg["content"]})
            else:
                msgs.append({"role": msg["role"], "content": msg["output"][0]["content"][0]["text"]})
        
            msg_id = msg["parentId"]
        
        return msgs
    
    def clean_up_chats(self):
        db, cursor = self.init_db()

        chats = requests.get(self.base_url + "/chats/?page=1", headers=self._get_headers(), verify=self.ca_cert).json()
        open_webui_ids = [chat["id"] for chat in chats]
        for chat_id in [row[0] for row in cursor.execute("SELECT identifier FROM chats;").fetchall()]:
            if chat_id not in open_webui_ids:
                cursor.execute("DELETE FROM chats WHERE identifier == ?;", (chat_id, ))
        
        self.close_db(db, cursor)

    def safe_json_loads(self, s):
        """Necesary to avoid problems when the LLM uses newlines"""
        s = s.replace("\n", "\\n") # Replace actual newlines with python escape sequence
        s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # remove all other control chars
        return json.loads(s) 

    async def _handle_reset_command(self, chat_id: str, response_queue: asyncio.Queue) -> None:
        """
        Handle the /reset command by creating a new session and storing the old session's summary.
        """

        db, cursor = self.init_db()

        self.chat.agentLLM.messages.append({"role": "user", "content": """
**Summarize the current conversation in 3-5 bullet points.**
Focus only on **new information, decisions, or unresolved questions** since the last summary.
Assume the reader already knows the prior context.
If no meaningful progress was made, state: *"No significant updates since last summary."*
Do not acknowledge this command or respond conversationally, just summarize.

**Constraints:**
- Max 5 bullet points.
- No fluff, no philosophy, no sarcasm (unless critical).
- Prioritize actionable or contextual details.

**Summary:**"""})
        
        response = self.chat.agentLLM.client.chat.complete(
            model=self.chat.agentLLM.model,
            messages=self.chat.agentLLM.messages,
            temperature=0.0,
        )
        
        old_summary = cursor.execute("SELECT summary FROM chats WHERE identifier == ?;", (chat_id,)).fetchone()[0] or ""
        new_summary = response.choices[0].message.content if response.choices[0].message.content else "No significant updates since last summary"
        summary = old_summary + new_summary
        cursor.execute("UPDATE chats SET summary = ? WHERE identifier == ?;", (summary, chat_id))
            
        
        # Create a new session in OpenWebUI
        new_chat_data = {
            "model": self.config.get_value("name"),
            "messages": [
                {
                    "role": "system",
                    "content": self.chat.agentLLM.prompt
                },
                {
                    "role": "user",
                    "content": f"Previous session summary: {summary}"
                }
            ]
        }
        
        cursor.execute(
            "UPDATE chats SET messages = ? WHERE identifier == ?;",
            (str(new_chat_data["messages"]), chat_id)
        )

        self.close_db(db, cursor)
        
        # Notify the user
        await response_queue.put("Session reset successfully. Editing messages from above this message will no longer work as expected, as the messages don't exist for the AI anymore. It only has a summary of the most important events.")

    def _setup_routes(self):
        DONE_SENTINEL = object()

        @self.app.post("/chat/completions")
        async def chat_completions(request: Request):
            self.clean_up_chats()
            data = await request.json()
            
            chat_id = None
            try:
                chats = requests.get(self.base_url + "/chats/?page=1", headers=self._get_headers(), verify=self.ca_cert).json()
                for chat in chats:
                    chat_content = requests.get(f"{self.base_url}/chats/{chat["id"]}", headers=self._get_headers(), verify=self.ca_cert).json()
                    
                    i = len(data["messages"])
                    found = True 
                    msg_id = chat_content["chat"]["history"]["currentId"]
                    msg = chat_content["chat"]["history"]["messages"][msg_id]
                    msg_id = msg["parentId"]
                    while not msg_id == None:
                        msg = chat_content["chat"]["history"]["messages"][msg_id]
                        i -= 1
                        
                        if i < 0:
                            found = False
                            break
                        
                        if data["messages"][i]["role"] != msg["role"]:
                            found = False
                            break

                        else:
                            if msg["role"] == "assistant":
                                if data["messages"][i]["content"] != msg["output"][0]["content"][0]["text"]:
                                    found = False
                                    break
                    
                        msg_id = msg["parentId"]
                    
                    if found == False:
                        continue

                    chat_id = chat["id"]
                    break
            except Exception as e:
                self.logger.error(e)

            response_queue = asyncio.Queue()
            has_user_message = False
            is_reset = False

            db, cursor = self.init_db()
            if chat_id == None:
                self.logger.error(f"Session not found. Please make sure you access the model via {self.base_url.removesuffix("/api/v1")}. Other OpenWebUI instances will not work.")
                await response_queue.put("An error occurred")
            elif chat_id not in [row[0] for row in cursor.execute("SELECT identifier FROM chats;").fetchall()]:
                self.chat.agentLLM.messages = [{"role": "system", "content": self.chat.agentLLM.prompt}]
                self.chat.agentLLM.messages.extend(data["messages"][:-1])
                user_message = data["messages"][-1]["content"]
                has_user_message = True
                cursor.execute("INSERT INTO chats (identifier, messages) VALUES ( ?, ?);", (chat_id, str(self.chat.agentLLM.messages)))
                await response_queue.put(f"Hello! I'm {self.config.get_value("name")}, your token-efficient AI assistant based on the LOUIS project. My source code is available under the AGPL license: https://github.com/LarsLerchbacher/LOUIS")
            else:
                self.chat.agentLLM.messages = eval(cursor.execute("SELECT messages FROM chats WHERE identifier == ?;", (chat_id, )).fetchone()[0])
                user_message = data["messages"][-1]["content"]
                has_user_message = True

            self.close_db(db, cursor)
            
            # Check if the user wants to reset the session
            if has_user_message:
                if user_message.strip().lower() == "/reset":
                    is_reset = True
                    await self._handle_reset_command(chat_id, response_queue)

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
                            'delta': {'content': chunk + "\n\n" if type(chunk) != object else ""},
                            'finish_reason': None
                        }]
                    })}\n\n"
                
                if not is_reset:
                    db, cursor = self.init_db()
                    cursor.execute("UPDATE chats SET messages = ? WHERE identifier == ?;", (str(self.chat.agentLLM.messages), chat_id))
                    self.close_db(db, cursor)

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

