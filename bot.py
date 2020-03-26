import re
import asyncio

import motor.motor_asyncio

from telethon.sync import TelegramClient, events
from telethon.sessions.string import StringSession
from telethon.tl.types import Channel, InputPeerUser
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from telethon.errors.rpcerrorlist import UserAlreadyParticipantError, FloodWaitError, ChannelPrivateError

from config import API_ID, API_HASH, SESSION, MONGODB_URL

import logging
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

joinchat_pattern = ".*t\.me\/joinchat\/([^\ \/\.]+)"

mongoDb = motor.motor_asyncio.AsyncIOMotorClient(
    MONGODB_URL, retryWrites=False)

db = mongoDb.get_default_database()

subscribes = db.subscribes

users = db.users


async def update_user(user):
    return await users.find_one_and_update(
        {'_id': user.user_id},
        {'$set': {'access_hash': user.access_hash}},
        upsert=True
    )


async def load_users(user_ids):
    return [InputPeerUser(user_id=user['_id'], access_hash=user['access_hash']) for user in await users.find({'_id': {'$in': user_ids}}).to_list(None)]


async def load_subscribes(channel_id):
    return await load_users([sub['user_id'] for sub in await subscribes.find({'channel_id': channel_id}).to_list(None)])


async def save_subscribe(user, channel):
    return await subscribes.find_one_and_update(
        {'user_id': user.user_id, 'channel_id': channel.id},
        {'$set': {'user_id': user.user_id, 'channel_id': channel.id}},
        upsert=True
    )


async def subscribe_channel(channel, event):
    if type(channel) == Channel and channel.broadcast:
        sender = await event.get_input_sender()
        subscribe = await save_subscribe(sender, channel)
        if not subscribe:
            await event.reply('Subscribed')
        else:
            await event.reply('Already subscribed')
        await update_user(sender)


def run_bot():

    with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:

        @client.on(events.NewMessage(incoming=True, pattern=joinchat_pattern, func=lambda e: e.is_private))
        async def joinchat(event):
            try:
                updates = await client(ImportChatInviteRequest(event.pattern_match.group(1)))
                await subscribe_channel(updates.chats[0], event)
            except UserAlreadyParticipantError:
                channel = await client.get_entity(event.message.message)
                await subscribe_channel(channel, event)
            except FloodWaitError:
                await event.reply('Try again later')
            except:
                await event.reply('Imposible subscribe channel')

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not re.match(joinchat_pattern, e.message.message)))
        async def private_handler(event):
            channel = None
            if event.message.fwd_from:
                try:
                    channel = await client.get_entity(event.message.fwd_from.channel_id)
                except ChannelPrivateError:
                    await event.reply('Channel is private')
                except:
                    pass
            if not channel:
                try:
                    channel = await client.get_entity(event.message.message)
                except:
                    pass
            if channel:
                await client(JoinChannelRequest(channel))
                await subscribe_channel(channel, event)

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_channel and not e.is_group))
        async def channel_handler(event):
            message = event.message
            channel_id = message.to_id.channel_id
            await asyncio.gather(*[client.forward_messages(user, message) for user in await load_subscribes(channel_id)])

        client.run_until_disconnected()


if __name__ == '__main__':
    run_bot()
