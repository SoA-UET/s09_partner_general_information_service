"""
A12 RabbitMQ Handler

Handles RabbitMQ communication for the A12 API group:
- A12a: Responds to get_core_info requests from S17
- A12b: Sends core_update events to S17
"""

import os
import threading
from typing import Any
from ..services.MessageQueueService import MessageQueueService


class A12Handler:
    """
    Handles A12 RabbitMQ API for Partner General Information Service.
    
    A12a: S17 → S09 (get_core_info method)
    A12b: S09 → S17 (core_update event)
    """
    
    def __init__(self, partner_information_service):
        """
        Initialize the A12 handler.
        
        Args:
            partner_information_service: The PartnerInformationService instance
        """
        self.partner_service = partner_information_service
        self.mq_service: MessageQueueService | None = None
        self.mq_lock = threading.Lock()
        
        # Queue names from environment or defaults
        self.a12a_request_queue = os.getenv(
            "A12A_REQUEST_QUEUE",
            "telcenter_partner_s09_a12a_requests"
        )
        self.a12a_response_queue = os.getenv(
            "A12A_RESPONSE_QUEUE",
            "telcenter_partner_s09_a12a_responses"
        )
        self.a12b_event_queue = os.getenv(
            "A12B_EVENT_QUEUE",
            "telcenter_partner_s17_core_update_events"
        )
        
        # Consumer threads
        self.threads: list[threading.Thread] = []
        self.num_threads = int(os.getenv("A12_CONSUMER_THREADS", "2"))
        
        # Method map for A12a
        self.method_map = {
            "get_core_info": self._handle_get_core_info,
        }
    
    def start(self):
        """Start the RabbitMQ consumer threads."""
        print(f"[A12Handler] Starting {self.num_threads} consumer threads...")
        
        # Initialize main MQ service for publishing
        self.mq_service = MessageQueueService()
        self.mq_service.declare_queue(self.a12a_request_queue)
        self.mq_service.declare_queue(self.a12a_response_queue)
        self.mq_service.declare_queue(self.a12b_event_queue)
        
        # Register as event listener for core_update events
        self.partner_service.register_event_listener(self._on_core_update)
        
        # Start consumer threads
        self.threads = [
            threading.Thread(target=self._consume_requests, daemon=True)
            for _ in range(self.num_threads)
        ]
        
        for thread in self.threads:
            thread.start()
        
        print(f"[A12Handler] Started listening on queue: {self.a12a_request_queue}")
    
    def wait(self):
        """Wait for all consumer threads to complete."""
        for thread in self.threads:
            thread.join()
    
    def _consume_requests(self):
        """Background thread to consume A12a requests."""
        with self.mq_lock:
            if self.mq_service is None:
                return
            mq = self.mq_service.clone()
        
        mq.declare_queue(self.a12a_request_queue)
        mq.declare_queue(self.a12a_response_queue)
        
        mq.register_callback(self.a12a_request_queue, self._handle_message)
        mq.start_consuming()
    
    def _handle_message(self, message: dict):
        """Handle incoming A12a request message."""
        request_id = message.get("id")
        
        if not request_id or not isinstance(request_id, str):
            print("[A12Handler] Ignoring message without valid id")
            return
        
        result_status = "success"
        result_content: Any = None
        
        try:
            result_content = self._process_request(message)
        except Exception as e:
            result_status = "error"
            result_content = str(e)
        
        # Send response
        response = {
            "id": request_id,
            "result": {
                "status": result_status,
                "content": result_content,
            }
        }
        
        with self.mq_lock:
            if self.mq_service:
                self.mq_service.publish_message(self.a12a_response_queue, response)
    
    def _process_request(self, message: dict) -> Any:
        """Process an A12a request and return the result."""
        method_name = message.get("method", "")
        
        if not method_name:
            raise ValueError("Message missing 'method' field")
        
        method = self.method_map.get(method_name)
        if method is None:
            raise ValueError(f"Unknown method: {method_name}")
        
        params = message.get("params", {})
        if isinstance(params, dict):
            return method(**params)
        elif isinstance(params, list):
            return method(*params)
        else:
            return method()
    
    def _handle_get_core_info(self) -> dict:
        """
        Handle get_core_info method (A12a).
        Returns core connection information.
        """
        return self.partner_service.get_core_info()
    
    def _on_core_update(self, event_name: str, params: dict):
        """
        Event listener callback for core_update events (A12b).
        Publishes the event to the A12b event queue.
        """
        if event_name != "core_update":
            return
        
        message = {
            "event": "core_update",
            "params": params,
        }
        
        with self.mq_lock:
            if self.mq_service:
                self.mq_service.publish_message(self.a12b_event_queue, message)
                print(f"[A12Handler] Published core_update event to {self.a12b_event_queue}")
