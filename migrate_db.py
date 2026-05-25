import sys
import os

# Add to path just in case
sys.path.append('/Users/leninm/Documents/Work/AI_trader')

from database import initialize_database, create_user, assign_orphaned_records_to_user, get_user_by_email, update_user_api_keys
from auth import hash_password
from config import KITE_API_KEY, KITE_API_SECRET, KITE_REQUEST_TOKEN, NEWS_API_KEY, GOOGLE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def migrate():
    print("Initializing DB...")
    initialize_database()
    
    email = "leninmariajoseph@gmail.com"
    user = get_user_by_email(email)
    if not user:
        print("Creating user Lenin...")
        user_id = create_user("Lenin", email, hash_password("Trade@0505"))
        keys = {
            "kite_api_key": KITE_API_KEY,
            "kite_api_secret": KITE_API_SECRET,
            "kite_request_token": KITE_REQUEST_TOKEN,
            "news_api_key": NEWS_API_KEY,
            "google_api_key": GOOGLE_API_KEY,
            "telegram_bot_token": TELEGRAM_BOT_TOKEN,
            "telegram_chat_id": TELEGRAM_CHAT_ID
        }
        update_user_api_keys(user_id, keys)
    else:
        user_id = user['id']
        print(f"User Lenin already exists with ID {user_id}")

    print("Assigning orphaned records...")
    assign_orphaned_records_to_user(user_id)
    print("Migration complete!")

if __name__ == '__main__':
    migrate()
