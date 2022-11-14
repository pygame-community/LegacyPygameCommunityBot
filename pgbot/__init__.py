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
import time
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

    if not common.TEST_MODE:
        routine.inactive_help_thread_alert.start()
        routine.force_help_thread_archive_after_timeout.start()
        routine.delete_help_threads_without_starter_message.start()

    if common.guild is None:
        raise RuntimeWarning(
            "Primary guild was not set. Some features of bot would not run as usual."
            " People running commands via DMs might face some problems"
        )

    setup_logging()
    common.pgbot_initialized = True
    await load_help_thread_data()


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

    if (
        isinstance(msg.channel, discord.Thread)
        and msg.channel.parent_id
        in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
        and msg.id == msg.channel.id  # OP deleted starter message
    ):
        member_msg_count = 0
        async for thread_message in msg.channel.history(
            limit=max(msg.channel.message_count, 60)
        ):
            if (
                not thread_message.author.bot
                and thread_message.type == discord.MessageType.default
            ):
                member_msg_count += 1
                if member_msg_count > 29:
                    break

        if member_msg_count < 30:
            await msg.channel.send(
                embed=discord.Embed(
                    title="Post scheduled for deletion",
                    description=(
                        "Someone deleted the starter message of this post.\n\n"
                        "Since it contains less than 30 messages sent by "
                        "server members, it will be deleted "
                        f"**<t:{int(time.time()+300)}:R>**."
                    ),
                    color=0x551111,
                )
            )
            await asyncio.sleep(300)
            await msg.channel.delete()


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
                    await snakecore.utils.embeds.edit_embed_at(message, fields=fields)
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
                await snakecore.utils.embeds.send_embed(
                    common.entries_discussion_channel,
                    title=title,
                    color=color,
                    fields=fields,
                )


def validate_help_forum_channel_thread_name(thread: discord.Thread) -> bool:
    return any(
        (
            common.GuildConstants.INVALID_HELP_THREAD_TITLE_SCANNING_ENABLED[
                caution_type
            ]
            and common.GuildConstants.INVALID_HELP_THREAD_TITLE_REGEX_PATTERNS[
                caution_type
            ].search(thread.name.replace(f" | {thread.owner_id}", ""))
            is not None
            for caution_type in common.GuildConstants.INVALID_HELP_THREAD_TITLE_TYPES
        )
    )


def get_help_forum_channel_thread_name_cautions(
    thread: discord.Thread,
) -> tuple[str, ...]:
    return tuple(
        (
            caution_type
            for caution_type in common.GuildConstants.INVALID_HELP_THREAD_TITLE_TYPES
            if common.GuildConstants.INVALID_HELP_THREAD_TITLE_SCANNING_ENABLED[
                caution_type
            ]
            and common.GuildConstants.INVALID_HELP_THREAD_TITLE_REGEX_PATTERNS[
                caution_type
            ].search(
                " ".join(thread.name.replace(f" | {thread.owner_id}", "").split())
            )  # normalize whitespace
            is not None
        )
    )


async def caution_about_help_forum_channel_thread_name(
    thread: discord.Thread, *caution_types: str
) -> list[discord.Message]:
    caution_messages = []
    for caution_type in caution_types:
        caution_messages.append(
            await thread.send(
                content=f"help-post-alert(<@{thread.owner_id}>, **{thread.name}**)",
                embed=discord.Embed.from_dict(
                    common.GuildConstants.INVALID_HELP_THREAD_TITLE_EMBEDS[caution_type]
                ),
            )
        )

    return caution_messages


def validate_regulars_help_forum_channel_thread_tags(thread: discord.Thread) -> bool:
    applied_tags = thread.applied_tags
    valid = True
    if applied_tags and not any(
        tag.name.lower().startswith(("solved", "invalid")) for tag in applied_tags
    ):
        issue_tags = tuple(
            tag for tag in applied_tags if tag.name.lower().startswith("issue")
        )
        if not len(issue_tags) or len(issue_tags) > 1:
            valid = False

    return valid


