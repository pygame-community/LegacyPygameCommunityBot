
import os
import sys
import time
import traceback
from datetime import datetime
import discord
from discord.embeds import EmptyEmbed
import psutil
from discord.embeds import EmptyEmbed

from . import common, user_commands, util

process = psutil.Process(os.getpid())


class AdminCommand(user_commands.UserCommand):
    """
    Base class to handle admin commands. Inherits all user commands, and also
    implements some more
    """

    async def cmd_eval(self):
        """
        ->type Admin commands
        ->signature pg!eval [command]
        ->description Execute a line of command without restrictions
        -----
        Implement pg!eval, for admins to run arbitrary code on the bot
        """
        try:
            script = compile(self.string, "<string>", "eval")  # compile script

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            total = time.perf_counter() - script_start

            await util.replace_embed(
                self.response_msg,
                f"Return output (code executed in {util.format_time(total)}):",
                util.code_block(repr(eval_output))
            )
        except Exception as ex:
            await util.replace_embed(
                self.response_msg,
                common.EXC_TITLES[1],
                util.code_block(
                    type(ex).__name__ + ": " + ", ".join(map(str, ex.args))
                )
            )

    async def cmd_sudo(self):
        """
        ->type More admin commands
        ->signature pg!sudo [message]
        ->description Send a message trough the bot
        -----
        Implement pg!sudo, for admins to send messages via the bot
        """
        await self.invoke_msg.channel.send(self.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_edit(self):
        """
        ->type More admin commands
        ->signature pg!sudo_edit [message_id] [message]
        ->description Edit a message that the bot sent.
        -----
        Implement pg!sudo_edit, for admins to edit messages via the bot
        """
        edit_msg = await self.invoke_msg.channel.fetch_message(
            util.filter_id(self.args[0])
        )
        await edit_msg.edit(content=self.string[len(self.args[0]) + 1:])
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_get(self):
        """
        ->type More admin commands
        ->signature pg!sudo_get [*args]
        ->description Get the text of a message through the bot
        ->extended description
        ```
        pg!sudo_get {message_id}
        pg!sudo_get {channel_id} {message_id}
        ```
        Get the contents of the embed of a message from the given arguments and send it as another message (with a `.txt` file attachment containing the embed data as a Python dictionary) to the channel where this command was invoked.
        -----
        Implement pg!sudo_get, to return the the contents of a message in a text file.
        """
        self.check_args(1, maxarg=2)

        src_msg_id = None
        src_msg = None
        src_channel_id = self.invoke_msg.channel.id
        src_channel = self.invoke_msg.channel

        if len(self.args) == 2:
            try:
                src_channel_id = int(self.args[0])
                src_msg_id = int(self.args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message and/or channel id(s)!"
                )
                return
            
            src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
            if src_channel is None:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid channel id!"
                )
                return
        else:
            try:
                src_msg_id = int(self.args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return
        try:
            src_msg = await src_channel.fetch_message(src_msg_id)
        except discord.NotFound:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "Invalid message id!"
            )
            return
        
        with open("messagedata.txt", "w", encoding="utf-8") as msg_txt:
            msg_txt.write(src_msg.content)

        await self.response_msg.channel.send(
            content=f"__Message data__\n*(Source: <https://discord.com/channels/{src_msg.author.guild.id}/{src_channel.id}/{src_msg.id}>)*",
            file=discord.File("messagedata.txt")
        )
        await self.response_msg.delete()

    async def cmd_sudo_clone(self):
        """
        ->type More admin commands
        ->signature pg!sudo_clone [*args]
        ->description Clone a message through the bot
        ->extended description
        ```
        pg!sudo_clone {message_id}
        pg!sudo_clone {channel_id} {message_id}
        pg!sudo_clone {message_id} {include_embeds_bool}
        pg!sudo_clone {channel_id} {message_id} {include_embeds_bool}
        pg!sudo_clone {message_id} {include_embeds_bool} {include_attachments_bool}
        pg!sudo_clone {channel_id} {message_id} {include_embeds_bool} {include_attachments_bool}
        ```
        Get a message from the given arguments and send it as another message to the channel where this command was invoked.
        -----
        Implement pg!sudo_clone, to get the content of a message and send it.
        """
        self.check_args(1, maxarg=4)

        src_msg_id = None
        src_msg = None
        src_channel_id = self.invoke_msg.channel.id
        src_channel = self.invoke_msg.channel

        include_embeds = True
        include_attachments = True

        if len(self.args) == 4:
            try:
                src_channel_id = int(self.args[0])
                src_msg_id = int(self.args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message and/or channel id(s)!"
                )
                return
            
            src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
            if src_channel is None:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid channel id!"
                )
                return
            
            if  self.args[2] == "0" or self.args[2] == "False":
                include_embeds = False
            elif self.args[2] == "1" or self.args[2] == "True":
                include_embeds = True

            if  self.args[3] == "0" or self.args[3] == "False":
                include_attachments = False
            elif self.args[3] == "1" or self.args[3] == "True":
                include_attachments = True

        elif len(self.args) == 3:
            if self.args[1] in ("0", "1" , "True", "False"):

                if  self.args[1] == "0" or self.args[1] == "False":
                    include_embeds = False
                elif self.args[1] == "1" or self.args[1] == "True":
                    include_embeds = True

                if self.args[2] == "0" or self.args[2] == "False":
                    include_attachments = False
                elif self.args[2] == "1" or self.args[2] == "True":
                    include_attachments = True
                
                try:
                    src_msg_id = int(self.args[0])
                except ValueError:
                    await util.replace_embed(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid message id!"
                    )
                    return
            else:
                
                if self.args[2] == "0" or self.args[2] == "False":
                    include_embeds = False
                elif self.args[2] == "1" or self.args[2] == "True":
                    include_embeds = True
                
                try:
                    src_channel_id = int(self.args[0])
                    src_msg_id = int(self.args[1])
                except ValueError:
                    await util.replace_embed(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid message and/or channel id(s)!"
                    )
                    return
                
                src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
                if src_channel is None:
                    await util.replace_embed(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid channel id!"
                    )
                    return

        elif len(self.args) == 2:

            if self.args[1] in ("0", "1" , "True", "False"):
                if  self.args[1] == "0" or self.args[1] == "False":
                    include_embeds = False
                elif self.args[1] == "1" or self.args[1] == "True":
                    include_embeds = True
                
                try:
                    src_msg_id = int(self.args[0])
                except ValueError:
                    await util.replace_embed(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid message id!"
                    )
                    return
            else:
                try:
                    src_channel_id = int(self.args[0])
                    src_msg_id = int(self.args[1])
                except ValueError:
                    await util.replace_embed(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid message and/or channel id(s)!"
                    )
                    return
                
                src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
                if src_channel is None:
                    await util.replace_embed(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid channel id!"
                    )
                    return
        else:
            try:
                src_msg_id = int(self.args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return
        try:
            src_msg: discord.Message = await src_channel.fetch_message(src_msg_id)
        except discord.NotFound:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "Invalid message id!"
            )
            return

        msg_files = None

        if src_msg.attachments and include_attachments:
            msg_files = []
            for att in src_msg.attachments:
                att_file = await att.to_file()
                msg_files.append(att_file)
        
        await self.response_msg.channel.send(
            content=src_msg.content,
            embed=src_msg.embeds[0] if src_msg.embeds and include_embeds else None,
            files=msg_files
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
        self.check_args(0)
        mem = process.memory_info().rss
        await util.replace_embed(
            self.response_msg,
            "Total memory used:",
            f"**{util.format_byte(mem, 4)}**\n({mem} B)"
        )


    async def cmd_stop(self):
        """
        ->type Admin commands
        ->signature pg!stop
        ->description Stop the bot
        -----
        Implement pg!stop, for admins to stop the bot
        """
        self.check_args(0)
        await util.replace_embed(
            self.response_msg,
            "Stopping bot...",
            "Change da world,\nMy final message,\nGoodbye."
        )
        sys.exit(0)


    async def cmd_emsudo_c(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_c [*args]
        ->description Send an embed trough the bot
        -----
        Implement pg!emsudo_c, for admins to send embeds via the bot
        """
        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return

        if len(args) == 1:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                ""
            )
        elif len(args) == 2:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                args[1]
            )
        elif len(args) == 3:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                args[1],
                args[2]
            )
        elif len(args) == 4:
            if isinstance(args[3], list):
                fields = util.get_embed_fields(args[3])
                await util.send_embed(
                    self.invoke_msg.channel,
                    args[0],
                    args[1],
                    args[2],
                    fields=fields
                )
            else:
                await util.send_embed(
                    self.invoke_msg.channel,
                    args[0],
                    args[1],
                    args[2],
                    args[3]
                )
        elif len(args) == 5:
            fields = util.get_embed_fields(args[3])
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                args[1],
                args[2],
                args[3],
                fields=fields
            )
        else:
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_edit_c(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_edit_c [message_id] [*args]
        ->description Edit an embed sent by the bot
        -----
        Implement pg!emsudo_edit_c, for admins to edit embeds via the bot
        """
        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return
        edit_msg = await self.invoke_msg.channel.fetch_message(
            args[0]
        )

        if len(args) == 2:
            await util.replace_embed(
                edit_msg,
                args[1],
                ""
            )
        elif len(args) == 3:
            await util.replace_embed(
                edit_msg,
                args[1],
                args[2]
            )
        elif len(args) == 4:
            await util.replace_embed(
                edit_msg,
                args[1],
                args[2],
                args[3]
            )
        elif len(args) == 5:
            if isinstance(args[4], list):
                fields = util.get_embed_fields(args[4])
                await util.replace_embed(
                    edit_msg,
                    args[1],
                    args[2],
                    args[3],
                    fields=fields
                )
            else:
                await util.replace_embed(
                    edit_msg,
                    args[1],
                    args[2],
                    args[3],
                    args[4]
                )
        elif len(args) == 6:
            fields = util.get_embed_fields(args[4])
            await util.replace_embed(
                edit_msg,
                args[1],
                args[2],
                args[3],
                args[4],
                fields=fields
            )
        else:
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo(self):
        """
        ->type More admin commands
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
            embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed,
            title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed, description=EmptyEmbed, image_url=EmptyEmbed,
            color=0xFFFFAA, fields=(), footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=None
        )

        if len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                src_channel = self.invoke_msg.author.guild.get_channel(int(self.args[0]))

                if not src_channel:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid channel id!",
                    ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[1])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.send_embed_from_dict(self.invoke_msg.channel, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
        
        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return


        if isinstance(args, dict):
            await util.send_embed_from_dict(self.invoke_msg.channel, args)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return
        
        elif isinstance(args, int):
            try:
                attachment_msg = await self.invoke_msg.channel.fetch_message(
                args
                )
            except discord.NotFound:
                await util.replace_embed(
                self.response_msg,
                "Invalid message id!",
                ""
                )
                return
            
            if not attachment_msg.attachments:
                await util.replace_embed(
                self.response_msg,
                "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                ""
                )
                return

            for attachment in attachment_msg.attachments:
                if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                    attachment_obj = attachment
                    break
            else:
                await util.replace_embed(
                self.response_msg,
                "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                ""
                )
                return
            
            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await util.send_embed_from_dict(self.invoke_msg.channel, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return
        
        elif isinstance(args, str) and not args:
            attachment_msg = self.invoke_msg

            if not attachment_msg.attachments:
                await util.replace_embed(
                self.response_msg,
                "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                ""
                )
                return

            for attachment in attachment_msg.attachments:
                if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                    attachment_obj = attachment
                    break
            else:
                await util.replace_embed(
                self.response_msg,
                "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                ""
                )
                return
            
            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await util.send_embed_from_dict(self.invoke_msg.channel, embed_dict)
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
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

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
                util_send_embed_args.update(
                    fields=util.get_embed_fields(args[4])
                )
            except TypeError:
                await util.replace_embed(
                self.response_msg,
                "Invalid format for field string!",
                ""
                )
                return

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

        await util.send_embed_2(self.invoke_msg.channel, **util_send_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_add(self):
        """
        ->type More admin commands
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

        util_add_embed_args = dict(
            embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed,
            title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed, description=EmptyEmbed, image_url=EmptyEmbed,
            color=0xFFFFAA, fields=(), footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=None
        )

        if len(self.args) == 3:
            if self.args[0].isnumeric() and self.args[1].isnumeric() and self.args[2].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(
                        self.args[0]
                    )
                except (discord.NotFound, IndexError, ValueError):
                    await util.replace_embed(
                        self.response_msg,
                        "Invalid arguments!",
                        ""
                    )
                    return
                
                src_channel = self.invoke_msg.author.guild.get_channel(int(self.args[1]))

                if not src_channel:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid source channel id!",
                    ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[2])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid source message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
            
        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(
                        self.args[0]
                    )
                except (discord.NotFound, IndexError, ValueError):
                    await util.replace_embed(
                        self.response_msg,
                        "Invalid arguments!",
                        ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[1])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
        
        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(
                args[0]
            )
        except (discord.NotFound, IndexError, ValueError):
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

        args = args[1:]
        arg_count = len(args)

        if arg_count > 0:
            if isinstance(args[0], (tuple, list)):
                if len(args[0]) == 3:
                    util_add_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                        author_icon_url=args[0][2],
                    )
                elif len(args[0]) == 2:
                    util_add_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                    )
                elif len(args[0]) == 1:
                    util_add_embed_args.update(
                        author_name=args[0][0],
                    )

            elif isinstance(args[0], dict):
                await util.replace_embed_from_dict(edit_msg, args[0])
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], int):
                try:
                    attachment_msg = await self.invoke_msg.channel.fetch_message(
                    args[0]
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return
                
                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
            
            elif isinstance(args[0], str) and not args[0]:
                attachment_msg = self.invoke_msg

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            else:
                util_add_embed_args.update(
                    author_name=args[0],
                )
        else:
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

        if arg_count > 1:
            if isinstance(args[1], (tuple, list)):
                if len(args[1]) == 3:
                    util_add_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                        thumbnail_url=args[1][2],
                    )

                elif len(args[1]) == 2:
                    util_add_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                    )

                elif len(args[1]) == 1:
                    util_add_embed_args.update(
                        title=args[1][0],
                    )

            else:
                util_add_embed_args.update(
                    title=args[1],
                )

        if arg_count > 2:
            if isinstance(args[2], (tuple, list)):
                if len(args[2]) == 2:
                    util_add_embed_args.update(
                        description=args[2][0],
                        image_url=args[2][1],
                    )

                elif len(args[2]) == 1:
                    util_add_embed_args.update(
                        description=args[2][0],
                    )

            else:
                util_add_embed_args.update(
                    description=args[2],
                )

        if arg_count > 3:
            if args[3] > -1:
                util_add_embed_args.update(
                    color=args[3],
                )

        if arg_count > 4:
            try:
                util_add_embed_args.update(
                    fields=util.get_embed_fields(args[4])
                )
            except TypeError:
                await util.replace_embed(
                self.response_msg,
                "Invalid format for field string!",
                ""
                )
                return

        if arg_count > 5:
            if isinstance(args[5], (tuple, list)):
                if len(args[5]) == 2:
                    util_add_embed_args.update(
                        footer_text=args[5][0],
                        footer_icon_url=args[5][1],
                    )

                elif len(args[5]) == 1:
                    util_add_embed_args.update(
                        footer_text=args[5][0],
                    )

            else:
                util_add_embed_args.update(
                    footer_text=args[5],
                )

        if arg_count > 6:
            util_add_embed_args.update(timestamp=args[6])

        await util.replace_embed_2(edit_msg, **util_add_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_replace(self):
        """
        ->type More admin commands
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
            embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed,
            title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed, description=EmptyEmbed, image_url=EmptyEmbed,
            color=0xFFFFAA, fields=(), footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=None
        )

        if len(self.args) == 3:
            if self.args[0].isnumeric() and self.args[1].isnumeric() and self.args[2].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(
                        self.args[0]
                    )
                except (discord.NotFound, IndexError, ValueError):
                    await util.replace_embed(
                        self.response_msg,
                        "Invalid arguments!",
                        ""
                    )
                    return
                
                src_channel = self.invoke_msg.author.guild.get_channel(int(self.args[1]))

                if not src_channel:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid source channel id!",
                    ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[2])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid source message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
        
        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(
                        self.args[0]
                    )
                except (discord.NotFound, IndexError, ValueError):
                    await util.replace_embed(
                        self.response_msg,
                        "Invalid arguments!",
                        ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[1])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
        
        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(
                args[0]
            )
        except (discord.NotFound, IndexError, ValueError):
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

        args = args[1:]
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

            elif isinstance(args[0], dict):
                await util.replace_embed_from_dict(edit_msg, args[0])
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], int):
                try:
                    attachment_msg = await self.invoke_msg.channel.fetch_message(
                    args[0]
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return
                
                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
            
            elif isinstance(args[0], str) and not args[0]:
                attachment_msg = self.invoke_msg

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.replace_embed_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            else:
                util_replace_embed_args.update(
                    author_name=args[0],
                )
        else:
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

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
                util_replace_embed_args.update(
                    fields=util.get_embed_fields(args[4])
                )
            except TypeError:
                await util.replace_embed(
                self.response_msg,
                "Invalid format for field string!",
                ""
                )
                return

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

        await util.replace_embed_2(edit_msg, **util_replace_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()
    

    async def cmd_emsudo_edit(self):
        """
        ->type More admin commands
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
            embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed,
            title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed, description=EmptyEmbed, image_url=EmptyEmbed,
            color=0xFFFFAA, fields=(), footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=None
        )

        if len(self.args) == 3:
            if self.args[0].isnumeric() and self.args[1].isnumeric() and self.args[2].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(
                        self.args[0]
                    )
                except (discord.NotFound, IndexError, ValueError):
                    await util.replace_embed(
                        self.response_msg,
                        "Invalid arguments!",
                        ""
                    )
                    return

                if not edit_msg.embeds:
                    await util.replace_embed(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message."
                    )
                    return
        
                edit_msg_embed = edit_msg.embeds[0]
                
                src_channel = self.invoke_msg.author.guild.get_channel(int(self.args[1]))

                if not src_channel:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid source channel id!",
                    ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[2])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid source message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.edit_embed_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
        
        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(
                        self.args[0]
                    )
                except (discord.NotFound, IndexError, ValueError):
                    await util.replace_embed(
                        self.response_msg,
                        "Invalid arguments!",
                        ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                if not edit_msg.embeds:
                    await util.replace_embed(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message."
                    )
                    return
        
                edit_msg_embed = edit_msg.embeds[0]

                try:
                    attachment_msg = await src_channel.fetch_message(
                        int(self.args[1])
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.edit_embed_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(
                args[0]
            )
        except (discord.NotFound, IndexError, ValueError):
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

        if not edit_msg.embeds:
            await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
            )
            return
        
        edit_msg_embed = edit_msg.embeds[0]

        args = args[1:]
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

            elif isinstance(args[0], dict):
                await util.edit_embed_from_dict(edit_msg, edit_msg_embed, args[0])
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], int):
                try:
                    attachment_msg = await self.invoke_msg.channel.fetch_message(
                    args[0]
                    )
                except discord.NotFound:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid message id!",
                    ""
                    )
                    return
                
                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.edit_embed_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return
            
            elif isinstance(args[0], str) and not args[0]:
                attachment_msg = self.invoke_msg

                if not attachment_msg.attachments:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if attachment.filename.endswith(".txt") or attachment.filename.endswith(".py"):
                        attachment_obj = attachment
                        break
                else:
                    await util.replace_embed(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    ""
                    )
                    return
                
                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await util.edit_embed_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            else:
                util_edit_embed_args.update(
                    author_name=args[0],
                )
        else:
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                ""
            )
            return

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
            if args[3] > -1:
                util_edit_embed_args.update(
                    color=args[3],
                )

        if arg_count > 4:
            try:
                util_edit_embed_args.update(
                    fields=util.get_embed_fields(args[4])
                )
            except TypeError:
                await util.replace_embed(
                self.response_msg,
                "Invalid format for field string!",
                ""
                )
                return

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

        await util.edit_embed_2(edit_msg, edit_msg_embed, **util_edit_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()



    async def cmd_emsudo_replace_field(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_replace [*args]
        ->description Replace an embed field through the bot
        ->extended description
        ```
        pg!emsudo_replace_field ({target_message_id}, {index}, {field_string})
        pg!emsudo_replace_field ({target_message_id}, {index}, {field_dict})
        ```
        Replace an embed field at the given index in the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_replace_field, for admins to update fields of embeds sent via the bot
        """

        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return
        
        arg_count = len(args)
        field_list = None
        field_dict = None
            
        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                ""
                )
                return
            
            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(
                    edit_msg_id
                )
            except discord.NotFound:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
                )
                return
            
            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                ""
                )
                return
            

            if isinstance(args[2], dict):
                field_dict = args[2]

            elif isinstance(args[2], str):
                try:
                    field_list = util.get_embed_fields((args[2],))[0]
                except (TypeError, IndexError):
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid format for field string!",
                    ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {"name": field_list[0], "value": field_list[1], "inline": field_list[2]}

                elif not field_list:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid format for field string!",
                    ""
                    )
                    return
            else:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                ""
                )
                return
        
        else:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
            ""
            )
            return

        try:
            await util.edit_embed_field_from_dict(edit_msg, edit_msg_embed, field_dict, field_index)
        except IndexError:
            await util.replace_embed(
            self.response_msg,
            "Invalid field index!",
            ""
            )
            return
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_insert_field(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_insert_field [*args]
        ->description Insert an embed field through the bot
        ->extended description
        ```
        pg!emsudo_insert_field ({target_message_id}, {index}, {field_string})
        pg!emsudo_insert_field ({target_message_id}, {index}, {field_dict})
        ```
        Insert an embed field at the given index into the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_insert_field, for admins to insert fields into embeds sent via the bot
        """

        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return
        
        arg_count = len(args)
        field_list = None
        field_dict = None
            
        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                ""
                )
                return
            
            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(
                    edit_msg_id
                )
            except discord.NotFound:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
                )
                return
            
            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                ""
                )
                return
            

            if isinstance(args[2], dict):
                field_dict = args[2]

            elif isinstance(args[2], str):
                try:
                    field_list = util.get_embed_fields((args[2],))[0]
                except (TypeError, IndexError):
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid format for field string!",
                    ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {"name": field_list[0], "value": field_list[1], "inline": field_list[2]}

                elif not field_list:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid format for field string!",
                    ""
                    )
                    return
            else:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                ""
                )
                return
        
        else:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
            ""
            )
            return

        try:
            await util.insert_embed_field_from_dict(edit_msg, edit_msg_embed, field_dict, field_index)
        except IndexError:
            await util.replace_embed(
            self.response_msg,
            "Invalid field index!",
            ""
            )
            return
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_insert_fields(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_insert_fields [*args]
        ->description Insert n embed fields through the bot
        ->extended description
        ```
        pg!emsudo_insert_fields ({target_message_id}, {index}, {field_string_tuple})
        pg!emsudo_insert_fields ({target_message_id}, {index}, {field_dict_tuple})
        pg!emsudo_insert_fields ({target_message_id}, {index}, {field_string_or_dict_tuple})
        ```
        Insert multiple embed fields at the given index into the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_insert_fields, for admins to insert multiple fields to embeds sent via the bot
        """

        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return
        
        arg_count = len(args)

        field_dicts_list = []
            
        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                ""
                )
                return
            
            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(
                    edit_msg_id
                )
            except discord.NotFound:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
                )
                return
            
            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                ""
                )
                return

            if isinstance(args[2], (list, tuple)):
                for i, data in enumerate(args[2]):
                    if isinstance(data, dict):
                        field_dicts_list.append(data)

                    elif isinstance(data, str):
                        try:
                            data_list = util.get_embed_fields((data,))[0]
                        except (TypeError, IndexError):
                            await util.replace_embed(
                            self.response_msg,
                            "Invalid format for field string!",
                            ""
                            )
                            return

                        if len(data_list) == 3:
                            data_dict = {"name": data_list[0], "value": data_list[1], "inline": data_list[2]}

                        elif not data_list:
                            await util.replace_embed(
                            self.response_msg,
                            "Invalid format for field string!",
                            ""
                            )
                            return

                        field_dicts_list.append(data_dict)
                    else:
                        await util.replace_embed(
                        self.response_msg,
                        f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                        ""
                        )
                        return

            else:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                ""
                )
                return
        
        else:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
            ""
            )
            return

        for field_dict in reversed(field_dicts_list):
            await util.insert_embed_field_from_dict(edit_msg, edit_msg_embed, field_dict, field_index)
        
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_add_field(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_add_field [*args]
        ->description Add an embed field through the bot
        ->extended description
        ```
        pg!emsudo_add_field ({target_message_id}, {field_string})
        pg!emsudo_add_field ({target_message_id}, {field_dict})
        ```
        Add an embed field to the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_add_field, for admins to add fields to embeds sent via the bot
        """

        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return
        
        arg_count = len(args)
        field_list = None
        field_dict = None
            
        if arg_count == 2:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a dictionary or a string is required.",
                ""
                )
                return
            
            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(
                    edit_msg_id
                )
            except discord.NotFound:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
                )
                return
            
            edit_msg_embed = edit_msg.embeds[0]

            if isinstance(args[1], dict):
                field_dict = args[1]

            elif isinstance(args[1], str):
                try:
                    field_list = util.get_embed_fields((args[1],))[0]
                except (TypeError, IndexError):
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid format for field string!",
                    ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {"name": field_list[0], "value": field_list[1], "inline": field_list[2]}

                elif not field_list:
                    await util.replace_embed(
                    self.response_msg,
                    "Invalid format for field string!",
                    ""
                    )
                    return
            else:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a dictionary or a string is required.",
                ""
                )
                return
        
        else:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by a dictionary or a string is required.",
            ""
            )
            return

        await util.add_embed_field_from_dict(edit_msg, edit_msg_embed, field_dict)
        
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_add_fields(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_add_fields [*args]
        ->description Add n embed fields through the bot
        ->extended description
        ```
        pg!emsudo_add_fields ({target_message_id}, {field_string_tuple})
        pg!emsudo_add_fields ({target_message_id}, {field_dict_tuple})
        pg!emsudo_add_fields ({target_message_id}, {field_string_or_dict_tuple})
        ```
        Add multiple embed fields to the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_add_fields, for admins to add multiple fields to embeds sent via the bot
        """
        

        try:
            args = eval(self.string)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await util.replace_embed(
                self.response_msg,
                "Invalid arguments!",
                f"```\n{''.join(tbs)}```"
            )
            return
        
        arg_count = len(args)

        field_dicts_list = []
            
        if arg_count == 2:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                ""
                )
                return
            
            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(
                    edit_msg_id
                )
            except discord.NotFound:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
                )
                return
            
            edit_msg_embed = edit_msg.embeds[0]

            if isinstance(args[1], (list, tuple)):
                for i, data in enumerate(args[1]):
                    if isinstance(data, dict):
                        field_dicts_list.append(data)

                    elif isinstance(data, str):
                        try:
                            data_list = util.get_embed_fields((data,))[0]
                        except (TypeError, IndexError):
                            await util.replace_embed(
                            self.response_msg,
                            "Invalid format for field string!",
                            ""
                            )
                            return

                        if len(data_list) == 3:
                            data_dict = {"name": data_list[0], "value": data_list[1], "inline": data_list[2]}

                        elif not data_list:
                            await util.replace_embed(
                            self.response_msg,
                            "Invalid format for field string!",
                            ""
                            )
                            return

                        field_dicts_list.append(data_dict)
                    else:
                        await util.replace_embed(
                        self.response_msg,
                        f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                        ""
                        )
                        return

            else:
                await util.replace_embed(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                ""
                )
                return
        
        else:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
            ""
            )
            return

        for field_dict in field_dicts_list:
            await util.add_embed_field_from_dict(edit_msg, edit_msg_embed, field_dict)
        
        await self.response_msg.delete()
        await self.invoke_msg.delete()
    

    async def cmd_emsudo_remove_field(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_remove_field [*args]
        ->description Remove an embed field through the bot
        ->extended description
        ```
        pg!emsudo_remove_field {target_message_id} {index}
        ```
        Remove an embed field at the given index of the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_remove_field, for admins to remove fields in embeds sent via the bot
        """

        self.check_args(2)
            
        try:
            edit_msg_id = int(self.args[0])
        except ValueError:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by an index is required.",
            ""
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(
                edit_msg_id
            )
        except discord.NotFound:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "Invalid message id!"
            )
            return

        if not edit_msg.embeds:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "No embed data found in message."
            )
            return
        
        edit_msg_embed = edit_msg.embeds[0]

        try:
            field_index = int(self.args[1])
        except ValueError:
            await util.replace_embed(
            self.response_msg,
            "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
            ""
            )
            return
            
        try:
            await util.remove_embed_field(edit_msg, edit_msg_embed, field_index)
        except IndexError:
            await util.replace_embed(
            self.response_msg,
            "Invalid field index!",
            ""
            )
            return
        
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_clear_fields(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_clear_fields [*args]
        ->description Remove all embed fields through the bot
        ->extended description
        ```
        pg!emsudo_clear_fields {target_message_id}
        ```
        Remove all embed fields of the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_clear_fields, for admins to remove fields in embeds sent via the bot
        """

        self.check_args(1)

        try:
            edit_msg_id = int(self.args[0])
        except ValueError:
            await util.replace_embed(
            self.response_msg,
            "Invalid argument! A valid integer message id is required.",
            ""
            )
            return
        
        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(
                edit_msg_id
            )
        except discord.NotFound:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "Invalid message id!"
            )
            return

        if not edit_msg.embeds:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "No embed data found in message."
            )
            return
        
        edit_msg_embed = edit_msg.embeds[0]

        await util.clear_embed_fields(edit_msg, edit_msg_embed)
        await self.response_msg.delete()
        await self.invoke_msg.delete()


    async def cmd_emsudo_get(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_get [*args]
        ->description Remove all embed fields through the bot
        ->extended description
        ```
        pg!emsudo_get {message_id}
        pg!emsudo_get {channel_id} {message_id}
        ```
        Get the contents of the embed of a message from the given arguments and send it as another message (with a `.txt` file attachment containing the embed data as a Python dictionary) to the channel where this command was invoked.
        -----
        Implement pg!emsudo_get, to return the embed of a message as a dictionary in a text file.
        """
        self.check_args(1, maxarg=2)

        src_msg_id = None
        src_msg = None
        src_channel_id = self.invoke_msg.channel.id
        src_channel = self.invoke_msg.channel

        embed_dicts = None

        if len(self.args) == 2:
            try:
                src_channel_id = int(self.args[0])
                src_msg_id = int(self.args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message and/or channel id(s)!"
                )
                return
            
            src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
            if src_channel is None:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid channel id!"
                )
                return
        else:
            try:
                src_msg_id = int(self.args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return
        try:
            src_msg = await src_channel.fetch_message(src_msg_id)
        except discord.NotFound:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "Invalid message id!"
            )
            return
        
        embed_dicts = tuple(emb.to_dict() for emb in src_msg.embeds)
    
        if not embed_dicts:
            await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
            )
            return
        
        with open("embeddata.txt", "w", encoding="utf-8") as embed_txt:
            embed_txt.write("\n".join(repr( {k:ed[k] for k in reversed(ed.keys())} ) for ed in embed_dicts))

        os.system("black -q embeddata.txt")

        await self.response_msg.channel.send(
            content="".join((
                "__Embed data:__\nTitle: **{0}** \n*(Source: ".format(embed_dicts[0].get("title", "N/A")),
                f"<https://discord.com/channels/{src_msg.author.guild.id}/{src_channel.id}/{src_msg.id}>)*"
            )),
            file=discord.File("embeddata.txt")
        )
        await self.response_msg.delete()
    

    async def cmd_emsudo_clone(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_clone [*args]
        ->description Remove all embed fields through the bot
        ->extended description
        ```
        pg!emsudo_clone {message_id}
        pg!emsudo_clone {channel_id} {message_id}
        ```
        Get a message from the given arguments and send it as another message (only containing its embed) to the channel where this command was invoked.
        -----
        Implement pg!_emsudo_clone, to get the embed of a message and send it.
        """
        self.check_args(1, maxarg=2)

        src_msg_id = None
        src_msg = None
        src_channel_id = self.invoke_msg.channel.id
        src_channel = self.invoke_msg.channel

        if len(self.args) == 2:
            try:
                src_channel_id = int(self.args[0])
                src_msg_id = int(self.args[1])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message and/or channel id(s)!"
                )
                return
            
            src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
            if src_channel is None:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid channel id!"
                )
                return
        else:
            try:
                src_msg_id = int(self.args[0])
            except ValueError:
                await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
                )
                return
        try:
            src_msg = await src_channel.fetch_message(src_msg_id)
        except discord.NotFound:
            await util.replace_embed(
            self.response_msg,
            "Cannot execute command:",
            "Invalid message id!"
            )
            return
        
        if not src_msg.embeds:
            await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message."
            )
            return
        
        for embed in src_msg.embeds:
            await self.response_msg.channel.send(embed=embed)
        
        await self.response_msg.delete()

    async def cmd_archive(self):
        """
        ->type Admin commands
        ->signature pg!archive [*args]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """
        self.check_args(3)
        origin = int(util.filter_id(self.args[0]))
        quantity = int(self.args[1])
        destination = int(util.filter_id(self.args[2]))

        origin_channel = None
        destination_channel = None

        for channel in common.bot.get_all_channels():
            if channel.id == origin:
                origin_channel = channel
            if channel.id == destination:
                destination_channel = channel

        if not origin_channel:
            await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid origin channel!"
            )
            return
        elif not destination_channel:
            await util.replace_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid destination channel!"
            )
            return

        messages = await origin_channel.history(limit=quantity).flatten()
        messages.reverse()
        message_list = await util.format_archive_messages(messages)

        archive_str = f"+{'=' * 40}+\n" + \
            f"+{'=' * 40}+\n".join(message_list) + f"+{'=' * 40}+\n"
        archive_list = util.split_long_message(archive_str)

        for message in archive_list:
            await destination_channel.send(message)

        await util.replace_embed(
            self.response_msg,
            f"Successfully archived {len(messages)} message(s)!",
            ""
        )
