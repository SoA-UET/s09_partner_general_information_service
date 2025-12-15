from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv('MONGO_URL')

if not MONGO_URL:
    print(f"Environment variable MONGO_URL is missing.")
    import sys
    sys.exit(1)

client = MongoClient(MONGO_URL)
db = client.get_default_database()

# NOTE: Change collection names as appropriate.

conversations_collection = db.conversations
messages_collection = db.messages

# Partner database collections
partner_db = client.get_database("telcenter_partner_partner")
partner_information_collection = partner_db.information