async def caution_about_regulars_help_forum_channel_thread_tags(
    thread: discord.Thread,
) -> discord.Message:
    return await thread.send(
        content=f"help-post-alert(<@{thread.owner_id}>, **{thread.name}**)",
        embed=discord.Embed(
            title="Your tag selection is incomplete",
            description=(
                "Please pick exactly **1 issue tag** and **1-3 aspect tags**.\n\n"
                "**Issue Tags** look like this: **(`issue: ...`)**.\n"
                "**Aspect Tags** are all non-issue tags in lowercase, e.g. **(`💥 collisions`)**\n\n"
                "**Example tag combination for reworking collisions:\n"
                "(`🪛 issue: rework/optim.`) (`💥 collisions`)**.\n\n"
                f"See the Post Guidelines of <#{thread.parent_id}> for more details.\n\n"
                "To make changes to your post's tags, either right-click on "
                "it (desktop/web) or click and hold on it (mobile), then click "
                "on **'Edit Tags'** to see a tag selection menu. Remember to save "
                "your changes after selecting the correct tag(s).\n\n"
                "Thank you for helping us maintain clean help forum channels "
                "<:pg_robot:837389387024957440>\n\n"
                "This alert should disappear after you have made appropriate changes."
            ),
            color=0x36393F,
        ),
    )


async def thread_create(thread: discord.Thread):
    if (
        thread.guild.id == common.GuildConstants.GUILD_ID
        and thread.parent_id in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
    ):
        caution_messages: list[discord.Message] = []
        issues_found = False
        thread_edits = {}
        try:
            await (
                thread.starter_message
                if thread.starter_message and thread.starter_message.id == thread.id
                else (await thread.fetch_message(thread.id))
            ).pin()

            parent = (
                thread.parent
                or common.bot.get_channel(thread.parent_id)
                or await common.bot.fetch_channel(thread.parent_id)
            )

            if (
                len((applied_tags := thread.applied_tags))
                < common.FORUM_THREAD_TAG_LIMIT
                or len(applied_tags) == common.FORUM_THREAD_TAG_LIMIT
                and any(tag.name.lower().startswith("solved") for tag in applied_tags)
            ):
                new_tags = [
                    tag
                    for tag in applied_tags
                    if not tag.name.lower().startswith("solved")
                ]

                for tag in parent.available_tags:
                    if tag.name.lower().startswith("unsolved"):
                        new_tags.insert(0, tag)  # mark help post as unsolved
                        break

                thread_edits["applied_tags"] = new_tags

            if caution_types := get_help_forum_channel_thread_name_cautions(thread):
                issues_found = True
                caution_messages.extend(
                    await caution_about_help_forum_channel_thread_name(
                        thread, *caution_types
                    )
                )
                if "thread_title_too_short" in caution_types:
                    thread_edits.update(
                        dict(
                            slowmode_delay=common.THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY,
                            reason="Slowmode penalty for the title of this help post being too short.",
                            applied_tags=new_tags,
                        )
                    )
            if (
                thread.parent_id
                == common.GuildConstants.HELP_FORUM_CHANNEL_IDS["regulars"]
            ):
                if not validate_regulars_help_forum_channel_thread_tags(thread):
                    issues_found = True
                    caution_messages.append(
                        await caution_about_regulars_help_forum_channel_thread_tags(
                            thread
                        )
                    )

            if issues_found and thread.id not in common.bad_help_thread_data:
                common.bad_help_thread_data[thread.id] = {
                    "thread_id": thread.id,
                    "last_cautioned_ts": time.time(),
                    "alert_message_ids": set(msg.id for msg in caution_messages),
                }

            owner_id_suffix = f" | {thread.owner_id}"
            if not (
                thread.name.endswith(owner_id_suffix)
                or str(thread.owner_id) in thread.name
            ):
                thread_edits["name"] = (
                    thread.name if len(thread.name) < 72 else thread.name[:72] + "..."
                ) + owner_id_suffix

            if thread_edits:
                await thread.edit(**thread_edits)

        except discord.HTTPException:
            pass


