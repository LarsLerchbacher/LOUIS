"""
	This file is part of LOUIS
	LOUIS is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
	LOUIS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details
	
	You should have received a copy of the GNU Affero General Public License along with LOUIS. If not, see <https://www.gnu.org/licenses/>.
"""
 
import threading
import time
import asyncio
import logging
from ChatHandler import ChatHandler
from Config import Config
import queue


class TUI():
    """Text User Interface for interacting with the AI.
    
    This class handles the TUI chat interface, including user input and displaying responses.
    """
    def __init__(self, logger: logging.Logger, session_logger: logging.Logger, config: Config, state=None):
        """Initialize the TUI with a logger, session logger, and configuration.
        
        Args:
            logger (logging.Logger): The logger for logging messages.
            session_logger (logging.Logger): The logger for session-specific logging.
            config (Config): The configuration object for the application.
            state (State): The state object for managing state data.
        """
        self.logger = logger
        self.session_logger = session_logger
        self.config = config
        self.state = state
        self.tui_chat()
        

    def thinking_animation(self, stop_event):
        """Display a thinking animation while the AI is processing."""
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        while not stop_event.is_set():
            for char in chars:
                print(f"\r{char}", end="", flush=True)
                time.sleep(0.1)
                if stop_event.is_set():
                    break

    def run_chat_handler(self, user_input, stop_event, response_queue):
        """Run the ChatHandler in a separate thread and stream responses from the queue."""
        self.chat = ChatHandler(self.config, self.logger, self.session_logger, self.state)
        self.chat.initialize()
        async def chat():
            self.chat.handle_user_input(user_input, response_queue)
            stop_event.set()

        self.task = asyncio.run(chat())

    def tui_chat(self):
        """Handle chat in the TUI with threading"""
        self.session_logger.assistant(f"Hello! I'm {self.config.get_value("name")}, your token-efficient AI assistant based on the LOUIS project. My source code is available under the AGPL license: https://github.com/LarsLerchbacher/LOUIS")

        response_queue = queue.Queue()

        while True:
            try:
                user_input = input("> ")
            
                if user_input == "/exit":
                    break
                elif user_input == "/reset" and self.chat:
                    self.chat.summarize()
                    continue
                elif user_input == "/new" and self.chat:
                    self.chat.agentLLM.reset(False)
                    continue
    
                self.stop_event = threading.Event()
                thinking_thread = threading.Thread(target=self.thinking_animation, args=(self.stop_event,))
                chat_thread = threading.Thread(target=self.run_chat_handler, args=(user_input, self.stop_event, response_queue))
                
                thinking_thread.start()
                chat_thread.start()
                
                # Join threads with a timeout to allow for keyboard interrupts
                while thinking_thread.is_alive() or chat_thread.is_alive():
                    try:
                        thinking_thread.join(timeout=0.1)
                        chat_thread.join(timeout=0.1)
                    except KeyboardInterrupt:
                        print("\nCtrl + C detected. Stopping program immediately...")
                        
                        # Set the stop event to signal threads to stop
                        self.stop_event.set()
                        
                        # Cancel any ongoing tasks
                        if hasattr(self, 'task') and self.task:
                            self.task.cancel()
                        
                        # Forcefully terminate the threads
                        thinking_thread.join(timeout=0.1)
                        chat_thread.join(timeout=0.1)
                        
                        break
                
            except KeyboardInterrupt:
                print("\nCtrl + C detected. Stopping program immediately...")
                
                # Set the stop event to signal threads to stop
                if 'stop_event' in locals():
                    self.stop_event.set()
                
                # Cancel any ongoing tasks
                if hasattr(self, 'task') and self.task:
                    self.task.cancel()
                
                break
