"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines some important utility functions.
"""

from __future__ import annotations
from ast import literal_eval
import asyncio
import datetime
import io
import time
from typing import Any, Callable, Coroutine, Optional, Sequence, Union


import discord
from discord.ext import commands
import pygame
import snakecore

from pgbot import common


def get_primary_guild_perms(mem: Union[discord.Member, discord.User]):
    """
    Return a tuple (is_admin, is_priv) for a given user
    """
    if mem.id in common.TEST_USER_IDS:
        return True, True

    if not isinstance(mem, discord.Member):
        return False, False

    is_priv = False

    if not common.GENERIC:
        for role in mem.roles:
            if role.id in common.GuildConstants.ADMIN_ROLES:
                return True, True
            elif role.id in common.GuildConstants.PRIV_ROLES:
                is_priv = True

    return False, is_priv


async def get_channel_feature(
    name: str, channel: common.Channel, defaultret: bool = False
):
    """
    Get the channel feature. Returns True if the feature name is disabled on
    that channel, False otherwise. Also handles category channel
    """
    async with snakecore.storage.DiscordStorage("feature") as storage_obj:
        storage_dict: dict[int, bool] = storage_obj.obj

    if channel.id in storage_dict:
        return storage_dict[channel.id]

    if isinstance(channel, discord.TextChannel):
        if channel.category_id is None:
            return defaultret
        return storage_dict.get(channel.category_id, defaultret)

    return defaultret


def color_to_rgb_int(col: pygame.Color, alpha: bool = False):
    """
    Get integer RGB representation of pygame color object.
    """
    return (
        col.r << 32 | col.g << 16 | col.b << 8 | col.a
        if alpha
        else col.r << 16 | col.g << 8 | col.b
    )


def parse_text_to_mapping(
    string: str, delimiter: str = ":", separator: str = " | ", eval_values: bool = False
) -> dict[str, Any]:
    mapping = {}
    pair_strings = string.split(sep=separator)

    for pair_str in pair_strings:
        key, _, value = pair_str.strip().partition(delimiter)

        if not value:
            raise ValueError(f"failed to parse mapping pair: '{pair_str}'")

        if eval_values:
            mapping[key] = literal_eval(value)
        else:
            mapping[key] = value

    return mapping


async def fetch_last_thread_activity_dt(thread: discord.Thread) -> datetime.datetime:
    """Get the last time this thread was active. This is usually
    the creation date of the most recent message.

    Args:
        thread (discord.Thread): The thread.

    Returns:
        datetime.datetime: The time.
    """
    last_active = thread.created_at
    last_message = thread.last_message
    if last_message is None:
        last_message_found = False
        if thread.last_message_id is not None:
            try:
                last_message = await thread.fetch_message(thread.last_message_id)
                last_message_found = True
            except discord.NotFound:
                pass

        if not last_message_found:
            try:
                last_messages = [msg async for msg in thread.history(limit=1)]
                if last_messages:
                    last_message = last_messages[0]
            except discord.HTTPException:
                pass

    if last_message is not None:
        last_active = last_message.created_at

    return last_active


async def fetch_last_thread_message(
    thread: discord.Thread,
) -> Optional[discord.Message]:
    """Get the last message sent in the given thread.

    Args:
        thread (discord.Thread): The thread.

    Returns:
        Optional[discord.Message]: The message, if it exists.
    """
    last_message = thread.last_message
    if last_message is None:
        last_message_found = False
        if thread.last_message_id is not None:
            try:
                last_message = await thread.fetch_message(thread.last_message_id)
                last_message_found = True
            except discord.NotFound:
                pass

        if not last_message_found:
            try:
                last_messages = [msg async for msg in thread.history(limit=1)]
                if last_messages:
                    last_message = last_messages[0]
            except discord.HTTPException:
                pass

    return last_message


async def help_thread_deletion_checks(thread: discord.Thread):
    member_msg_count = 0
    try:
        async for thread_message in thread.history(limit=max(thread.message_count, 60)):
            if (
                not thread_message.author.bot
                and thread_message.type == discord.MessageType.default
            ):
                member_msg_count += 1
                if member_msg_count > 29:
                    break

        if member_msg_count < 30:
            await thread.send(
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
            await thread.delete()
    except discord.HTTPException:
        pass


def split_wc_scores(scores: dict[int, int]):
    """
    Split wc scoreboard into different categories
    """
    scores_list = [(score, f"<@!{mem}>") for mem, score in scores.items()]
    scores_list.sort(reverse=True)

    for title, category_score in common.GuildConstants.WC_SCORING:
        category_list = list(filter(lambda x: x[0] >= category_score, scores_list))
        if not category_list:
            continue

        desc = ">>> " + "\n".join(
            (f"`{score}` **•** {mem} :medal:" for score, mem in category_list)
        )

        yield dict(name=title, value=desc, inline=False)
        scores_list = scores_list[len(category_list) :]


async def give_wc_roles(member: discord.Member, score: int):
    """
    Updates the WC roles of a member based on their latest total score
    """
    got_role: bool = False
    for min_score, role_id in common.GuildConstants.WC_ROLES:
        if score >= min_score and not got_role:
            # This is the role to give
            got_role = True
            if role_id not in map(lambda x: x.id, member.roles):
                await member.add_roles(
                    discord.Object(role_id),
                    reason="Automatic bot action, adds WC event roles",
                )

        else:
            # any other event related role to be removed
            if role_id in map(lambda x: x.id, member.roles):
                await member.remove_roles(
                    discord.Object(role_id),
                    reason="Automatic bot action, removes older WC event roles",
                )


async def message_delete_reaction_listener(
    client: Union[discord.Client, discord.AutoShardedClient],
    msg: discord.Message,
    invoker: Union[discord.Member, discord.User],
    emoji: Union[discord.Emoji, discord.PartialEmoji, str],
    role_whitelist: Optional[Sequence[Union[discord.Role, int]]] = None,
    timeout: Optional[float] = None,
    on_delete: Union[
        Callable[[discord.Message], Coroutine[Any, Any, Any]],
        Callable[[discord.Message], Any],
        None,
    ] = None,
):
    """Allows for a message to be deleted using a specific reaction.
    If any HTTP-related exceptions are raised by `discord.py` within this function,
    it will fail silently.

    Args:
        msg (discord.Message): The message to use.
        invoker (Union[discord.Member, discord.User]): The member/user who can delete
          a message.
        emoji (Union[discord.Emoji, discord.PartialEmoji, str]): The emoji to
          listen for.
        role_whitelist (Sequence[int], optional): A sequence (that supports `__contains__`) of
          role IDs whose reactions can also be picked up by this function.
        timeout (Optional[float], optional): A timeout for waiting, before automatically
          removing any added reactions and returning silently.
        on_delete (Union[Callable[[discord.Message], Coroutine[Any, Any, Any]], Callable[[discord.Message], Any], None], optional):
          A (coroutine) function to call when a message is successfully deleted via the
          reaction. Defaults to None.

    Raises:
        TypeError: Invalid argument types.
    """

    role_whitelist_set = set(
        r.id if isinstance(r, discord.Role) else r for r in (role_whitelist or ())
    )

    if not isinstance(emoji, (discord.Emoji, discord.PartialEmoji, str)):
        raise TypeError("invalid emoji given as input.")

    try:
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            return

        check = None
        if isinstance(client, commands.Bot):
            await client.is_owner(invoker)  # fetch and cache bot owners implicitly
            # fmt: off
            valid_user_ids = set((
                (invoker.id, *(
                (client.owner_id,)
                if client.owner_id else
                tuple(client.owner_ids)
                if client.owner_ids
                else ()),)
            ))
            # fmt: on
        else:
            valid_user_ids = set((invoker.id,))

        if isinstance(invoker, discord.Member):
            check = (
                lambda event: event.message_id == msg.id
                and snakecore.utils.is_emoji_equal(event.emoji, emoji)
                and (
                    event.user_id in valid_user_ids
                    or any(
                        role.id in role_whitelist_set
                        for role in getattr(event.member, "roles", ())[1:]
                    )
                )
            )
        elif isinstance(invoker, discord.User):
            if isinstance(msg.channel, discord.DMChannel):
                check = (
                    lambda event: event.message_id == msg.id
                    and snakecore.utils.is_emoji_equal(event.emoji, emoji)
                )
            else:
                check = (
                    lambda event: event.message_id == msg.id
                    and snakecore.utils.is_emoji_equal(event.emoji, emoji)
                    and event.user_id in valid_user_ids
                )
        else:
            raise TypeError(
                "argument 'invoker' expected discord.Member/.User, "
                f"not {invoker.__class__.__name__}"
            )

        event: discord.RawReactionActionEvent = await client.wait_for(
            "raw_reaction_add", check=check, timeout=timeout
        )

        try:
            await msg.delete()
        except discord.HTTPException:
            pass
        else:
            if on_delete is not None:
                await discord.utils.maybe_coroutine(on_delete, msg)

    except (asyncio.TimeoutError, asyncio.CancelledError) as a:
        try:
            await msg.clear_reaction(emoji)
        except discord.HTTPException:
            pass

        if isinstance(a, asyncio.CancelledError):
            raise a


class RedirectTextIOWrapper(io.TextIOWrapper):
    def __init__(
        self,
        buffer: io.BufferedIOBase,
        streams: Sequence[io.TextIOBase],
        flush_streams: bool = True,
        close_streams: bool = False,
        **kwargs,
    ):
        """A subclass of `TextIOWrapper` that additionally redirects writes to the given TextIOBase streams.

        Args:
            buffer (BufferedIOBase): The buffer.
            streams (Sequence[TextIOBase]): The streams to redirect write operations to.
            flush_streams (bool, optional): Whether to flush the redirection streams when being flushed. Defaults to True.
            close_streams (bool, optional): Whether to close the redirection streams when being closed. Defaults to False.

        Raises:
            TypeError: Invalid redirect stream type.
        """
        super().__init__(buffer, **kwargs)
        if not all(
            (isinstance(stream, io.TextIOBase) and stream.writable())
            for stream in iter(streams)
        ):
            raise TypeError(
                "argument 'streams' must be a sequence of writable, flushable TextIOBase instances"
            )
        self._streams = tuple(streams)
        self._flush_streams = flush_streams
        self._close_streams = close_streams

    def _streams_get(self) -> tuple[io.TextIOBase]:
        return self._streams

    def _streams_set(self, streams: Sequence[io.TextIOBase]):
        if not all(
            (isinstance(stream, io.TextIOBase) and stream.writable())
            for stream in iter(streams)
        ):
            raise AttributeError(
                "attribute 'streams' must be a sequence of writable, flushable TextIOBase instances"
            )
        self._streams = tuple(streams)

    streams = property(fget=_streams_get, fset=_streams_set)

    def write(self, __s: str, /):
        super().write(__s)
        for stream in self._streams:
            stream.write(__s)

    def flush(self) -> None:
        super().flush()
        if self._flush_streams:
            for stream in self._streams:
                stream.flush()

    def close(self):
        super().close()
        if self._close_streams:
            for stream in self._streams:
                stream.close()