async def send_help_thread_solved_alert(thread: discord.Thread):
    await thread.send(
        content="help-post-solved",
        embed=discord.Embed(
            title="Post marked as solved",
            description=(
                "This help post has been marked as solved.\n"
                "It will now close with a 1 minute slowmode "
                "after 1 hour of inactivity.\nFor the sake of the "
                "OP, please avoid sending any further messages "
                "that aren't essential additions to the currently "
                "accepted answers.\n\n"
                "**Mark all messages you find helpful here with a ✅ reaction "
                "please** <:pg_robot:837389387024957440>\n\n"
                "The slowmode and archive timeout will both be reverted "
                "if this post is unmarked as solved."
            ),
            color=0x00AA00,
        ),
    )


async def thread_update(before: discord.Thread, after: discord.Thread):
    if after.parent_id in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values():
        try:
            if not (after.archived or after.locked):
                thread_edits = {}
                caution_messages: list[discord.Message] = []
                bad_thread_name = False
                bad_thread_tags = False
                owner_id_suffix = f" | {after.owner_id}"
                owner_id_suffix_added = not before.name.endswith(
                    owner_id_suffix
                ) and after.name.endswith(owner_id_suffix)

                if before.name != after.name:
                    if caution_types := get_help_forum_channel_thread_name_cautions(
                        after
                    ):
                        bad_thread_name = True
                        if not owner_id_suffix_added:
                            caution_messages.extend(
                                await caution_about_help_forum_channel_thread_name(
                                    after, *caution_types
                                )
                            )
                            if (
                                "thread_title_too_short" in caution_types
                                and after.slowmode_delay
                                < common.THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY
                            ):
                                thread_edits.update(
                                    dict(
                                        slowmode_delay=common.THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY,
                                        reason="Slowmode penalty for the title of this "
                                        "help post being too short.",
                                    )
                                )
                            elif (
                                after.slowmode_delay
                                == common.THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY
                            ):
                                thread_edits.update(
                                    dict(
                                        slowmode_delay=(
                                            after.parent
                                            or common.bot.get_channel(after.parent_id)
                                            or await common.bot.fetch_channel(
                                                after.parent_id
                                            )
                                        ).default_thread_slowmode_delay,
                                        reason="This help post's title is not too short anymore.",
                                    )
                                )

                elif before.applied_tags != after.applied_tags:
                    if (
                        after.parent_id
                        == common.GuildConstants.HELP_FORUM_CHANNEL_IDS["regulars"]
                    ):
                        if not validate_regulars_help_forum_channel_thread_tags(after):
                            bad_thread_tags = True
                            caution_messages.append(
                                await caution_about_regulars_help_forum_channel_thread_tags(
                                    after
                                )
                            )

                if bad_thread_name or bad_thread_tags:
                    if after.id not in common.bad_help_thread_data:
                        common.bad_help_thread_data[after.id] = {
                            "thread_id": after.id,
                            "last_cautioned_ts": time.time(),
                            "alert_message_ids": set(
                                msg.id for msg in caution_messages
                            ),
                        }
                    common.bad_help_thread_data[after.id][
                        "last_cautioned_ts"
                    ] = time.time()
                    common.bad_help_thread_data[after.id]["alert_message_ids"].update(
                        (msg.id for msg in caution_messages)
                    )
                else:
                    if after.id in common.bad_help_thread_data:
                        if (
                            after.slowmode_delay
                            == common.THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY
                        ):
                            thread_edits.update(
                                dict(
                                    slowmode_delay=(
                                        after.parent
                                        or common.bot.get_channel(after.parent_id)
                                        or await common.bot.fetch_channel(
                                            after.parent_id
                                        )
                                    ).default_thread_slowmode_delay,
                                    reason="This help post's title is not invalid anymore.",
                                )
                            )

                        for msg_id in tuple(
                            common.bad_help_thread_data[after.id]["alert_message_ids"]
                        ):
                            try:
                                await after.get_partial_message(msg_id).delete()
                            except discord.NotFound:
                                pass

                        if (
                            after.id in common.bad_help_thread_data
                        ):  # fix concurrency bugs where key was already deleted
                            del common.bad_help_thread_data[after.id]

                    solved_in_before = any(
                        tag.name.lower().startswith("solved")
                        for tag in before.applied_tags
                    )
                    solved_in_after = any(
                        tag.name.lower().startswith("solved")
                        for tag in after.applied_tags
                    )
                    if not solved_in_before and solved_in_after:
                        new_tags = [
                            tag
                            for tag in after.applied_tags
                            if not tag.name.lower().startswith("unsolved")
                        ]
                        await send_help_thread_solved_alert(after)
                        thread_edits.update(
                            dict(
                                auto_archive_duration=60,
                                reason="This help post was marked as solved.",
                                applied_tags=new_tags,
                            )
                        )

                        if after.id in common.inactive_help_thread_data:
                            try:
                                if alert_message_id := common.inactive_help_thread_data[
                                    after.id
                                ].get("alert_message_id", None):
                                    try:
                                        await after.get_partial_message(
                                            alert_message_id
                                        ).delete()
                                    except discord.NotFound:
                                        pass
                            finally:
                                del common.inactive_help_thread_data[after.id]

                    elif solved_in_before and not solved_in_after:
                        parent = (
                            after.parent
                            or common.bot.get_channel(after.parent_id)
                            or await common.bot.fetch_channel(after.parent_id)
                        )

                        new_tags = after.applied_tags
                        if len(new_tags) < common.FORUM_THREAD_TAG_LIMIT:
                            for tag in parent.available_tags:
                                if tag.name.lower().startswith("unsolved"):
                                    new_tags.insert(
                                        0, tag
                                    )  # mark help post as unsolved
                                    break

                        slowmode_delay = discord.utils.MISSING
                        if after.slowmode_delay == 60:  # no custom slowmode override
                            slowmode_delay = parent.default_thread_slowmode_delay

                        thread_edits.update(
                            dict(
                                auto_archive_duration=parent.default_auto_archive_duration,
                                slowmode_delay=slowmode_delay,
                                reason="This help post was unmarked as solved.",
                                applied_tags=new_tags,
                            )
                        )

                if (
                    not (
                        after.name.endswith(owner_id_suffix)
                        or str(after.owner_id) in after.name
                    )
                    and not (await asyncio.sleep(2))
                    and not (
                        after.name.endswith(owner_id_suffix)
                        or str(after.owner_id) in after.name
                    )
                ):  # wait for a few event loop iterations, before doing a second,
                    # check, to be sure that a bot edit hasn't already occured
                    thread_edits["name"] = (
                        after.name if len(after.name) < 72 else after.name[:72] + "..."
                    ) + owner_id_suffix

                if thread_edits:
                    await after.edit(
                        **thread_edits
                    )  # apply edits in a batch to save API calls

            elif after.archived:
                if any(
                    tag.name.lower().startswith("solved") for tag in after.applied_tags
                ):
                    parent = (
                        after.parent
                        or common.bot.get_channel(after.parent_id)
                        or await common.bot.fetch_channel(after.parent_id)
                    )
                    if (
                        after.slowmode_delay == parent.default_thread_slowmode_delay
                    ):  # no custom slowmode override
                        await after.edit(archived=False, slowmode_delay=60)
                        await asyncio.sleep(5)
                        await after.edit(archived=True)

        except discord.HTTPException:
            pass


