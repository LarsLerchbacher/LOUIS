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
import sqlite3
import requests
from mistralai.client.models import AssistantMessage, ToolCall, FunctionCall

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
        
        self.done = threading.Event()
        self._task_queue.put((self.initialize, self.done))
        self.done.wait()
    
    def _worker_loop(self):
        while True:
            task, self.done = self._task_queue.get()
            task()
            self.done.set() 
    
    def initialize(self):
        
        self.chat = ChatHandler(self.config, self.logger, self.session_logger)
        self.chat.initialize() 
        
        db = sqlite3.connect("database.sqlite")
        cursor = sqlite3.Cursor(db)
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier STRING NOT NULL,
            messages STRING 
        );""")
        
        db.commit()
        cursor.close()
        db.close()
        
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
        db = sqlite3.connect("database.sqlite")
        cursor = sqlite3.Cursor(db)

        chats = requests.get(self.base_url + "/chats/?page=1", headers=self._get_headers(), verify=self.ca_cert).json()
        open_webui_ids = [chat["id"] for chat in chats]
        for chat_id in [row[0] for row in cursor.execute("SELECT identifier FROM chats;").fetchall()]:
            if chat_id not in open_webui_ids:
                cursor.execute("DELETE FROM chats WHERE identifier == ?;", (chat_id, ))
        
        db.commit()
        cursor.close()
        db.close()
    
    def safe_json_loads(self, s):
        """Necesary to avoid problems when the LLM uses newlines"""
        s = s.replace("\n", "\\n") # Replace actual newlines with python escape sequence
        s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # remove all other control chars
        return json.loads(s) 

    def _setup_routes(self):
        DONE_SENTINEL = object()

        @self.app.post("/chat/completions")
        async def chat_completions(request: Request):
            self.clean_up_chats()
            data = await request.json()
            
            db = sqlite3.connect("database.sqlite")
            cursor = sqlite3.Cursor(db)
            
            # TODO: Get openwebui chat id by reading chat list and comparing conversations with current messages
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
            if chat_id == None:
                self.logger.error(f"Session not found. Please make sure you access the model via {self.base_url.removesuffix("/api/v1")}. Other OpenWebUI instances will not work.")
                response_queue.put("An error occurred")
            elif chat_id not in [row[0] for row in cursor.execute("SELECT identifier FROM chats;").fetchall()]:
                self.chat.agentLLM.messages = [{"role": "system", "content": self.chat.agentLLM.prompt}]
                self.chat.agentLLM.messages.extend(data["messages"][:-1])
                user_message = data["messages"][-1]["content"]
                cursor.execute("INSERT INTO chats (identifier, messages) VALUES ( ?, ?);", (chat_id, str(self.chat.agentLLM.messages)))
            else:
                self.chat.agentLLM.messages = eval(cursor.execute("SELECT messages FROM chats WHERE identifier == ?;", (chat_id, )).fetchone()[0])
                user_message = data["messages"][-1]["content"]

            async def process_input():
                loop = asyncio.get_event_loop()
                self.done = threading.Event()

                def task():
                    self.chat.handle_user_input(user_message, response_queue, loop)
                    loop.call_soon_threadsafe(response_queue.put_nowait, DONE_SENTINEL)
                    self.done.set()

                self._task_queue.put((task, self.done))
                await loop.run_in_executor(None, self.done.wait)

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
                
                cursor.execute("UPDATE chats SET messages = ? WHERE identifier == ?;", (str(self.chat.agentLLM.messages), chat_id))

                db.commit()
                cursor.close()
                db.close()

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

