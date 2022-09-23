"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file is the main file of pgbot subdir
"""

import asyncio
import datetime
import io
import logging
import os
import re
import random
import signal
import sys
from typing import Optional, Union

import discord
import pygame
import snakecore

import pgbot
from pgbot import common, exceptions, event_listeners, routine, utils
from pgbot.utils import (
    get_primary_guild_perms,
    message_delete_reaction_listener,
    parse_text_to_mapping,
)


def setup_logging():
    discord.utils.setup_logging(level=logging.ERROR)


async def _init():
    """
    Startup call helper for pygame bot
    """
    await snakecore.init(global_client=common.bot)

    if not common.TEST_MODE:
        # when we are not in test mode, we want stout/stderr to appear on a console
        # in a discord channel
        common.stdout = io.StringIO()
        sys.stdout = pgbot.utils.RedirectTextIOWrapper(
            sys.stdout.buffer, (common.stdout,)
        )
        sys.stderr = pgbot.utils.RedirectTextIOWrapper(
            sys.stderr.buffer, (common.stdout,)
        )

    print("The PygameCommunityBot is now online!")
    print("Server(s):")

    for guild in common.bot.guilds:
        prim = ""

        if common.guild is None and (
            common.GENERIC or guild.id == common.GuildConstants.GUILD_ID
        ):
            prim = "| Primary Guild"
            common.guild = guild

        print(" -", guild.name, "| Number of channels:", len(guild.channels), prim)
        if common.GENERIC:
            continue

        for channel in guild.channels:
            if channel.id == common.GuildConstants.STORAGE_CHANNEL_ID:
                if not common.TEST_MODE:
                    snakecore.config.conf.storage_channel = (
                        common.storage_channel
                    ) = channel
                await snakecore.storage.init_discord_storage()
            elif channel.id == common.GuildConstants.LOG_CHANNEL_ID:
                common.log_channel = channel
            elif channel.id == common.GuildConstants.ARRIVALS_CHANNEL_ID:
                common.arrivals_channel = channel
            elif channel.id == common.GuildConstants.GUIDE_CHANNEL_ID:
                common.guide_channel = channel
            elif channel.id == common.GuildConstants.ROLES_CHANNEL_ID:
                common.roles_channel = channel
            elif channel.id == common.GuildConstants.ENTRY_CHANNEL_IDS["discussion"]:
                common.entries_discussion_channel = channel
            elif channel.id == common.GuildConstants.CONSOLE_CHANNEL_ID:
                common.console_channel = channel
            elif channel.id == common.GuildConstants.RULES_CHANNEL_ID:
                common.rules_channel = channel
            for key, value in common.GuildConstants.ENTRY_CHANNEL_IDS.items():
                if channel.id == value:
                    common.entry_channels[key] = channel

    await common.bot.load_extension("pgbot.exts.core_commands.help")
    await common.bot.load_extension("pgbot.exts.core_commands.admin")
    await common.bot.load_extension("pgbot.exts.core_commands.user")

    async with snakecore.storage.DiscordStorage(
        "blacklist", list
    ) as storage_obj:  # disable blacklisted commands
        for cmd_qualname in storage_obj.obj:
            cmd = common.bot.get_command(cmd_qualname)
            if cmd is not None:
                cmd.enabled = False


async def init():
    """
    Startup call helper for pygame bot
    """
    if common.pgbot_initialized:
        return

    try:
        await _init()
    except Exception:
        # error happened in the first init sequence. report error to stdout/stderr
        # note that the chances of this happening are pretty slim, but you never know
        sys.stdout = common.old_stdout
        sys.stderr = common.old_stderr
        raise

    routine.handle_console.start()
    routine.routine.start()

    if common.guild is None:
        raise RuntimeWarning(
            "Primary guild was not set. Some features of bot would not run as usual."
            " People running commands via DMs might face some problems"
        )

    setup_logging()
    common.pgbot_initialized = True


def format_entries_message(
    msg: discord.Message, entry_type: str
) -> tuple[str, list[dict[str, Union[str, bool]]]]:
    """
    Formats an entries message to be reposted in discussion channel
    """
    if entry_type != "":
        title = f"New {entry_type.lower()} in #\u200b{common.entry_channels[entry_type].name}"
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


URL_PATTERN = re.compile(
    r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])"
)
# https://stackoverflow.com/a/6041965/14826938


def entry_message_validity_check(
    message: discord.Message, min_chars=32, max_chars=float("inf")
):
    """Checks if a message posted in a showcase channel for projects has the right format.

    Returns:
        bool: True/False
    """
    search_obj = URL_PATTERN.search((message.content if message.content else ""))
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

    else:
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

    # This function is called right when a member joins, even before the member
    # finishes the join screening. So we wait for that to happen and then send
    # the message. Wait for a maximum of six hours.
    for _ in range(1080):
        await asyncio.sleep(20)

        if not member.pending:
            # Don't use embed here, because pings would not work
            if member.guild.id == common.GuildConstants.GUILD_ID:
                greet = random.choice(common.GuildConstants.BOT_WELCOME_MSG["greet"])
                check = random.choice(common.GuildConstants.BOT_WELCOME_MSG["check"])
                grab = random.choice(common.GuildConstants.BOT_WELCOME_MSG["grab"])
                end = random.choice(common.GuildConstants.BOT_WELCOME_MSG["end"])
                await common.arrivals_channel.send(
                    f"{greet} {member.mention}! {check} "
                    + f"{common.guide_channel.mention}{grab} "
                    + f"{common.roles_channel.mention}{end}"
                )
            return


async def clean_storage_member(member: discord.Member):
    """
    This function silently removes users from storage messages
    """
    for table_name in ("stream", "reminders", "clock"):
        async with snakecore.storage.DiscordStorage(table_name) as storage_obj:
            data = storage_obj.obj
            if member.id in data:
                data.pop(member)
                storage_obj.obj = data


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
            msg.channel.id == common.GuildConstants.ENTRY_CHANNEL_IDS["showcase"]
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
    bot_id = common.bot.user.id
    if new.content.startswith((common.COMMAND_PREFIX, f"<@{bot_id}>", f"<@!{bot_id}>")):
        try:
            if new.id in common.cmd_logs.keys():
                await handle_command(new, common.cmd_logs[new.id])
        except discord.HTTPException:
            pass

    if common.GENERIC or common.TEST_MODE:
        return

    if new.channel.id == common.GuildConstants.ENTRY_CHANNEL_IDS["showcase"]:
        embed_repost_edited = False
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
                        deletion_datetime = datetime.datetime.now(
                            datetime.timezone.utc
                        ) + datetime.timedelta(minutes=2)
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
                                delete_bad_entry_and_warning(new, warn_msg, delay=120)
                            ),
                            warn_msg.id,
                        ]
                    except discord.NotFound:  # cancelling didn't work, warning and entry message were already deleted
                        del common.entry_message_deletion_dict[new.id]

            else:  # an edit led to an invalid entry message from a valid one
                deletion_datetime = datetime.datetime.now(
                    datetime.timezone.utc
                ) + datetime.timedelta(minutes=2)
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
                    warn_msg = await new.channel.fetch_message(deletion_data_list[1])
                    await warn_msg.delete()
                except discord.NotFound:  # cancelling didn't work, warning and entry message were already deleted
                    pass
            del common.entry_message_deletion_dict[new.id]

        async for message in common.entries_discussion_channel.history(  # attempt to find and edit repost
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
            if (
                datetime.datetime.now(datetime.timezone.utc) - old.created_at
            ) < datetime.timedelta(
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


async def validate_help_forum_channel_thread_name(thread: discord.Thread):
    caution_message = None
    for caution_type in (
        guild_constants := common.GuildConstants
    ).INVALID_HELP_THREAD_TITLE_TYPES:
        if (
            guild_constants.INVALID_HELP_THREAD_TITLE_SCANNING_ENABLED[caution_type]
            and guild_constants.INVALID_HELP_THREAD_TITLE_REGEX_PATTERNS[
                caution_type
            ].search(thread.name)
            is not None
        ):
            caution_message = await thread.send(
                content=f"<@{thread.owner_id}>",
                embed=discord.Embed.from_dict(
                    guild_constants.INVALID_HELP_THREAD_TITLE_EMBEDS[caution_type]
                ),
            )

    if caution_message is not None:
        common.hold_task(
            asyncio.create_task(
                message_delete_reaction_listener(
                    caution_message,
                    (
                        thread.owner
                        or common.bot.get_user(thread.owner_id)
                        or (await common.bot.fetch_user(thread.owner_id))
                    ),
                    emoji="🗑",
                    role_whitelist=common.GuildConstants.ADMIN_ROLES,
                    timeout=120,
                )
            )
        )


async def thread_create(thread: discord.Thread):
    if (
        thread.guild.id == common.GuildConstants.GUILD_ID
        and thread.parent_id in common.GuildConstants.HELP_FORUM_CHANNEL_IDS
    ):
        try:
            await (
                thread.starter_message or (await thread.fetch_message(thread.id))
            ).pin()
            await validate_help_forum_channel_thread_name(thread)
        except discord.HTTPException:
            pass


async def thread_update(before: discord.Thread, after: discord.Thread):
    if after.parent_id in common.GuildConstants.HELP_FORUM_CHANNEL_IDS:
        try:
            if not (after.archived or after.locked) and before.name != after.name:
                await validate_help_forum_channel_thread_name(after)
        except discord.HTTPException:
            pass


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

    if (
        msg.author.id == common.bot.user.id
        and msg.embeds
        and (footer_text := msg.embeds[0].footer.text)
    ):
        split_footer = footer_text.split("___\n")  # separator used by poll embeds

        if len(split_footer) == 1:
            return

        try:
            poll_config_map = parse_text_to_mapping(
                split_footer[1], delimiter=":", separator=" | "
            )
        except (SyntaxError, ValueError):
            raise

        if "by" in poll_config_map and "voting-mode" in poll_config_map:
            for reaction in msg.reactions:
                async for user in reaction.users():
                    if (
                        user.id == payload.user_id
                        and not snakecore.utils.is_emoji_equal(
                            payload.emoji, reaction.emoji
                        )
                    ):
                        await reaction.remove(user)


async def handle_message(msg: discord.Message):
    """
    Handle a message posted by user
    """
    if msg.type == discord.MessageType.premium_guild_subscription:
        if not common.TEST_MODE:
            await msg.channel.send(
                "A LOT OF THANKSSS! :heart: <:pg_party:772652894574084098>"
            )

    mentions = f"<@!{common.bot.user.id}>", f"<@{common.bot.user.id}>"

    if msg.content.startswith(common.COMMAND_PREFIX) or (
        msg.content.startswith(mentions) and msg.content not in mentions
    ):  # ignore normal pings
        if msg.content == common.COMMAND_PREFIX:
            await msg.channel.send(
                embed=discord.Embed(
                    title="Help",
                    description=f"Type `{common.COMMAND_PREFIX}help` to see what I'm capable of!",
                    color=common.DEFAULT_EMBED_COLOR,
                )
            )
            return
        else:
            ret = await handle_command(msg)
        if ret is not None:
            common.cmd_logs[msg.id] = ret

        if len(common.cmd_logs) > 100:
            del common.cmd_logs[next(iter(common.cmd_logs.keys()))]

    elif not common.TEST_MODE:

        if common.GENERIC:
            return

        if msg.channel in common.entry_channels.values():
            if msg.channel.id == common.GuildConstants.ENTRY_CHANNEL_IDS["showcase"]:
                if not entry_message_validity_check(msg):
                    deletion_datetime = datetime.datetime.now(
                        datetime.timezone.utc
                    ) + datetime.timedelta(minutes=2)
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
                title, fields = format_entries_message(msg, entry_type)
                await snakecore.utils.embed_utils.send_embed(
                    common.entries_discussion_channel,
                    title=title,
                    color=color,
                    fields=fields,
                )


async def handle_command(
    invoke_message: discord.Message, response_message: Optional[discord.Message] = None
):
    """
    Handle a command invocation
    """
    is_admin, _ = get_primary_guild_perms(invoke_message.author)
    bot_id = common.bot.user.id

    is_mention_invocation = invoke_message.content.startswith(
        (f"<@!{common.bot.user.id}>", f"<@{common.bot.user.id}>")
    )
    if is_admin and invoke_message.content.startswith(
        (
            f"{common.COMMAND_PREFIX}stop",
            f"<@{bot_id}> stop",
            f"<@{bot_id}>stop",
            f"<@!{bot_id}> stop",
            f"<@!{bot_id}>stop",
        )
    ):
        splits = invoke_message.content.strip().split(" ")
        splits.pop(0)
        try:
            if splits:
                for uid in map(
                    lambda arg: snakecore.utils.extract_markdown_mention_id(arg)
                    if snakecore.utils.is_markdown_mention(arg)
                    else arg,
                    splits,
                ):
                    if uid in common.TEST_USER_IDS:
                        break
                else:
                    return

        except ValueError:
            if response_message is None:
                await snakecore.utils.embed_utils.send_embed(
                    invoke_message.channel,
                    title="Invalid arguments!",
                    description="All arguments must be integer IDs or member mentions",
                    color=0xFF0000,
                )
            else:
                await snakecore.utils.embed_utils.replace_embed_at(
                    response_message,
                    title="Invalid arguments!",
                    description="All arguments must be integer IDs or member mentions",
                    color=0xFF0000,
                )
            return

        if response_message is None:
            await snakecore.utils.embed_utils.send_embed(
                invoke_message.channel,
                title="Stopping bot...",
                description="Change da world,\nMy final message,\nGoodbye.",
                color=common.DEFAULT_EMBED_COLOR,
            )
        else:
            await snakecore.utils.embed_utils.replace_embed_at(
                response_message,
                title="Stopping bot...",
                description="Change da world,\nMy final message,\nGoodbye.",
                color=common.DEFAULT_EMBED_COLOR,
            )
        sys.exit(0)

    if (
        common.TEST_MODE
        and common.TEST_USER_IDS
        and invoke_message.author.id not in common.TEST_USER_IDS
    ):
        return

    ctx = await common.bot.get_context(invoke_message)

    if (is_mention_invocation and not ctx.command) or not (
        is_mention_invocation or (ctx.command or ctx.invoked_with)
    ):
        # skip unintended or malformed command invocations
        return

    if response_message is None:
        response_message = await snakecore.utils.embed_utils.send_embed(
            invoke_message.channel,
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u200b", value="`Loading...`", inline=False)],
        )

    common.recent_response_messages[invoke_message.id] = response_message

    if not common.TEST_MODE and not common.GENERIC:
        log_txt_file = None
        escaped_cmd_text = discord.utils.escape_markdown(invoke_message.content)
        if len(escaped_cmd_text) > 2047:
            with io.StringIO(invoke_message.content) as log_buffer:
                log_txt_file = discord.File(log_buffer, filename="command.txt")

        await common.log_channel.send(
            embed=snakecore.utils.embed_utils.create_embed(
                title=f"Command invoked by {invoke_message.author} / {invoke_message.author.id}",
                description=escaped_cmd_text
                if len(escaped_cmd_text) <= 2047
                else escaped_cmd_text[:2044] + "...",
                color=common.DEFAULT_EMBED_COLOR,
                fields=[
                    dict(
                        name="\u200b",
                        value=f"by {invoke_message.author.mention}\n**[View Original]({invoke_message.jump_url})**",
                        inline=False,
                    ),
                ],
            ),
            file=log_txt_file,
        )

    common.hold_task(
        asyncio.create_task(
            message_delete_reaction_listener(
                response_message,
                invoke_message.author,
                emoji="🗑",
                role_whitelist=common.GuildConstants.ADMIN_ROLES,
                timeout=30,
            )
        )
    )

    await common.bot.invoke(ctx)
    return response_message


def cleanup(*_):
    """
    Call cleanup functions
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(snakecore.storage.quit_discord_storage())
    loop.run_until_complete(common.bot.close())
    loop.close()


def run():
    """
    Does what discord.Client.run does, except, handles custom cleanup functions
    and pygame init
    """

    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()  # pylint: disable=no-member
    common.pygame_display = pygame.display.set_mode((1, 1))

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