async def raw_thread_delete(payload: discord.RawThreadDeleteEvent):
    if payload.thread_id in common.inactive_help_thread_data:
        del common.inactive_help_thread_data[payload.thread_id]


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

    if not (
        (
            isinstance(channel, discord.abc.GuildChannel)
            and isinstance(channel, discord.abc.Messageable)
        )
        or isinstance(channel, discord.Thread)
    ):
        return

    try:
        user = common.bot.get_user(payload.user_id) or await common.bot.fetch_user(
            payload.user_id
        )
        msg: discord.Message = await channel.fetch_message(payload.message_id)
    except discord.HTTPException:
        return

    if user.bot:
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

        if (
            "by" in poll_config_map
            and "voting-mode" in poll_config_map
            and poll_config_map["voting-mode"] == "single"
        ):
            for reaction in msg.reactions:
                async for user in reaction.users():
                    if (
                        user.id == payload.user_id
                        and not snakecore.utils.is_emoji_equal(
                            payload.emoji, reaction.emoji
                        )
                    ):
                        await reaction.remove(user)
    try:
        if (
            isinstance(msg.channel, discord.Thread)
            and msg.channel.parent_id
            in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
            and not msg.channel.flags.pinned
        ):
            if not snakecore.utils.is_emoji_equal(payload.emoji, "✅"):
                return

            white_check_mark_reaction = discord.utils.find(
                lambda r: snakecore.utils.is_emoji_equal(r.emoji, "✅"),
                msg.reactions,
            )

            if not msg.pinned and (
                payload.user_id == msg.channel.owner_id
                or payload.member is not None
                and (
                    (await common.bot.is_owner(payload.member))
                    or any(
                        role.id in common.GuildConstants.ADMIN_ROLES
                        for role in payload.member.roles
                    )
                )
            ):
                await msg.pin(
                    reason="The owner of this message's thread has marked it as helpful."
                )
            elif payload.user_id == msg.author.id and msg.id != msg.channel.id:
                await msg.remove_reaction("✅", msg.author)

            elif not msg.pinned and (
                white_check_mark_reaction and white_check_mark_reaction.count >= 4
            ):
                await msg.pin(
                    reason="Multiple members of this message's thread "
                    "have marked it as helpful."
                )

            if (
                msg.id == msg.channel.id
                and (
                    (by_op := payload.user_id == msg.channel.owner_id)
                    or payload.member is not None
                    and (
                        (await common.bot.is_owner(payload.member))
                        or any(
                            role.id in common.GuildConstants.ADMIN_ROLES
                            for role in payload.member.roles
                        )
                    )
                )
                and msg.channel.applied_tags
                and not any(
                    tag.name.lower() in ("solved", "invalid")
                    for tag in msg.channel.applied_tags
                )
            ) and len(
                msg.channel.applied_tags
            ) < common.FORUM_THREAD_TAG_LIMIT:  # help post should be marked as solved
                for tag in (
                    msg.channel.parent
                    or common.bot.get_channel(msg.channel.parent_id)
                    or await common.bot.fetch_channel(msg.channel.parent_id)
                ).available_tags:
                    if tag.name.lower().startswith("solved"):
                        new_tags = [
                            tg
                            for tg in msg.channel.applied_tags
                            if tg.name.lower() != "unsolved"
                        ]
                        new_tags.append(tag)

                        await msg.channel.edit(
                            reason="This help post was marked as solved by "
                            + ("the OP" if by_op else "an admin")
                            + " (via a ✅ reaction).",
                            applied_tags=new_tags,
                        )
                        break

    except discord.HTTPException:
        pass


