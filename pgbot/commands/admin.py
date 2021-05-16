from __future__ import annotations

import datetime
import os
import pprint
import time
import traceback
from typing import Optional, Union

import black
import discord
import psutil
import pygame

from discord.embeds import EmptyEmbed
from pgbot import common, db, embed_utils, utils
from pgbot.commands.base import BotException, CodeBlock, String
from pgbot.commands.emsudo import EmsudoCommand
from pgbot.commands.user import UserCommand

process = psutil.Process(os.getpid())


class AdminCommand(UserCommand, EmsudoCommand):
    """
    Base class for all admin commands
    """

    async def handle_cmd(self):
        """
        Temporary function, to divert paths for emsudo commands and other
        commands
        """
        if self.cmd_str.startswith("emsudo"):
            await EmsudoCommand.handle_cmd(self)
        else:
            await UserCommand.handle_cmd(self)

    async def cmd_see_db(self, name: str):
        """
        ->type Admin commands
        ->signature pg!see_db <name>
        ->description Visualize DB
        -----
        Implement pg!see_db, to visualise DB messages
        """
        await embed_utils.replace(
            self.response_msg,
            f"Here are the contents of the table {name}:",
            utils.code_block(pprint.pformat(await db.DiscordDB(name).get())),
        )

    async def cmd_whitelist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!whitelist_cmd [*cmds]
        ->description Whitelist commands
        -----
        Implement pg!whitelist_cmd, to whitelist commands
        """
        db_obj = db.DiscordDB("blacklist")
        commands = await db_obj.get([])
        cnt = 0
        for cmd in cmds:
            if cmd in commands:
                cnt += 1
                commands.remove(cmd)

        await db_obj.write(commands)

        await embed_utils.replace(
            self.response_msg,
            "Whitelisted!",
            f"Successfully whitelisted {cnt} command(s)",
        )

    async def cmd_blacklist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!blacklist_cmd [*cmds]
        ->description Blacklist commands
        -----
        Implement pg!blacklist_cmd, to blacklist commands
        """
        db_obj = db.DiscordDB("blacklist")
        commands = await db_obj.get([])

        cnt = 0
        for cmd in cmds:
            if cmd not in commands and cmd != "whitelist_cmd":
                cnt += 1
                commands.append(cmd)

        await db_obj.write(commands)

        await embed_utils.replace(
            self.response_msg,
            "Blacklisted!",
            f"Successfully blacklisted {cnt} command(s)",
        )

    async def cmd_clock(
        self,
        action: str = "",
        timezone: float = 0,
        color: Optional[pygame.Color] = None,
        member: Optional[discord.Member] = None,
    ):
        """
        ->type Admin commands
        ->signature pg!clock [action] [timezone] [color] [member]
        ->description 24 Hour Clock showing <@&778205389942030377> 's who are available to help
        ->extended description
        Admins can run clock with more arguments, to add/update/remove other members.
        `pg!clock update [timezone in hours] [color as hex string] [mention member]`
        `pg!clock remove [mention member]`
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        return await super().cmd_clock(action, timezone, color, member)

    async def cmd_eval(self, code: CodeBlock):
        """
        ->type Admin commands
        ->signature pg!eval <command>
        ->description Execute a line of command without restrictions
        -----
        Implement pg!eval, for admins to run arbitrary code on the bot
        """
        try:
            script = compile(code.code, "<string>", "eval")  # compile script

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            total = time.perf_counter() - script_start

            await embed_utils.replace(
                self.response_msg,
                f"Return output (code executed in {utils.format_time(total)}):",
                utils.code_block(repr(eval_output)),
            )
        except Exception as ex:
            raise BotException(
                "An exception occured:",
                utils.code_block(
                    type(ex).__name__ + ": " + ", ".join(map(str, ex.args))
                ),
            )

    async def cmd_sudo(self, msg: String):
        """
        ->type More admin commands
        ->signature pg!sudo <msg>
        ->description Send a message trough the bot
        -----
        Implement pg!sudo, for admins to send messages via the bot
        """
        await self.channel.send(msg.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_edit(self, edit_msg: discord.Message, msg: String):
        """
        ->type More admin commands
        ->signature pg!sudo_edit <edit_msg> <msg>
        ->description Edit a message that the bot sent.
        -----
        Implement pg!sudo_edit, for admins to edit messages via the bot
        """
        await edit_msg.edit(content=msg.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_get(
        self, msg: discord.Message, attach: bool = False, info: bool = False
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_get <message> [attach] [stats]
        ->description Get the text of a message through the bot

        Get the contents of the embed of a message from the given arguments and send it as another message
        (as an embed code block or a message with a `.txt` file attachment containing the message data)
        to the channel where this command was invoked.
        -----
        Implement pg!sudo_get, to return the the contents of a message as an embed or in a text file.
        """
        if attach:
            try:
                with open("messagedata.txt", "w", encoding="utf-8") as msg_txt:
                    msg_txt.write(msg.content)

                await self.response_msg.channel.send(
                    file=discord.File("messagedata.txt"),
                    embed=await embed_utils.send_2(
                        None,
                        author_name="Message data",
                        description=f"**[View Original Message]({msg.jump_url})**",
                        color=0xFFFFAA,
                    ),
                )
            finally:
                if os.path.exists("messagedata.txt"):
                    os.remove("messagedata.txt")

        elif info:
            info_embed = embed_utils.get_msg_info_embed(msg)
            info_embed.set_author(name="Message data & info")
            info_embed.title = ""
            info_embed.description = f"```\n{msg.content}```\n\u2800"
            await self.response_msg.channel.send(embed=info_embed)

        else:
            await embed_utils.send_2(
                self.response_msg.channel,
                author_name="Message data",
                description="```\n{0}```".format(
                    msg.content.replace("```", "\\`\\`\\`")
                ),
                fields=(
                    ("\u2800", f"**[View Original Message]({msg.jump_url})**", False),
                ),
            )

        await self.response_msg.delete()

    async def cmd_sudo_clone(
        self,
        msg: discord.Message,
        embeds: bool = True,
        attach: bool = True,
        spoiler: bool = False,
        info: bool = False,
        author: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_clone <msg> [embeds] [attach] [spoiler] [info] [author]
        ->description Clone a message through the bot

        Get a message from the given arguments and send it as another message to the channel where this command was invoked.
        -----
        Implement pg!sudo_clone, to get the content of a message and send it.
        """

        msg_files = None
        cloned_msg = None

        if msg.attachments and attach:
            blank_filename = f"filetoolarge {int(time.perf_counter_ns())}.txt"
            try:
                with open(blank_filename, "w", encoding="utf-8") as toolarge:
                    toolarge.write("This file is too large to be archived.")

                    msg_files = [
                        await a.to_file(spoiler=spoiler or a.is_spoiler())
                        if a.size <= common.GUILD_MAX_FILE_SIZE
                        else discord.File(toolarge)
                        for a in msg.attachments
                    ]

            finally:
                if os.path.exists(blank_filename):
                    os.remove(blank_filename)

        if msg.embeds and embeds:
            cloned_msg = await self.response_msg.channel.send(
                content=msg.content, embed=msg.embeds[0], files=msg_files
            )

            for i in range(1, len(msg.embeds)):
                await self.response_msg.channel.send(
                    embed=msg.embeds[i],
                )
        else:
            cloned_msg = await self.response_msg.channel.send(
                content=msg.content,
                embed=msg.embeds[0] if msg.embeds and embeds else None,
                files=msg_files,
            )

        if info:
            await self.response_msg.channel.send(
                embed=embed_utils.get_msg_info_embed(msg, author=author),
                reference=cloned_msg,
            )
        await self.response_msg.delete()

    async def cmd_sudo_info(self, msg: discord.Message, author: bool = True):
        """
        ->type More admin commands
        ->signature pg!sudo_info <message> [author_bool]
        ->description Get information about a message and its author

        Get information about a message and its author in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!sudo_info, to get information about a message and its author.
        """

        await self.response_msg.channel.send(
            embed=embed_utils.get_msg_info_embed(msg, author=author)
        )
        await self.response_msg.delete()

    async def cmd_member_info(self, member: Optional[discord.Member] = None):
        """
        ->type More admin commands
        ->signature pg!member_info [member]
        ->description Get information about a message and its author

        Get information about a member in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!member_info, to get information about a member.
        """
        if member is None:
            member = self.author

        await self.response_msg.channel.send(
            embed=embed_utils.get_user_info_embed(member)
        )
        await self.response_msg.delete()

    async def cmd_heap(self):
        """
        ->type Admin commands
        ->signature pg!heap
        ->description Show the memory usage of the bot
        -----
        Implement pg!heap, for admins to check memory taken up by the bot
        """
        mem = process.memory_info().rss
        await embed_utils.replace(
            self.response_msg,
            "Total memory used:",
            f"**{utils.format_byte(mem, 4)}**\n({mem} B)",
        )

    async def cmd_stop(self):
        """
        ->type Admin commands
        ->signature pg!stop [*ids]
        ->description Stop the bot
        ->extended description
        Any additional arguments are IDs of members running test bots, to stop
        the test bots of particular wizards
        -----
        The actual pg!stop function is implemented elsewhere, this is just
        a stub for the docs
        """

    async def cmd_archive(
        self,
        origin: discord.TextChannel,
        quantity: int,
        destination: Optional[discord.TextChannel] = None,
        before: Optional[Union[int, datetime.datetime]] = None,
        after: Optional[Union[int, datetime.datetime]] = None,
        around: Optional[Union[int, datetime.datetime]] = None,
        raw: bool = False,
        show_header: bool = True,
        show_author: bool = True,
        divider_str: String = String("-" * 56),
        group_by_author: bool = True,
        oldest_first: bool = True,
        same_channel: bool = False,
    ):
        """
        ->type Admin commands
        ->signature pg!archive <origin channel> <quantity> [destination channel]
        [before] [after] [around] [raw=False] [show_header=True] [show_author=True]
        [divider_str=("-"*56)] [group_by_author=True] [oldest_first=True] [same_channel=False]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """

        archive_header_msg = None
        archive_header_msg_embed = None

        if destination is None:
            destination = self.channel

        if origin == destination and not same_channel:
            raise BotException(
                "Cannot execute command:", "Origin and destination channels are same"
            )

        tz_utc = datetime.timezone.utc
        datetime_format_str = f"%a, %d %b %Y - %H:%M:%S (UTC)"
        blank_filename = f"filetoolarge {int(time.perf_counter_ns())}.txt"

        divider_str = divider_str.string

        if isinstance(before, int):
            try:
                before = await origin.fetch_message(before)
            except discord.NotFound:
                raise BotException(
                    "Invalid `before` argument",
                    "`before` has to be an ID to a message from the origin channel",
                )

        if isinstance(after, int):
            try:
                after = await origin.fetch_message(after)
            except discord.NotFound:
                raise BotException(
                    "Invalid `after` argument",
                    "`after` has to be an ID to a message from the origin channel",
                )

        if isinstance(around, int):
            try:
                around = await origin.fetch_message(around)
            except discord.NotFound:
                raise BotException(
                    "Invalid `around` argument",
                    "`around` has to be an ID to a message from the origin channel",
                )

        if quantity <= 0:
            if quantity == -1 and not after:
                raise BotException(
                    "Invalid `quantity` argument",
                    "`quantity` must be above -1 when `after=` is not specified.",
                )
            elif quantity != -1:
                raise BotException(
                    "Invalid `quantity` argument",
                    "Quantity has to be a positive integer (or `-1` when `after=` is specified).",
                )

        await destination.trigger_typing()
        messages = await origin.history(
            limit=quantity if quantity != -1 else None,
            before=before,
            after=after,
            around=around,
        ).flatten()

        if not messages:
            raise BotException(
                "Invalid time range",
                "No messages were found for the specified timestamps.",
            )

        if not after and oldest_first:
            messages.reverse()

        with open(blank_filename, "w") as toolarge_txt:
            toolarge_txt.write("This file is too large to be archived.")

        if show_header and not raw:
            start_date = messages[0].created_at.replace(tzinfo=None)
            end_date = messages[-1].created_at.replace(tzinfo=None)
            start_date_str = start_date.strftime(datetime_format_str)
            end_date_str = end_date.strftime(datetime_format_str)

            if start_date == end_date:
                msg = f"On `{start_date_str} | {start_date.isoformat()}`"
            else:
                msg = (
                    f"From\n> `{start_date_str} | {start_date.isoformat()}`\n"
                    + f"To\n> `{end_date_str} | {end_date.isoformat()}`"
                )

            archive_header_msg_embed = embed_utils.create(
                title=f"__Archive of `#{origin.name}`__",
                description=f"\nAn archive of **{origin.mention}** "
                f"({len(messages)} message(s))\n\n" + msg,
                color=0xFFFFFF,
                footer_text="Status: Incomplete",
            )

            archive_header_msg = await destination.send(embed=archive_header_msg_embed)

        no_mentions = discord.AllowedMentions.none()
        try:
            for i, msg in enumerate(
                reversed(messages) if not oldest_first else messages
            ):
                author = msg.author
                await destination.trigger_typing()

                attached_files = [
                    (
                        await a.to_file(spoiler=a.is_spoiler())
                        if a.size <= common.GUILD_MAX_FILE_SIZE
                        else discord.File(blank_filename)
                    )
                    for a in msg.attachments
                ]

                if not raw:
                    author_embed = None
                    current_divider_str = divider_str
                    if show_author or divider_str:
                        if (
                            group_by_author
                            and i > 0
                            and messages[i - 1].author == author
                        ):
                            # no author info or divider for mesmages next to each other sharing an author
                            current_divider_str = None
                        else:
                            author_embed = embed_utils.create(
                                description=f"{author.mention}"
                                f" (`{author.name}#{author.discriminator}`)\n"
                                f"**[View Original]({msg.jump_url})**",
                                color=0x36393F,
                                footer_text="\nISO Time: "
                                f"{msg.created_at.replace(tzinfo=None).isoformat()}"
                                f"\nID: {author.id}",
                                timestamp=msg.created_at.replace(tzinfo=tz_utc),
                                footer_icon_url=str(author.avatar_url),
                            )

                        if author_embed or current_divider_str:
                            await destination.send(
                                content=current_divider_str,
                                embed=author_embed,
                                allowed_mentions=no_mentions,
                            )

                await destination.trigger_typing()

                await destination.send(
                    content=msg.content,
                    embed=msg.embeds[0] if msg.embeds else None,
                    files=attached_files if attached_files else None,
                    allowed_mentions=no_mentions,
                )

                for i in range(1, len(msg.embeds)):
                    await destination.trigger_typing()
                    await destination.send(embed=msg.embeds[i])

                await destination.trigger_typing()

        finally:
            if os.path.exists(blank_filename):
                os.remove(blank_filename)

        if divider_str and not raw:
            await destination.send(content=divider_str)

        await embed_utils.replace(
            self.response_msg, f"Successfully archived {len(messages)} message(s)!", ""
        )

        if show_header and not raw:
            archive_header_msg_embed.set_footer(text="Status: Completed")
            await embed_utils.replace_from_dict(
                archive_header_msg, archive_header_msg_embed.to_dict()
            )
        await self.response_msg.delete(delay=5.0)

    async def cmd_poll(
        self,
        desc: String,
        *emojis: String,
        author: Optional[String] = None,
        color: Optional[pygame.Color] = None,
        url: Optional[String] = None,
        img_url: Optional[String] = None,
        thumbnail: Optional[String] = None,
    ):
        """
        ->type Admin commands
        ->signature pg!poll <description> [*emojis] [author] [color] [url] [image_url] [thumbnail]
        ->description Start a poll.
        ->extended description
        The args must be strings with one emoji and one description of said emoji (see example command). \
        The emoji must be a default emoji or one from this server. To close the poll see pg!close_poll.
        Additionally admins can specify some keyword arguments to improve the appearance of the poll
        ->example command pg!poll "Which apple is better?" "🍎" "Red apple" "🍏" "Green apple"
        """
        embed_dict = {}
        if author:
            embed_dict["author"] = {"name": author.string}

        if color:
            embed_dict["color"] = utils.color_to_rgb_int(color)

        if url:
            embed_dict["url"] = url.string

        if img_url:
            embed_dict["image"] = {"url": img_url.string}

        if thumbnail:
            embed_dict["thumbnail"] = {"url": thumbnail.string}

        return await super().cmd_poll(desc, *emojis, admin_embed=embed_dict)

    async def cmd_close_poll(
        self,
        msg: discord.Message,
        color: pygame.Color = pygame.Color("#A83232"),
    ):
        """
        ->type Admin commands
        ->signature pg!close_poll <msg> [color]
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        The color is the color of the closed poll embed
        """
        return await super().cmd_close_poll(msg, color)

    
    async def cmd_msudo(
        self,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
        
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo [*args]
        ->description Send an embed through the bot
        ->extended description
        ```
        pg!emsudo {embed_tuple}
        pg!emsudo {embed_dict}
        pg!emsudo {message_id}
        pg!emsudo {channel_id} {message_id}
        pg!emsudo {empty_str}
        ```
        Generate an embed from the given arguments and send it with a message to the channel where this command was invoked.
        -----
        Implement pg!emsudo, for admins to send embeds via the bot
        """

        util_send_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        attachment_msg: discord.Message = None
        only_description = False

        if data is None:
            attachment_msg = self.invoke_msg
        
        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                only_description = True
                util_send_embed_args.update(description=data.string)
        
        elif isinstance(data, discord.Message):
            attachment_msg = data
            

        if attachment_msg:
            if not attachment_msg.attachments:
                await embed_utils.replace(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )
                return

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith("text")
                ):
                    attachment_obj = attachment
                    break
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )
                return

            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await embed_utils.send_from_dict(self.invoke_msg.channel, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return
            
        if not only_description:    
            try:
                args = eval(data.code)
            except Exception as e:
               
                raise BotException(
                    self.response_msg, "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```"
                )

            if isinstance(args, dict):
                await embed_utils.send_from_dict(self.invoke_msg.channel, args)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            arg_count = len(args)

            if arg_count > 0:
                if isinstance(args[0], (tuple, list)):
                    if len(args[0]) == 3:
                        util_send_embed_args.update(
                            author_name=args[0][0],
                            author_url=args[0][1],
                            author_icon_url=args[0][2],
                        )
                    elif len(args[0]) == 2:
                        util_send_embed_args.update(
                            author_name=args[0][0],
                            author_url=args[0][1],
                        )
                    elif len(args[0]) == 1:
                        util_send_embed_args.update(
                            author_name=args[0][0],
                        )

                else:
                    util_send_embed_args.update(
                        author_name=args[0],
                    )
            else:
                raise BotException("Invalid arguments!", "")

            if arg_count > 1:
                if isinstance(args[1], (tuple, list)):
                    if len(args[1]) == 3:
                        util_send_embed_args.update(
                            title=args[1][0],
                            url=args[1][1],
                            thumbnail_url=args[1][2],
                        )

                    elif len(args[1]) == 2:
                        util_send_embed_args.update(
                            title=args[1][0],
                            url=args[1][1],
                        )

                    elif len(args[1]) == 1:
                        util_send_embed_args.update(
                            title=args[1][0],
                        )

                else:
                    util_send_embed_args.update(
                        title=args[1],
                    )

            if arg_count > 2:
                if isinstance(args[2], (tuple, list)):
                    if len(args[2]) == 2:
                        util_send_embed_args.update(
                            description=args[2][0],
                            image_url=args[2][1],
                        )

                    elif len(args[2]) == 1:
                        util_send_embed_args.update(
                            description=args[2][0],
                        )

                else:
                    util_send_embed_args.update(
                        description=args[2],
                    )

            if arg_count > 3:
                if args[3] > -1:
                    util_send_embed_args.update(
                        color=args[3],
                    )

            if arg_count > 4:
                try:
                    util_send_embed_args.update(fields=embed_utils.get_fields(args[4]))
                except TypeError:
                    raise BotException(
                        self.response_msg, "Invalid format for field string(s)!",
                        " The format should be `<name|value|inline>`"
                    )

            if arg_count > 5:
                if isinstance(args[5], (tuple, list)):
                    if len(args[5]) == 2:
                        util_send_embed_args.update(
                            footer_text=args[5][0],
                            footer_icon_url=args[5][1],
                        )

                    elif len(args[5]) == 1:
                        util_send_embed_args.update(
                            footer_text=args[5][0],
                        )

                else:
                    util_send_embed_args.update(
                        footer_text=args[5],
                    )

            if arg_count > 6:
                util_send_embed_args.update(timestamp=args[6])

        await embed_utils.send_2(self.invoke_msg.channel, **util_send_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_msudo_add(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
        overwrite: bool = False
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add [*args]
        ->description Add an embed through the bot
        ->extended description
        ```
        pg!emsudo_add ({target_message_id}, *{embed_tuple})
        pg!emsudo_add ({target_message_id}, {embed_dict})
        pg!emsudo_add {target_message_id} {message_id}
        pg!emsudo_add {target_message_id} {channel_id} {message_id}
        pg!emsudo_add ({target_message_id}, {empty_str})
        ```
        Add an embed to a message (even if it has one, it will be replaced) in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_add, for admins to add embeds to messages via the bot
        """

        if not msg.embeds or overwrite:
            await self.cmd_msudo_replace(msg=msg, data=data)
        else:
            raise BotException(
                "Cannot overwrite embed!",
                "The given message's embed cannot be overwritten when"
                " `overwrite=` is set to `False`"
            )


    async def cmd_msudo_replace(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_replace [*args]
        ->description Replace an embed through the bot
        ->extended description
        ```
        pg!emsudo_replace ({target_message_id}, *{embed_tuple})
        pg!emsudo_replace ({target_message_id}, {embed_dict})
        pg!emsudo_replace {target_message_id} {message_id}
        pg!emsudo_replace {target_message_id} {channel_id} {message_id}
        pg!emsudo_replace ({target_message_id}, {empty_str})
        ```
        Replace the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_replace, for admins to replace embeds via the bot
        """

        util_replace_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        attachment_msg: discord.Message = None
        only_description = False

        if data is None:
            attachment_msg = self.invoke_msg
        
        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                only_description = True
                util_replace_embed_args.update(description=data.string)
        
        elif isinstance(data, discord.Message):
            attachment_msg = data
    
        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
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
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )

            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await embed_utils.replace_from_dict(msg, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return
            
        if not only_description:    
            try:
                args = eval(data.code)
            except Exception as e:
                raise BotException(
                    self.response_msg,
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```"
                )

            if isinstance(args, dict):
                await embed_utils.replace_from_dict(msg, args)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            arg_count = len(args)

            if arg_count > 0:
                if isinstance(args[0], (tuple, list)):
                    if len(args[0]) == 3:
                        util_replace_embed_args.update(
                            author_name=args[0][0],
                            author_url=args[0][1],
                            author_icon_url=args[0][2],
                        )
                    elif len(args[0]) == 2:
                        util_replace_embed_args.update(
                            author_name=args[0][0],
                            author_url=args[0][1],
                        )
                    elif len(args[0]) == 1:
                        util_replace_embed_args.update(
                            author_name=args[0][0],
                        )

                else:
                    util_replace_embed_args.update(
                        author_name=args[0],
                    )
            else:
                raise BotException("Invalid arguments!", "")

            if arg_count > 1:
                if isinstance(args[1], (tuple, list)):
                    if len(args[1]) == 3:
                        util_replace_embed_args.update(
                            title=args[1][0],
                            url=args[1][1],
                            thumbnail_url=args[1][2],
                        )

                    elif len(args[1]) == 2:
                        util_replace_embed_args.update(
                            title=args[1][0],
                            url=args[1][1],
                        )

                    elif len(args[1]) == 1:
                        util_replace_embed_args.update(
                            title=args[1][0],
                        )

                else:
                    util_replace_embed_args.update(
                        title=args[1],
                    )

            if arg_count > 2:
                if isinstance(args[2], (tuple, list)):
                    if len(args[2]) == 2:
                        util_replace_embed_args.update(
                            description=args[2][0],
                            image_url=args[2][1],
                        )

                    elif len(args[2]) == 1:
                        util_replace_embed_args.update(
                            description=args[2][0],
                        )

                else:
                    util_replace_embed_args.update(
                        description=args[2],
                    )

            if arg_count > 3:
                if args[3] > -1:
                    util_replace_embed_args.update(
                        color=args[3],
                    )

            if arg_count > 4:
                try:
                    util_replace_embed_args.update(fields=embed_utils.get_fields(args[4]))
                except TypeError:
                    raise BotException(
                        self.response_msg, "Invalid format for field string(s)!",
                        " The format should be `<name|value|inline>`"
                    )

            if arg_count > 5:
                if isinstance(args[5], (tuple, list)):
                    if len(args[5]) == 2:
                        util_replace_embed_args.update(
                            footer_text=args[5][0],
                            footer_icon_url=args[5][1],
                        )

                    elif len(args[5]) == 1:
                        util_replace_embed_args.update(
                            footer_text=args[5][0],
                        )

                else:
                    util_replace_embed_args.update(
                        footer_text=args[5],
                    )

            if arg_count > 6:
                util_replace_embed_args.update(timestamp=args[6])

        await embed_utils.replace_2(msg, **util_replace_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_msudo_edit(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_edit [*args]
        ->description Edit an embed through the bot
        ->extended description
        ```
        pg!emsudo_edit ({target_message_id}, *{embed_tuple})
        pg!emsudo_edit ({target_message_id}, {embed_dict})
        pg!emsudo_edit {target_message_id} {message_id}
        pg!emsudo_edit {target_message_id} {channel_id} {message_id}
        pg!emsudo_edit ({target_message_id}, {empty_str})
        ```
        Update the given attributes of an embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_edit, for admins to replace embeds via the bot
        """

        util_edit_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        attachment_msg: discord.Message = None
        only_description = False

        if not msg.embeds:
            raise BotException(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )

        if data is None:
            attachment_msg = self.invoke_msg
        
        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                only_description = True
                util_edit_embed_args.update(description=data.string)
        
        elif isinstance(data, discord.Message):
            attachment_msg = data
    
        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
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
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )

            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await embed_utils.edit_from_dict(msg, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return
            
        if not only_description:    
            try:
                args = eval(data.code)
            except Exception as e:
                raise BotException(
                    self.response_msg,
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```"
                )

            if isinstance(args, dict):
                await embed_utils.edit_from_dict(msg, args)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            arg_count = len(args)

            if arg_count > 0:
                if isinstance(args[0], (tuple, list)):
                    if len(args[0]) == 3:
                        util_edit_embed_args.update(
                            author_name=args[0][0],
                            author_url=args[0][1],
                            author_icon_url=args[0][2],
                        )
                    elif len(args[0]) == 2:
                        util_edit_embed_args.update(
                            author_name=args[0][0],
                            author_url=args[0][1],
                        )
                    elif len(args[0]) == 1:
                        util_edit_embed_args.update(
                            author_name=args[0][0],
                        )

                else:
                    util_edit_embed_args.update(
                        author_name=args[0],
                    )
            else:
                raise BotException("Invalid arguments!", "")

            if arg_count > 1:
                if isinstance(args[1], (tuple, list)):
                    if len(args[1]) == 3:
                        util_edit_embed_args.update(
                            title=args[1][0],
                            url=args[1][1],
                            thumbnail_url=args[1][2],
                        )

                    elif len(args[1]) == 2:
                        util_edit_embed_args.update(
                            title=args[1][0],
                            url=args[1][1],
                        )

                    elif len(args[1]) == 1:
                        util_edit_embed_args.update(
                            title=args[1][0],
                        )

                else:
                    util_edit_embed_args.update(
                        title=args[1],
                    )

            if arg_count > 2:
                if isinstance(args[2], (tuple, list)):
                    if len(args[2]) == 2:
                        util_edit_embed_args.update(
                            description=args[2][0],
                            image_url=args[2][1],
                        )

                    elif len(args[2]) == 1:
                        util_edit_embed_args.update(
                            description=args[2][0],
                        )

                else:
                    util_edit_embed_args.update(
                        description=args[2],
                    )

            if arg_count > 3:
                util_edit_embed_args.update(
                    color=args[3],
                )
            else:
                util_edit_embed_args.update(
                    color=-1,
                )

            if arg_count > 4:
                try:
                    util_edit_embed_args.update(fields=embed_utils.get_fields(args[4]))
                except TypeError:
                    raise BotException(
                        self.response_msg, "Invalid format for field string(s)!",
                        " The format should be `<name|value|inline>`"
                    )

            if arg_count > 5:
                if isinstance(args[5], (tuple, list)):
                    if len(args[5]) == 2:
                        util_edit_embed_args.update(
                            footer_text=args[5][0],
                            footer_icon_url=args[5][1],
                        )

                    elif len(args[5]) == 1:
                        util_edit_embed_args.update(
                            footer_text=args[5][0],
                        )

                else:
                    util_edit_embed_args.update(
                        footer_text=args[5],
                    )

            if arg_count > 6:
                util_edit_embed_args.update(timestamp=args[6])

        await embed_utils.edit_2(msg, **util_edit_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_msudo_clone(self, msg: discord.Message):
        """
        ->type emsudo commands
        ->signature pg!emsudo_clone [*args]
        ->description Clone all embeds.
        ->extended description
        ```
        pg!emsudo_clone {message_id}
        pg!emsudo_clone {channel_id} {message_id}
        ```
        Get a message from the given arguments and send it as another message (only containing its embed) to the channel where this command was invoked.
        -----
        Implement pg!_emsudo_clone, to get the embed of a message and send it.
        """

        if not msg.embeds:
            raise BotException(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )

        for embed in msg.embeds:
            await self.response_msg.channel.send(embed=embed)

        await self.response_msg.delete()

    async def cmd_msudo_get(
        self,
        msg: discord.Message,
        attrib_string: Optional[String] = String("")
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_get [*args]
        ->description Get the embed data of a message
        ->extended description
        ```
        pg!emsudo_get {message_id} {optional_embed_attr} {optional_embed_attr}...
        pg!emsudo_get {channel_id} {message_id} {optional_embed_attr} {optional_embed_attr}...
        ```
        Get the contents of the embed of a message from the given arguments and send it as another message (with a `.txt` file attachment containing the embed data as a Python dictionary) to the channel where this command was invoked.
        If specific embed attributes are specified, then only those will be fetched from the embed of the given message, otherwise all attributes will be fetched.
        ->example command pg!emsudo_get 123456789123456789 title
        pg!emsudo_get 123456789123456789 98765432198765444321 description fields
        pg!emsudo_get 123456789123456789 98765432198765444321
        -----
        Implement pg!emsudo_get, to return the embed of a message as a dictionary in a text file.
        """

        embed_attr_keys = {
            "author",
            "provider",
            "title",
            "url",
            "description",
            "type",
            "color",
            "fields",
            "thumbnail",
            "image",
            "footer",
            "timestamp",
        }

        reduced_embed_attr_keys = set()
        filtered_field_indices = []
        offset_idx = None

        attrib_string = attrib_string.string
        attrib_tuple = attrib_string.split()
        
        for i in range(len(attrib_tuple)):
            if attrib_tuple[i] == "fields":
                reduced_embed_attr_keys.add("fields")
                for j in range(i + 1, len(attrib_tuple)):
                    if self.args[j].isnumeric():
                        filtered_field_indices.append(int(attrib_tuple[j]))
                    else:
                        offset_idx = j
                        break
                else:
                    break

                if offset_idx:
                    break

            elif attrib_tuple[i] in attrib_tuple:
                reduced_embed_attr_keys.add(attrib_tuple[i])
            else:
                raise BotException(
                    "Cannot execute command:",
                    "Invalid embed attribute names!",
                )

        if offset_idx:
            for i in range(offset_idx, len(attrib_tuple)):
                if attrib_tuple[i] in embed_attr_keys:
                    reduced_embed_attr_keys.add(attrib_tuple[i])
                else:
                    raise BotException(
                        "Cannot execute command:",
                        "Invalid embed attribute names!",
                    )

        if not msg.embeds:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )
            return

        embed_dict = msg.embeds[0].to_dict()

        if reduced_embed_attr_keys:
            for key in tuple(embed_dict.keys()):
                if key not in reduced_embed_attr_keys:
                    del embed_dict[key]

            if (
                "fields" in reduced_embed_attr_keys
                and "fields" in embed_dict
                and filtered_field_indices
            ):
                embed_dict["fields"] = [
                    embed_dict["fields"][idx] for idx in sorted(filtered_field_indices)
                ]

        embed_dict_code = repr({k: embed_dict[k] for k in reversed(embed_dict.keys())})

        with open("embeddata.txt", "w", encoding="utf-8") as embed_txt:
            embed_txt.write(black.format_str(embed_dict_code, mode=black.FileMode()))

        await self.response_msg.channel.send(
            embed=await embed_utils.send_2(
                None,
                author_name="Embed Data",
                title=embed_dict.get("title", "(add a title by editing this embed)"),
                fields=(
                    (
                        "\u2800",
                        f"**[View Original Message]({msg.jump_url})**",
                        True,
                    ),
                ),
            ),
            file=discord.File("embeddata.txt"),
        )
        await self.response_msg.delete()