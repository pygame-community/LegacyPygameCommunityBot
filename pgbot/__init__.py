"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file is the main file of pgbot subdir
"""

import asyncio
import datetime
import io
import os
import re
import random
import signal
import sys
from typing import Union

import discord
import pygame
import snakecore

from pgbot import commands, common, db, emotion, routine, utils


async def _init():
    """
    Startup call helper for pygame bot
    """

    await snakecore.init(global_client=common.bot)

    if not common.TEST_MODE:
        # when we are not in test mode, we want stout/stderr to appear on a console
        # in a discord channel
        sys.stdout = sys.stderr = common.stdout = io.StringIO()

    print("The PygameCommunityBot is now online!")
    print("Server(s):")

    for server in common.bot.guilds:
        prim = ""

        if common.guild is None and (
            common.GENERIC or server.id == common.ServerConstants.SERVER_ID
        ):
            prim = "| Primary Guild"
            common.guild = server

        print(" -", server.name, "| Number of channels:", len(server.channels), prim)
        if common.GENERIC:
            continue

        for channel in server.channels:
            if channel.id == common.ServerConstants.DB_CHANNEL_ID:
                common.db_channel = channel
                await db.init()
            elif channel.id == common.ServerConstants.LOG_CHANNEL_ID:
                common.log_channel = channel
            elif channel.id == common.ServerConstants.ARRIVALS_CHANNEL_ID:
                common.arrivals_channel = channel
            elif channel.id == common.ServerConstants.GUIDE_CHANNEL_ID:
                common.guide_channel = channel
            elif channel.id == common.ServerConstants.ROLES_CHANNEL_ID:
                common.roles_channel = channel
            elif channel.id == common.ServerConstants.ENTRIES_DISCUSSION_CHANNEL_ID:
                common.entries_discussion_channel = channel
            elif channel.id == common.ServerConstants.CONSOLE_CHANNEL_ID:
                common.console_channel = channel
            elif channel.id == common.ServerConstants.RULES_CHANNEL_ID:
                common.rules_channel = channel
            for key, value in common.ServerConstants.ENTRY_CHANNEL_IDS.items():
                if channel.id == value:
                    common.entry_channels[key] = channel


async def init():
    """
    Startup call helper for pygame bot
    """
    try:
        await _init()
    except Exception:
        # error happened in the first init sequence. report error to stdout/stderr
        # note that the chances of this happening are pretty slim, but you never know
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        raise

    routine.handle_console.start()
    routine.routine.start()

    if common.guild is None:
        raise RuntimeWarning(
            "Primary guild was not set. Some features of bot would not run as usual."
            " People running commands via DMs might face some problems"
        )


def format_entries_message(
    msg: discord.Message, entry_type: str
) -> tuple[str, list[dict[str, Union[str, bool]]]]:
    """
    Formats an entries message to be reposted in discussion channel
    """
    if entry_type != "":
        title = f"New {entry_type.lower()} in #{common.ZERO_SPACE}{common.entry_channels[entry_type].name}"
    else:
        title = ""

    attachments = ""
    if msg.attachments:
        for i, attachment in enumerate(msg.attachments):
            attachments += f" • [Link {i + 1}]({attachment.url})\n"
    else:
        attachments = "No attachments"

    desc = msg.content if msg.content else "No description provided."

    fields = [
        {"name": "**Posted by**", "value": msg.author.mention, "inline": True},
        {
            "name": "**Original msg.**",
            "value": f"[View]({msg.jump_url})",
            "inline": True,
        },
        {"name": "**Attachments**", "value": attachments, "inline": True},
        {"name": "**Description**", "value": desc, "inline": True},
    ]
    return title, fields


def entry_message_validity_check(
    message: discord.Message, min_chars=32, max_chars=float("inf")
):
    """Checks if a message posted in a showcase channel for projects has the right format.

    Returns:
        bool: True/False
    """
    url_regex_pattern = r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])"
    # https://stackoverflow.com/a/6041965/14826938

    search_obj = re.search(
        url_regex_pattern, (message.content if message.content else "")
    )
    link_in_msg = bool(search_obj)
    first_link_str = search_obj.group() if link_in_msg else ""

    if (
        message.content
        and (link_in_msg and len(message.content) > len(first_link_str))
        and min_chars < len(message.content) < max_chars
    ):
        return True

    elif (message.content or message.reference) and message.attachments:
        return True

    return False


async def delete_bad_entry_and_warning(
    entry_msg: discord.Message, warn_msg: discord.Message, delay: float = 0.0
):
    """A function to pardon a bad entry message with a grace period. If this coroutine is not cancelled during the
    grace period specified in `delay` in seconds, it will delete both `entry_msg` and `warn_msg`, if possible.

    Args:
        entry_msg (discord.Message): [description]
        warn_msg (discord.Message): [description]
        delay (float, optional): [description]. Defaults to 0..
    """
    try:
        await asyncio.sleep(delay)  # allow cancelling during delay
    except asyncio.CancelledError:
        return

    finally:
        for msg in (entry_msg, warn_msg):
            # don't error here if messages were already deleted
            try:
                await msg.delete()
            except discord.NotFound:
                pass


async def member_join(member: discord.Member):
    """
    This function handles the greet message when a new member joins
    """
    if common.TEST_MODE or member.bot or common.GENERIC:
        # Do not greet people in test mode, or if a bot joins
        return

    greet = random.choice(common.BOT_WELCOME_MSG["greet"])
    check = random.choice(common.BOT_WELCOME_MSG["check"])

    grab = random.choice(common.BOT_WELCOME_MSG["grab"])
    end = random.choice(common.BOT_WELCOME_MSG["end"])

    # This function is called right when a member joins, even before the member
    # finishes the join screening. So we wait for that to happen and then send
    # the message. Wait for a maximum of six hours.
    for _ in range(10800):
        await asyncio.sleep(2)

        if not member.pending:
            # Don't use embed here, because pings would not work
            await common.arrivals_channel.send(
                f"{greet} {member.mention}! {check} "
                + f"{common.guide_channel.mention}{grab} "
                + f"{common.roles_channel.mention}{end}"
            )
            # new member joined, yaayyy, snek is happi
            await emotion.update("happy", 20)
            return


async def clean_db_member(member: discord.Member):
    """
    This function silently removes users from database messages
    """
    for table_name in ("stream", "reminders", "clock"):
        async with db.DiscordDB(table_name) as db_obj:
            data = db_obj.get({})
            if member.id in data:
                data.pop(member)
                db_obj.write(data)


async def message_delete(msg: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    if msg.id in common.cmd_logs.keys():
        del common.cmd_logs[msg.id]

    elif msg.author.id == common.bot.user.id:
        for log in common.cmd_logs.keys():
            if common.cmd_logs[log].id is not None:
                if common.cmd_logs[log].id == msg.id:
                    del common.cmd_logs[log]
                    return

    if common.GENERIC or common.TEST_MODE:
        return

    if msg.channel in common.entry_channels.values():
        if (
            msg.channel.id == common.ServerConstants.ENTRY_CHANNEL_IDS["showcase"]
            and msg.id in common.entry_message_deletion_dict
        ):  # for case where user deletes their bad entry by themselves
            deletion_data_list = common.entry_message_deletion_dict[msg.id]
            deletion_task = deletion_data_list[0]
            if not deletion_task.done():
                deletion_task.cancel()
                try:
                    warn_msg = await msg.channel.fetch_message(
                        deletion_data_list[1]
                    )  # warning and entry message were already deleted
                    await warn_msg.delete()
                except discord.NotFound:
                    pass

            del common.entry_message_deletion_dict[msg.id]

        async for message in common.entries_discussion_channel.history(
            around=msg.created_at, limit=5
        ):
            try:
                link = message.embeds[0].fields[1].value
                if not isinstance(link, str):
                    continue

                if int(link.split("/")[6][:-1]) == msg.id:
                    await message.delete()
                    break

            except (IndexError, AttributeError):
                pass


async def message_edit(old: discord.Message, new: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if new.content.startswith(common.PREFIX):
        try:
            if new.id in common.cmd_logs.keys():
                await commands.handle(new, common.cmd_logs[new.id])
        except discord.HTTPException:
            pass

    if common.GENERIC or common.TEST_MODE:
        return

    if new.channel in common.entry_channels.values():
        embed_repost_edited = False
        if new.channel.id == common.ServerConstants.ENTRY_CHANNEL_IDS["showcase"]:
            if not entry_message_validity_check(new):
                if new.id in common.entry_message_deletion_dict:
                    deletion_data_list = common.entry_message_deletion_dict[new.id]
                    deletion_task = deletion_data_list[0]
                    if deletion_task.done():
                        del common.entry_message_deletion_dict[new.id]
                    else:
                        try:
                            deletion_task.cancel()  # try to cancel deletion after noticing edit by sender
                            warn_msg = await new.channel.fetch_message(
                                deletion_data_list[1]
                            )
                            deletion_datetime = (
                                datetime.datetime.utcnow()
                                + datetime.timedelta(minutes=2)
                            )
                            await warn_msg.edit(
                                content=(
                                    "I noticed your edit, but: Your entry message must contain an attachment or a (Discord recognized) link to be valid."
                                    " If it doesn't contain any characters but an attachment, it must be a reply to another entry you created."
                                    f" If no attachments are present, it must contain at least 32 characters (including any links, but not links alone)."
                                    f" If you meant to comment on another entry, please delete your message and go to {common.entries_discussion_channel.mention}."
                                    " If no changes are made, your entry message will be"
                                    f" deleted {snakecore.utils.create_markdown_timestamp(deletion_datetime, tformat='R')}."
                                )
                            )
                            common.entry_message_deletion_dict[new.id] = [
                                asyncio.create_task(
                                    delete_bad_entry_and_warning(
                                        new, warn_msg, delay=120
                                    )
                                ),
                                warn_msg.id,
                            ]
                        except discord.NotFound:  # cancelling didn't work, warning and entry message were already deleted
                            del common.entry_message_deletion_dict[new.id]

                else:  # an edit led to an invalid entry message from a valid one
                    deletion_datetime = datetime.datetime.utcnow() + datetime.timedelta(
                        minutes=2
                    )
                    warn_msg = await new.reply(
                        "Your entry message must contain an attachment or a (Discord recognized) link to be valid."
                        " If it doesn't contain any characters but an attachment, it must be a reply to another entry you created."
                        f" If no attachments are present, it must contain at least 32 characters (including any links, but not links alone)."
                        f" If you meant to comment on another entry, please delete your message and go to {common.entries_discussion_channel.mention}."
                        " If no changes are made, your entry message will be"
                        f" deleted {snakecore.utils.create_markdown_timestamp(deletion_datetime, tformat='R')}."
                    )

                    common.entry_message_deletion_dict[new.id] = [
                        asyncio.create_task(
                            delete_bad_entry_and_warning(new, warn_msg, delay=120)
                        ),
                        warn_msg.id,
                    ]
                return

            elif (
                entry_message_validity_check(new)
                and new.id in common.entry_message_deletion_dict
            ):  # an invalid entry was corrected
                deletion_data_list = common.entry_message_deletion_dict[new.id]
                deletion_task = deletion_data_list[0]
                if not deletion_task.done():  # too late to do anything
                    try:
                        deletion_task.cancel()  # try to cancel deletion after noticing valid edit by sender
                        warn_msg = await new.channel.fetch_message(
                            deletion_data_list[1]
                        )
                        await warn_msg.delete()
                    except discord.NotFound:  # cancelling didn't work, warning and entry message were already deleted
                        pass
                del common.entry_message_deletion_dict[new.id]

        async for message in common.entries_discussion_channel.history(
            around=old.created_at, limit=5
        ):
            try:
                embed = message.embeds[0]
                link = embed.fields[1].value
                if not isinstance(link, str):
                    continue

                if int(link.split("/")[6][:-1]) == new.id:
                    _, fields = format_entries_message(new, "")
                    await snakecore.utils.embed_utils.edit_embed_at(
                        message, fields=fields
                    )
                    embed_repost_edited = True
                    break

            except (IndexError, AttributeError):
                pass

        if not embed_repost_edited:
            if (datetime.datetime.utcnow() - old.created_at) < datetime.timedelta(
                minutes=5
            ):  # for new, recently corrected entry messages
                entry_type = "showcase"
                color = 0xFF8800

                title, fields = format_entries_message(new, entry_type)
                await snakecore.utils.embed_utils.send_embed(
                    common.entries_discussion_channel,
                    title=title,
                    color=color,
                    fields=fields,
                )


async def raw_reaction_add(payload: discord.RawReactionActionEvent):
    """
    Helper to handle a raw reaction added on discord
    """

    # Try to fetch channel without API call first
    channel = common.bot.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await common.bot.fetch_channel(payload.channel_id)
        except discord.HTTPException:
            return

    if not isinstance(channel, discord.TextChannel):
        return

    try:
        msg: discord.Message = await channel.fetch_message(payload.message_id)
    except discord.HTTPException:
        return

    if not msg.embeds or common.UNIQUE_POLL_MSG not in str(msg.embeds[0].footer.text):
        return

    for reaction in msg.reactions:
        async for user in reaction.users():
            if user.id == payload.user_id and not snakecore.utils.is_emoji_equal(
                payload.emoji, reaction.emoji
            ):
                await reaction.remove(user)


async def handle_message(msg: discord.Message):
    """
    Handle a message posted by user
    """
    if msg.type == discord.MessageType.premium_guild_subscription:
        await emotion.server_boost(msg)

    if msg.content.startswith(common.PREFIX):
        ret = await commands.handle(msg)
        if ret is not None:
            common.cmd_logs[msg.id] = ret

        if len(common.cmd_logs) > 100:
            del common.cmd_logs[list(common.cmd_logs.keys())[0]]

        await emotion.update("bored", -10)

    elif not common.TEST_MODE:
        await emotion.check_bonk(msg)

        # Check for these specific messages, do not try to generalise, because we do not
        # want the bot spamming the bydariogamer quote
        # no_mentions = discord.AllowedMentions.none()
        # if unidecode.unidecode(msg.content.lower()) in common.DEAD_CHAT_TRIGGERS:
        #     # ded chat makes snek sad
        #     await msg.channel.send(
        #         "good." if await emotion.get("anger") >= 60 else common.BYDARIO_QUOTE,
        #         allowed_mentions=no_mentions,
        #     )
        #     await emotion.update("happy", -8)

        if common.GENERIC:
            return

        if msg.channel in common.entry_channels.values():

            if msg.channel.id == common.ServerConstants.ENTRY_CHANNEL_IDS["showcase"]:
                if not entry_message_validity_check(msg):
                    deletion_datetime = datetime.datetime.utcnow() + datetime.timedelta(
                        minutes=2
                    )
                    warn_msg = await msg.reply(
                        "Your entry message must contain an attachment or a (Discord recognized) link to be valid."
                        " If it doesn't contain any characters but an attachment, it must be a reply to another entry you created."
                        f" If no attachments are present, it must contain at least 32 characters (including any links, but not links alone)."
                        f" If you meant to comment on another entry, please delete your message and go to {common.entries_discussion_channel.mention}."
                        " If no changes are made, your entry message will be"
                        f" deleted {snakecore.utils.create_markdown_timestamp(deletion_datetime, tformat='R')}."
                    )
                    common.entry_message_deletion_dict[msg.id] = [
                        asyncio.create_task(
                            delete_bad_entry_and_warning(msg, warn_msg, delay=120)
                        ),
                        warn_msg.id,
                    ]
                    return

                entry_type = "showcase"
                color = 0xFF8800
            else:
                entry_type = "resource"
                color = 0x0000AA

            title, fields = format_entries_message(msg, entry_type)
            await snakecore.utils.embed_utils.send_embed(
                common.entries_discussion_channel,
                title=title,
                color=color,
                fields=fields,
            )
        elif (
            random.random() < await emotion.get("happy") / 200
            or msg.author.id == 683852333293109269
        ):
            await emotion.dad_joke(msg)


def cleanup(*_):
    """
    Call cleanup functions
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db.quit())
    loop.run_until_complete(common.bot.close())
    loop.close()


def run():
    """
    Does what discord.Client.run does, except, handles custom cleanup functions
    and pygame init
    """

    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()  # pylint: disable=no-member
    common.window = pygame.display.set_mode((1, 1))

    # use signal.signal to setup SIGTERM signal handler, runs after event loop
    # closes
    signal.signal(signal.SIGTERM, cleanup)

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(common.bot.start(common.TOKEN))

    except KeyboardInterrupt:
        # Silence keyboard interrupt traceback (it contains no useful info)
        pass

    finally:
        cleanup()