async def raw_reaction_remove(payload: discord.RawReactionActionEvent):
    channel = common.bot.get_channel(payload.channel_id)
    if channel is not None:
        try:
            channel = await common.bot.fetch_channel(payload.channel_id)
        except discord.HTTPException:
            return

    if (
        not isinstance(channel, discord.Thread)
        or isinstance(channel, discord.Thread)
        and (
            channel.parent_id
            not in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
            or channel.flags.pinned
        )
    ):
        return

    try:
        msg = await channel.fetch_message(payload.message_id)
        if (
            isinstance(msg.channel, discord.Thread)
            and msg.channel.parent_id
            in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
        ):
            if not snakecore.utils.is_emoji_equal(payload.emoji, "✅"):
                return

            white_check_mark_reaction = discord.utils.find(
                lambda r: snakecore.utils.is_emoji_equal(r.emoji, "✅"),
                msg.reactions,
            )

            if msg.pinned and (
                (
                    not white_check_mark_reaction
                    or white_check_mark_reaction
                    and white_check_mark_reaction.count < 4
                )
                or (
                    payload.member is not None
                    and (
                        (await common.bot.is_owner(payload.member))
                        or any(
                            role.id in common.GuildConstants.ADMIN_ROLES
                            for role in payload.member.roles
                        )
                    )
                )
            ):
                await msg.unpin(
                    reason="Multiple members of this message's thread "
                    "have unmarked it as helpful."
                )

            if (
                msg.id == msg.channel.id
                and (
                    (by_op := payload.user_id == msg.channel.owner_id)
                    or (
                        payload.member is not None
                        and (
                            (await common.bot.is_owner(payload.member))
                            or any(
                                role.id in common.GuildConstants.ADMIN_ROLES
                                for role in payload.member.roles
                            )
                        )
                    )
                )
                and msg.channel.applied_tags
                and any(
                    tag.name.lower().startswith("solved")
                    for tag in msg.channel.applied_tags
                )
            ):  # help post should be unmarked as solved
                for tag in (
                    msg.channel.parent
                    or common.bot.get_channel(msg.channel.parent_id)
                    or await common.bot.fetch_channel(msg.channel.parent_id)
                ).available_tags:
                    if tag.name.lower().startswith("solved"):
                        await msg.channel.remove_tags(
                            tag,
                            reason="This help post was unmarked as solved by "
                            + ("the OP" if by_op else "an admin")
                            + " (via removing a ✅ reaction).",
                        )
                        break
    except discord.HTTPException:
        pass


