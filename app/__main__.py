"""
Telcenter Partner - S09: Partner General Information Service

Main entry point for the service.
This service manages partner connection information and provides:
- HTTP APIs (H25, H26) for Partner Portal
- RabbitMQ APIs (A12) for internal Partner services
"""

import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from .services import partner_information_service
from .amqp import A12Handler


def main():
    """Main entry point for S09 Partner General Information Service."""
    print("[S09] Starting Partner General Information Service...")
    
    from . import app

    # Initialize and start A12 RabbitMQ handler
    a12_handler = A12Handler(partner_information_service)
    
    # Start RabbitMQ consumers in background threads
    rabbitmq_enabled = os.getenv('RABBITMQ_ENABLED', 'true').lower() == 'true'
    if rabbitmq_enabled:
        try:
            a12_handler.start()
            print("[S09] A12 RabbitMQ handler started")
        except Exception as e:
            print(f"[S09] Warning: Failed to start RabbitMQ handler: {e}")
            print("[S09] Service will continue without RabbitMQ support")
    else:
        print("[S09] RabbitMQ is disabled, skipping A12 handler")
    
    # Get server configuration
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"[S09] Starting HTTP server on {host}:{port}")
    print(f"[S09] API documentation available at http://{host}:{port}/api")

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
