"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the sudo commands of the bot
"""


from __future__ import annotations

import asyncio
import datetime
import io
import os
from typing import Optional, Union

import discord
import psutil

from pgbot import common
from pgbot.utils import embed_utils, utils
from pgbot.commands.base import BaseCommand, BotException, String, add_group

process = psutil.Process(os.getpid())


class SudoCommand(BaseCommand):
    """
    Base class for all sudo commands
    """

    @add_group("sudo")
    async def cmd_sudo(
        self,
        *datas: Union[discord.Message, String],
        destination: Optional[common.Channel] = None,
        from_attachment: bool = True,
        mention: bool = False,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo <*datas> [destination=] [from_attachment=True]
        ->description Send a message through the bot
        ->extended description
        Send a sequence of messages contain text from the given
        data using the specified arguments.

        __Args__:
            `*datas: (Message|String)`
            > A sequence of discord messages whose text
            > or text attachment should be used as input,
            > or strings.

            `destination (TextChannel) = `
            > A destination channel to send the output to.

            `from_attachment (bool) = True`
            > Whether the attachment of an input message should be
            > used to create a message.

            `mention (bool) = False`
            > Whether any mentions in the given input text
            > should ping their target. If set to `True`,
            > any role/user/member that the bot is allowed to ping will
            > be pinged.

        __Returns__:
            > One or more generated messages based on the given input.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!sudo "lol" "that" "was" "funny /s" destination=#general
        pg!sudo 987654321987654321 "Additionally, ..." 123456739242423 from_attachment=True
        -----
        Implement pg!sudo, for admins to send messages via the bot
        """

        if destination is None:
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author, destination, permissions=("view_channel", "send_messages")
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        for i, data in enumerate(datas):
            if isinstance(data, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    data.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )

            if not i % 50:
                await asyncio.sleep(0)

        output_strings = []
        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(
                ("\u2800", "`...`", False),
                ("\u2800", "`...`", False),
            ),
        )
        data_count = len(datas)
        for i, data in enumerate(datas):
            if data_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{data_count}` inputs processed\n"
                        f"{(i/data_count)*100:.01f}% | "
                        + utils.progress_bar(i / data_count, divisions=30),
                    ),
                    0,
                )
            attachment_msg = None

            if isinstance(data, String):
                if not data.string:
                    attachment_msg = self.invoke_msg
                else:
                    msg_text = data.string
                    output_strings.append(msg_text)

            elif isinstance(data, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    data.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                if from_attachment:
                    attachment_msg = data
                else:
                    src_msg_txt = data.content
                    if src_msg_txt:
                        output_strings.append(src_msg_txt)
                    else:
                        raise BotException(
                            f"Input {i}: No message text found!",
                            "The message given as input does not have any text content.",
                        )

            if attachment_msg:
                if not attachment_msg.attachments:
                    raise BotException(
                        f"Input {i}: No valid attachment found in message.",
                        "It must be a `.txt` file containing text data."
                        " If you want to retrieve the content of the"
                        " given message(s) instead, set the"
                        "` from_attachment=` argument to `False`",
                    )

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    raise BotException(
                        f"Input {i}: No valid attachment found in message.",
                        "It must be a `.txt` file containing text data.",
                    )

                msg_text = await attachment_obj.read()
                msg_text = msg_text.decode()

                if 0 < len(msg_text) <= 2000:
                    output_strings.append(msg_text)
                else:
                    raise BotException(
                        f"Input {i}: Too little/many characters!",
                        "a Discord message must contain at least one character and cannot contain more than 2000.",
                    )

            await asyncio.sleep(0)

        if not datas:
            data_count = 1
            attachment_msg = self.invoke_msg
            if not attachment_msg.attachments:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt` file containing text data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith("text")
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt` file containing text data.",
                )

            msg_text = await attachment_obj.read()
            msg_text = msg_text.decode()

            if 0 < len(msg_text) <= 2000:
                output_strings.append(msg_text)
            else:
                raise BotException(
                    "Too little/many characters!",
                    "a Discord message must contain at least one character and cannot contain more than 2000.",
                )

        if data_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Completed",
                    value=f"`{data_count}/{data_count}` inputs processed\n"
                    "100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        allowed_mentions = (
            discord.AllowedMentions.all() if mention else discord.AllowedMentions.none()
        )
        output_count = len(output_strings)
        for j, msg_txt in enumerate(output_strings):
            if output_count > 2 and not j % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Creating Messages",
                        value=f"`{j}/{output_count}` messages created\n"
                        f"{(j/output_count)*100:.01f}% | "
                        + utils.progress_bar(j / output_count, divisions=30),
                    ),
                    1,
                )
            await destination.send(content=msg_txt, allowed_mentions=allowed_mentions)

        if data_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Creation Completed",
                    value=f"`{output_count}/{output_count}` messages created\n"
                    "100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                1,
            )

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete(delay=10.0 if data_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("sudo", "edit")
    async def cmd_sudo_edit(
        self,
        msg: discord.Message,
        data: Union[discord.Message, String],
        from_attachment: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_edit <msg> <data> [from_attachment=True]
        ->description Replace a message that the bot sent
        ->extended description
        Replace the text content of a message using the given attributes.

        __Args__:
            `msg: (Message)`
            > A discord message whose text content
            > should be replaced.

            `data: (Message|String)`
            > The text data that should be used to replace
            > the input message text.

            `from_attachment (bool) = True`
            > Whether the attachment of the input message in `data`
            > should be used to edit the target message. If set to
            > `False`, the text content of the input message in
            > `data` will be used.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!sudo edit 9876543211234676789 "bruh"
        pg!sudo edit 1234567890876543345/9876543211234676789 2345678427483744843
        -----
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        elif isinstance(data, discord.Message) and not utils.check_channel_permissions(
            self.author,
            data.channel,
            permissions=("view_channel",),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        attachment_msg: Optional[discord.Message] = None
        msg_text = ""

        if isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                msg_text = data.string

        elif isinstance(data, discord.Message):
            if from_attachment:
                attachment_msg = data
            else:
                src_msg_txt = data.content
                if src_msg_txt:
                    msg_text = src_msg_txt
                else:
                    raise BotException(
                        "No message text found!",
                        "The message given as input does not have any text content.",
                    )

        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt` file containing text data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith("text")
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt` file containing text data.",
                )

            msg_text = await attachment_obj.read()
            msg_text = msg_text.decode()

            if not 0 < len(msg_text) <= 2000:
                raise BotException(
                    "Too little/many characters!",
                    "a Discord message must contain at least one character and cannot contain more than 2000.",
                )
        try:
            await msg.edit(content=msg_text)
        except discord.HTTPException as e:
            raise BotException(
                "An exception occured while handling the command!", e.args[0]
            )
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("sudo", "swap")
    async def cmd_sudo_swap(
        self,
        msg_a: discord.Message,
        msg_b: discord.Message,
        embeds: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo swap <message> <message>
        ->description Swap message contents and embeds between messages through the bot
        ->extended description
        Swap message contents and embeds between the two given messages.

        __Args__:
            `message_a: (Message)`
            > A discord message whose embed
            > should be swapped with that of `message_b`.

            `message_b: (Message)`
            > Another discord message whose embed
            > should be swapped with that of `message_a`.

            `embeds: (bool) = True`
            > If set to `True`, the first embeds will also
            > (when present) be swapped between the given messages.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command pg!sudo swap 123456789123456789 69696969969669420
        -----
        """

        if not utils.check_channel_permissions(
            self.author,
            msg_a.channel,
            permissions=("view_channel", "send_messages"),
        ) or not utils.check_channel_permissions(
            self.author,
            msg_b.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        if (
            not msg_a.content
            and not msg_a.embeds
            or not msg_b.content
            and not msg_b.embeds
        ):
            raise BotException(
                "Cannot execute command:",
                "Not enough data found in one or more of the given messages.",
            )

        elif common.bot.user.id not in (msg_a.author.id, msg_b.author.id):
            raise BotException(
                "Cannot execute command:",
                f"Both messages must have been authored by me, {common.bot.user.mention}.",
            )

        msg_embed_a = msg_a.embeds[0] if msg_a.embeds else None
        msg_embed_b = msg_b.embeds[0] if msg_b.embeds else None

        msg_content_a = msg_a.content
        msg_content_b = msg_b.content

        if embeds:
            await msg_a.edit(content=msg_content_b, embed=msg_embed_b)
            await msg_b.edit(content=msg_content_a, embed=msg_embed_a)
        else:
            await msg_a.edit(content=msg_content_b)
            await msg_b.edit(content=msg_content_a)

        try:
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("sudo", "get")
    async def cmd_sudo_get(
        self,
        *msgs: discord.Message,
        destination: Optional[common.Channel] = None,
        as_attachment: bool = False,
        attachments: bool = True,
        embeds: bool = True,
        info: bool = False,
        author_info: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_get <*messages> [destination=] [as_attachment=False] [attachments=True]
        [embeds=True] [info=False] [author_info=False]
        ->description Get the text of messages through the bot
        ->extended description
        Get the contents, attachments and serialized embeds of the given messages and send them to the given destination channel.

        __Args__:
            `*messages: (Message)`
            > A sequence of discord messages whose text,
            contents, attachments or embeds should be retrieved.

            `destination: (Channel) =`
            > A destination channel to send the generated outputs to.
            > If omitted, the destination will be the channel where
            > this command was invoked.

            `as_attachment: (bool) = False`
            > Whether the text content (if present) of the given
            > messages should be sent as an attachment (`.txt`)
            > or as embed containing it inside a code block in its
            > description. This will always occur if the text
            > content is above 2000 characters.

            `attachments: (bool) = True`
            > Whether the attachments of the given messages
            > should be retrieved (when possible).

            `embeds: (bool) = True`
            > Whether the embeds of the given messages
            > should be retrieved (as serialized JSON data).

        +===+

            `info: (bool) = False`
            > If set to `True`, an embed containing info
            > about each message will be sent along with
            > the message data output.

            `author_info: (bool) = True`
            > If set to `True`, extra information about
            > the message authors will be added to the
            > info embed which is sent if `info` is set
            > to `True`.

        __Returns__:
            > One or more messages with attachents or embeds
            > based on the given input.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """
        if not isinstance(destination, discord.TextChannel):
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author, destination, permissions=("view_channel", "send_messages")
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if msg.channel not in checked_channels:
                if not utils.check_channel_permissions(
                    self.author, msg.channel, permissions=("view_channel",)
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                else:
                    checked_channels.add(msg.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No messages given as input.",
            )

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )
            await destination.trigger_typing()

            escaped_msg_content = msg.content.replace("```", "\\`\\`\\`")
            attached_files = None
            if attachments:
                with io.StringIO("This file was too large to be duplicated.") as fobj:
                    attached_files = [
                        (
                            await a.to_file(spoiler=a.is_spoiler())
                            if a.size <= self.filesize_limit
                            else discord.File(fobj, f"filetoolarge - {a.filename}.txt")
                        )
                        for a in msg.attachments
                    ]

            if info:
                info_embed = embed_utils.get_msg_info_embed(msg, author_info)
                info_embed.set_author(name="Message data & info")
                info_embed.title = ""

                info_embed.description = "".join(
                    (
                        f"__Text"
                        + (" (Shortened)" if len(escaped_msg_content) > 2000 else "")
                        + "__:",
                        f"\n\n ```\n{escaped_msg_content[:2001]}\n\n[...]\n```"
                        + "\n\u2800"
                        if len(escaped_msg_content) > 2000
                        else "\n\u2800",
                    )
                )

                content_file = None
                if as_attachment or len(msg.content) > 2000:
                    with io.StringIO(msg.content) as fobj:
                        content_file = discord.File(fobj, "messagedata.txt")

                await destination.send(embed=info_embed, file=content_file)

            elif as_attachment:
                with io.StringIO(msg.content) as fobj:
                    await destination.send(
                        file=discord.File(fobj, "messagedata.txt"),
                        embed=embed_utils.create(
                            author_name="Message data",
                            description=f"**[View Original Message]({msg.jump_url})**",
                        ),
                    )
            else:
                if len(msg.content) > 2000 or len(escaped_msg_content) > 2000:
                    with io.StringIO(msg.content) as fobj:
                        await destination.send(
                            file=discord.File(fobj, "messagedata.txt"),
                            embed=embed_utils.create(
                                author_name="Message data",
                                description=f"**[View Original Message]({msg.jump_url})**",
                            ),
                        )
                else:
                    await embed_utils.send_2(
                        self.channel,
                        author_name="Message data",
                        description="```\n{0}```".format(escaped_msg_content),
                        fields=(
                            (
                                "\u2800",
                                f"**[View Original Message]({msg.jump_url})**",
                                False,
                            ),
                        ),
                    )

            if attached_files:
                for i in range(len(attached_files)):
                    await self.channel.send(
                        content=f"**Message attachment** ({i+1}):",
                        file=attached_files[i],
                    )

            if embeds and msg.embeds:
                embed_data_fobjs = []
                for embed in msg.embeds:
                    embed_data_fobj = io.StringIO()
                    embed_utils.export_embed_data(
                        embed.to_dict(),
                        fp=embed_data_fobj,
                        indent=4,
                        as_json=True,
                    )
                    embed_data_fobj.seek(0)
                    embed_data_fobjs.append(embed_data_fobj)

                for i in range(len(embed_data_fobjs)):
                    await self.channel.send(
                        content=f"**Message embed** ({i+1}):",
                        file=discord.File(
                            embed_data_fobjs[i], filename="embeddata.json"
                        ),
                    )

                for embed_data_fobj in embed_data_fobjs:
                    embed_data_fobj.close()

            await asyncio.sleep(0)

        if msg_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` messages processed\n"
                    "100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        try:
            await self.response_msg.delete(delay=10 if msg_count > 2 else 0)
        except discord.NotFound:
            pass

    @add_group("sudo", "fetch")
    async def cmd_sudo_fetch(
        self,
        origin: discord.TextChannel,
        quantity: int,
        channel_ids: bool = False,
        urls: bool = False,
        pinned: bool = False,
        pin_range: Optional[range] = None,
        before: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        after: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        around: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        oldest_first: bool = True,
        prefix: String = String(""),
        sep: String = String(" "),
        suffix: String = String(""),
    ):
        """
        ->type More admin commands
        ->signature pg!sudo fetch <origin channel> <quantity> [urls=False] [pinned=False] [pin_range=]
        [before=None] [after=None] [around=None] [oldest_first=True] [prefix=""] [sep=" "] [suffix=""]
        ->description Fetch message IDs or URLs
        -----
        """

        if not utils.check_channel_permissions(
            self.author,
            origin,
            permissions=("view_channel",),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        output_str = prefix.string
        destination = self.channel

        if pinned:
            messages = await origin.pins()
            if not messages:
                raise BotException(
                    "No pinned messages found",
                    "No pinned messages were found in the specified channel.",
                )

            if oldest_first:
                messages.reverse()

            if quantity > 0:
                messages = messages[: quantity + 1]
                if oldest_first:
                    messages.reverse()

            elif quantity == 0:
                if pin_range:
                    messages = messages[
                        pin_range.start : pin_range.stop : pin_range.step
                    ]

                    if pin_range.step != -1 and oldest_first:
                        messages.reverse()

            elif quantity < 0:
                raise BotException(
                    "Invalid `quantity` argument",
                    "Quantity has to be a positive integer (`=> 0`).",
                )

        else:
            if (
                isinstance(before, discord.PartialMessage)
                and before.channel.id != origin.id
            ):
                raise BotException(
                    "Invalid `before` argument",
                    "`before` has to be an ID to a message from the origin channel",
                )

            if (
                isinstance(after, discord.PartialMessage)
                and after.channel.id != origin.id
            ):
                raise BotException(
                    "Invalid `after` argument",
                    "`after` has to be an ID to a message from the origin channel",
                )

            if (
                isinstance(around, discord.PartialMessage)
                and around.channel.id != origin.id
            ):
                raise BotException(
                    "Invalid `around` argument",
                    "`around` has to be an ID to a message from the origin channel",
                )

            if quantity <= 0:
                if quantity == 0 and not after:
                    raise BotException(
                        "Invalid `quantity` argument",
                        "`quantity` must be above 0 when `after=` is not specified.",
                    )
                elif quantity != 0:
                    raise BotException(
                        "Invalid `quantity` argument",
                        "Quantity has to be a positive integer (or `0` when `after=` is specified).",
                    )

            await destination.trigger_typing()
            messages = await origin.history(
                limit=quantity if quantity != 0 else None,
                before=before,
                after=after,
                around=around,
            ).flatten()

            if not messages:
                raise BotException(
                    "Invalid message/time range",
                    "No messages were found for the specified input values.",
                )

            if not after and oldest_first:
                messages.reverse()

        msg_count = len(messages)
        msgs_per_loop = 200

        if urls:
            output_filename = "message_urls.txt"
            start_idx = 0
            end_idx = 0
            for i in range(msg_count // msgs_per_loop):
                start_idx = msgs_per_loop * i
                end_idx = start_idx + msgs_per_loop - 1
                output_str += sep.string.join(
                    messages[j].jump_url
                    for j in range(start_idx, start_idx + msgs_per_loop)
                )
                await asyncio.sleep(0)

            output_str += (
                "".join(messages[j].jump_url for j in range(end_idx + 1, msg_count))
                + suffix.string
            )

        elif channel_ids:
            output_filename = "message_and_channel_ids.txt"
            start_idx = 0
            end_idx = 0
            for i in range(msg_count // msgs_per_loop):
                start_idx = msgs_per_loop * i
                end_idx = start_idx + msgs_per_loop - 1
                output_str += sep.string.join(
                    f"{messages[j].channel.id}/{messages[j].id}"
                    for j in range(start_idx, start_idx + msgs_per_loop)
                )
                await asyncio.sleep(0)

            output_str += (
                sep.string.join(
                    f"{messages[j].channel.id}/{messages[j].id}"
                    for j in range(end_idx + 1, msg_count)
                )
                + suffix.string
            )

        else:
            output_filename = "message_and_channel_ids.txt"
            start_idx = 0
            end_idx = 0
            for i in range(msg_count // msgs_per_loop):
                start_idx = msgs_per_loop * i
                end_idx = start_idx + msgs_per_loop - 1
                output_str += sep.string.join(
                    f"{messages[j].id}"
                    for j in range(start_idx, start_idx + msgs_per_loop)
                )
                await asyncio.sleep(0)

            output_str += (
                sep.string.join(
                    f"{messages[j].id}" for j in range(end_idx + 1, msg_count)
                )
                + suffix.string
            )

        with io.StringIO(output_str) as fobj:
            await destination.send(file=discord.File(fobj, filename=output_filename))
        try:
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("sudo", "clone")
    async def cmd_sudo_clone(
        self,
        *msgs: discord.Message,
        destination: Optional[common.Channel] = None,
        embeds: bool = True,
        attachments: bool = True,
        as_spoiler: bool = False,
        info: bool = False,
        author_info: bool = True,
        skip_empty: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo clone <*messages> [destination=] [embeds=True] [attachments=True] [as_spoiler=False]
        [info=False] [author_info=True]
        ->description Clone a message through the bot
        ->extended description
        Clone the given messages and send them to the given destination channel.

        __Args__:
            `*messages: (Message)`
            > A sequence of discord messages whose text,
            contents, attachments or embeds should be cloned.

            `destination: (Channel) =`
            > A destination channel to send the cloned outputs to.
            > If omitted, the destination will be the channel where
            > this command was invoked.

            `as_attachment: (bool) = False`
            > Whether the text content (if present) of the given
            > messages should be sent as an attachment (`.txt`)
            > or as embed containing it inside a code block in its
            > description.

            `attachments: (bool) = True`
            > Whether the attachments of the given messages
            > should be cloned as well (if possible).

            `embeds: (bool) = True`
            > Whether the embeds of the given messages
            > should be cloned along with the outut messages.

        +===+

            `as_spoiler: (bool) = False`
            > If set to `True`, the attachments of the input messages
            > will be explicitly marked as spoilers when sent to the
            > destination channel.

            `info: (bool) = False`
            > If set to `True`, an embed containing info
            > about each message will be sent along with
            > the message data output.

            `author_info: (bool) = True`
            > If set to `True`, extra information about
            > the message authors will be added to the
            > info embed which is sent if `info` is set
            > to `True`.

            `skip_empty: (bool) = True`
            > Whether empty messages
            > should be skipped.

        __Returns__:
            > One or more cloned messages with attachents
            > or embeds based on the given input.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """

        if not isinstance(destination, discord.TextChannel):
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author, destination, permissions=("view_channel", "send_messages")
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if msg.channel not in checked_channels:
                if not utils.check_channel_permissions(
                    self.author, msg.channel, permissions=("view_channel",)
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                else:
                    checked_channels.add(msg.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No messages given as input.",
            )

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )

        msg_count = len(msgs)
        no_mentions = discord.AllowedMentions.none()
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )

            await destination.trigger_typing()
            cloned_msg0 = None
            attached_files = []
            if msg.attachments and attachments:
                with io.StringIO("This file was too large to be cloned.") as fobj:
                    attached_files = [
                        (
                            await a.to_file(spoiler=a.is_spoiler() or as_spoiler)
                            if a.size <= self.filesize_limit
                            else discord.File(fobj, f"filetoolarge - {a.filename}.txt")
                        )
                        for a in msg.attachments
                    ]

            if msg.content or msg.embeds or attached_files:
                if len(msg.content) > 2000:
                    start_idx = 0
                    stop_idx = 0
                    for i in range(len(msg.content) // 2000):
                        start_idx = 2000 * i
                        stop_idx = 2000 + 2000 * i

                        if not i:
                            cloned_msg0 = await destination.send(
                                content=msg.content[start_idx:stop_idx],
                                allowed_mentions=no_mentions,
                            )
                        else:
                            await destination.send(
                                content=msg.content[start_idx:stop_idx],
                                allowed_mentions=no_mentions,
                            )

                    with io.StringIO(msg.content) as fobj:
                        await destination.send(
                            content=msg.content[stop_idx:],
                            embed=embed_utils.create(footer_text="Full message data"),
                            file=discord.File(fobj, filename="messagedata.txt"),
                            allowed_mentions=no_mentions,
                        )

                    await destination.send(
                        embed=msg.embeds[0] if msg.embeds and embeds else None,
                        file=attached_files[0] if attached_files else None,
                    )
                else:
                    cloned_msg0 = await destination.send(
                        content=msg.content,
                        embed=msg.embeds[0] if msg.embeds and embeds else None,
                        file=attached_files[0] if attached_files else None,
                        allowed_mentions=no_mentions,
                    )
            elif not skip_empty:
                raise BotException("Cannot clone an empty message!", "")

            for i in range(1, len(attached_files)):
                await self.channel.send(
                    file=attached_files[i],
                )

            for i in range(1, len(msg.embeds)):
                await self.channel.send(
                    embed=msg.embeds[i],
                )

            if info:
                await self.channel.send(
                    embed=embed_utils.get_msg_info_embed(msg, author=author_info),
                    reference=cloned_msg0,
                )

            await asyncio.sleep(0)

        if msg_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` messages processed\n"
                    "100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        try:
            await self.response_msg.delete(delay=10 if msg_count > 2 else 0)
        except discord.NotFound:
            pass
