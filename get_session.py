from telethon.sync import TelegramClient
from telethon.sessions.string import StringSession
from config import API_ID, API_HASH

def create_session_string():

    session = StringSession()

    with TelegramClient(session, API_ID, API_HASH) as client:
        print(session.save())

if __name__ == '__main__':
    create_session_string()
    