async def handle_message(msg: discord.Message):
    """
    Handle a message posted by user
    """
    if msg.author.bot:
        return

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
                await snakecore.utils.embeds.send_embed(
                    common.entries_discussion_channel,
                    title=title,
                    color=color,
                    fields=fields,
                )

    if msg.channel.id in common.UPVOTE_THREADS:
        try:
            await msg.add_reaction(common.UPVOTE_THREADS[msg.channel.id])
        except discord.HTTPException:
            pass


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
                await snakecore.utils.embeds.send_embed(
                    invoke_message.channel,
                    title="Invalid arguments!",
                    description="All arguments must be integer IDs or member mentions",
                    color=0xFF0000,
                )
            else:
                await snakecore.utils.embeds.replace_embed_at(
                    response_message,
                    title="Invalid arguments!",
                    description="All arguments must be integer IDs or member mentions",
                    color=0xFF0000,
                )
            return

        if response_message is None:
            await snakecore.utils.embeds.send_embed(
                invoke_message.channel,
                title="Stopping bot...",
                description="Change da world,\nMy final message,\nGoodbye.",
                color=common.DEFAULT_EMBED_COLOR,
            )
        else:
            await snakecore.utils.embeds.replace_embed_at(
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
        response_message = await snakecore.utils.embeds.send_embed(
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
            embed=snakecore.utils.embeds.create_embed(
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
                common.bot,
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


async def load_help_thread_data():
    async with snakecore.storage.DiscordStorage(
        "inactive_help_thread_data", dict
    ) as storage_obj:
        common.inactive_help_thread_data = storage_obj.obj

    async with snakecore.storage.DiscordStorage(
        "bad_help_thread_data", dict
    ) as storage_obj:
        bad_help_thread_data = storage_obj.obj
        for thread_id, thread_data in bad_help_thread_data.items():
            common.bad_help_thread_data[thread_id] = thread_data


async def dump_help_thread_data():
    async with snakecore.storage.DiscordStorage(
        "inactive_help_thread_data", dict
    ) as storage_obj:
        storage_obj.obj = common.inactive_help_thread_data

    async with snakecore.storage.DiscordStorage(
        "bad_help_thread_data", dict
    ) as storage_obj:
        storage_obj.obj = common.bad_help_thread_data


def cleanup(*_):
    """
    Call cleanup functions
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(dump_help_thread_data())
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
