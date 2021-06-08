"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the "help" commands of the bot
"""

from __future__ import annotations

import os
import re
import time
from typing import Optional

import discord
import pygame

from pgbot import common, db
from pgbot.commands.base import BaseCommand, BotException, String, no_dm
from pgbot.commands.utils import clock, docs, help
from pgbot.utils import utils, embed_utils


class HelpCommand(BaseCommand):
    """Base class to handle 'help' commands of the bot."""

    async def cmd_rules(self, *rules: int):
        """
        ->type Get help
        ->signature pg!rules [*rule_numbers]
        ->description Get rules of the server
        -----
        Implement pg!rules, to get rules of the server
        """
        if not rules:
            raise BotException("Please enter rule number(s)", "")

        if common.GENERIC:
            raise BotException(
                "Cannot execute command!",
                "This command cannot be exected when the bot is on generic mode",
            )

        fields = []
        for rule in sorted(set(rules)):
            if 0 < rule <= len(common.ServerConstants.RULES):
                msg = await common.rules_channel.fetch_message(
                    common.ServerConstants.RULES[rule - 1]
                )
                value = msg.content

            elif rule == 42:
                value = (
                    "*Shhhhh*, you have found an unwritten rule!\n"
                    "Click [here](https://bitly.com/98K8eH) to gain the most "
                    "secret and ultimate info!"
                )

            else:
                value = "Does not exist lol"

            fields.append(
                {
                    "name": f"__Rule number {rule}:__",
                    "value": value,
                    "inline": False,
                }
            )

        if len(rules) == 1:
            await embed_utils.replace_2(
                self.response_msg,
                author_name="Pygame Community",
                author_icon_url=common.GUILD_ICON,
                title=fields[0]["name"],
                description=fields[0]["value"][:2048],
                color=0x228B22,
            )
        else:
            for field in fields:
                field["value"] = field["value"][:1024]

            await embed_utils.replace_2(
                self.response_msg,
                author_name="Pygame Community",
                author_icon_url=common.GUILD_ICON,
                title="Rules",
                fields=fields,
                color=0x228B22,
            )

    async def cmd_clock(
        self,
        action: str = "",
        timezone: float = 0,
        color: Optional[pygame.Color] = None,
        *,
        _member: Optional[discord.Member] = None,
    ):
        """
        ->type Get help
        ->signature pg!clock
        ->description 24 Hour Clock showing <@&778205389942030377> s who are available to help
        -> Extended description
        People on the clock can run the clock with more arguments, to update their data.
        `pg!clock update [timezone in hours] [color as hex string]`
        `timezone` is float offset from GMT in hours.
        `color` optional color argument, that shows up on the clock.
        Note that you might not always display with that colour.
        This happens if more than one person are on the same timezone
        Use `pg!clock remove` to remove yourself from the clock
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        db_obj = db.DiscordDB("clock")

        timezones = db_obj.get({})
        if action:
            if _member is None:
                member = self.author
                if member.id not in timezones:
                    raise BotException(
                        "Cannot update clock!",
                        "You cannot run clock update commands because you are "
                        + "not on the clock",
                    )
            else:
                member = _member

            if action == "update":
                if abs(timezone) > 12:
                    raise BotException(
                        "Failed to update clock!", "Timezone offset out of range"
                    )

                if member.id in timezones:
                    timezones[member.id][0] = timezone
                    if color is not None:
                        timezones[member.id][1] = utils.color_to_rgb_int(color)
                else:
                    if color is None:
                        raise BotException(
                            "Failed to update clock!",
                            "Color argument is required when adding new people",
                        )
                    timezones[member.id] = [timezone, utils.color_to_rgb_int(color)]

                # sort timezones dict after an update operation
                timezones = dict(sorted(timezones.items(), key=lambda x: x[1][0]))

            elif action == "remove":
                try:
                    timezones.pop(member.id)
                except KeyError:
                    raise BotException(
                        "Failed to update clock!",
                        "Cannot remove non-existing person from clock",
                    )

            else:
                raise BotException(
                    "Failed to update clock!", f"Invalid action specifier {action}"
                )

            db_obj.write(timezones)

        t = time.time()

        # needed for typecheckers to know that self.guild cannot be none
        if self.guild is None:
            return

        pygame.image.save(
            await clock.user_clock(t, timezones, self.guild), f"temp{t}.png"
        )
        common.cmd_logs[self.invoke_msg.id] = await self.channel.send(
            file=discord.File(f"temp{t}.png")
        )
        os.remove(f"temp{t}.png")

        await self.response_msg.delete()

    @no_dm
    async def cmd_doc(self, name: str):
        """
        ->type Get help
        ->signature pg!doc <object name>
        ->description Look up the docstring of a Python/Pygame object, e.g str or pygame.Rect
        -----
        Implement pg!doc, to view documentation
        """
        # needed for typecheckers to know that self.author is a member
        if isinstance(self.author, discord.User):
            return

        await docs.put_doc(name, self.response_msg, self.author, self.page)

    @no_dm
    async def cmd_help(self, *names: str):
        """
        ->type Get help
        ->signature pg!help [command]
        ->description Ask me for help
        ->example command pg!help help
        -----
        Implement pg!help, to display a help message
        """

        # needed for typecheckers to know that self.author is a member
        if isinstance(self.author, discord.User):
            return

        await help.send_help_message(
            self.response_msg,
            self.author,
            names,
            self.cmds_and_funcs,
            self.groups,
            self.page,
        )

    @no_dm
    async def cmd_resources(
        self,
        limit: Optional[int] = None,
        filter_tag: Optional[String] = None,
        filter_member: Optional[discord.Member] = None,
        oldest_first: bool = False,
    ):
        """
        ->type Get help
        ->signature pg!resources [limit] [filter_tag] [filter_member] [oldest_first]
        ->description Browse through resources.
        ->extended description
        pg!resources takes in additional arguments, though they are optional.
        `oldest_first`: Set oldest_first to True to browse through the oldest resources
        `limit=[num]`: Limits the number of resources to the number
        `filter_tag=[tag]`: Includes only the resources with that tag(s)
        `filter_member=[member]`: Includes only the resources posted by that user
        ->example command pg!resources limit=5 oldest_first=True filter_tag="python, gamedev" filter_member=444116866944991236
        """

        # needed for typecheckers to know that self.author is a member
        if isinstance(self.author, discord.User):
            return

        # NOTE: It is hardcoded in the bot to remove some messages in resource-entries,
        #       if you want to remove more, add the ID to the list below
        msgs_to_filter = {
            817137523905527889,
            810942002114986045,
            810942043488256060,
        }

        if common.GENERIC:
            raise BotException(
                "Cannot execute command!",
                "This command cannot be exected when the bot is on generic mode",
            )

        def process_tag(tag: str):
            for to_replace in ("tag_", "tag-", "<", ">", "`"):
                tag = tag.replace(to_replace, "")
            return tag.title()

        def filter_func(x):
            return x.id != msg_to_filter

        resource_entries_channel = common.entry_channels["resource"]

        # Retrieves all messages inside resource entries channel
        msgs = await resource_entries_channel.history(
            oldest_first=oldest_first
        ).flatten()

        # Filters any messages that have the same ID as the ones provided
        # in msgs_to_filter
        for msg_to_filter in msgs_to_filter:
            msgs = list(filter(filter_func, msgs))

        if filter_tag:
            # Filter messages based on tag
            for tag in map(str.strip, filter_tag.string.split(",")):
                tag = tag.lower()
                msgs = list(
                    filter(
                        lambda x: f"tag_{tag}" in x.content.lower()
                        or f"tag-<{tag}>" in x.content.lower(),
                        msgs,
                    )
                )

        if filter_member:
            msgs = list(filter(lambda x: x.author.id == filter_member.id, msgs))

        if limit is not None:
            # Uses list slicing instead of TextChannel.history's limit param
            # to include all param specified messages
            msgs = msgs[:limit]

        tags = {}
        old_tags = {}
        links = {}
        for msg in msgs:
            # Stores the tags (tag_{Your tag here}), old tags (tag-<{your tag here}>),
            # And links inside separate dicts with regex
            links[msg.id] = [
                match.group()
                for match in re.finditer("http[s]?://(www.)?[^ \n]+", msg.content)
            ]
            tags[msg.id] = [
                f"`{process_tag(match.group())}` "
                for match in re.finditer("tag_.+", msg.content.lower())
            ]
            old_tags[msg.id] = [
                f"`{process_tag(match.group())}` "
                for match in re.finditer("tag-<.+>", msg.content.lower())
            ]

        pages = []
        copy_msgs = msgs[:]
        i = 1
        while msgs:
            # Constructs embeds based on messages, and store them in pages to be used in the paginator
            top_msg = msgs[:6]
            if len(copy_msgs) > 1:
                title = (
                    f"Retrieved {len(copy_msgs)} entries in "
                    f"#{resource_entries_channel.name}"
                )
            else:
                title = (
                    f"Retrieved {len(copy_msgs)} entry in "
                    f"#{resource_entries_channel.name}"
                )
            current_embed = discord.Embed(title=title)

            # Cycles through the top 6 messages
            for msg in top_msg:
                try:
                    name = msg.content.split("\n")[1].strip().replace("**", "")
                    if not name:
                        continue

                    field_name = f"{i}. {name}, posted by {msg.author.display_name}"
                    # If the field name is > 256 (discord limit), shorten it with list slicing
                    field_name = f"{field_name[:253]}..."

                    value = msg.content.split(name)[1].removeprefix("**").strip()
                    # If the preview of the resources > 80, shorten it with list slicing
                    value = f"{value[:80]}..."
                    value += f"\n\nLinks: **[Message]({msg.jump_url})**"

                    for j, link in enumerate(links[msg.id], 1):
                        value += f", [Link {j}]({link})"

                    value += "\nTags: "
                    if tags[msg.id]:
                        value += "".join(tags[msg.id]).removesuffix(",")
                    elif old_tags[msg.id]:
                        value += "".join(old_tags[msg.id]).removesuffix(",")
                    else:
                        value += "None"

                    current_embed.add_field(
                        name=field_name,
                        value=f"{value}\n{common.ZERO_SPACE}",
                        inline=True,
                    )
                    i += 1
                except IndexError:
                    # Suppresses IndexError because of rare bug
                    pass

            pages.append(current_embed)
            msgs = msgs[6:]

        if len(pages) == 0:
            raise BotException(
                f"Retrieved 0 entries in #{resource_entries_channel.name}",
                "There are no results of resources with those parameters. Please try again.",
            )

        # Creates a paginator for the caller to use
        page_embed = embed_utils.PagedEmbed(
            self.response_msg,
            pages,
            self.author,
            self.cmd_str,
            self.page,
        )

        await page_embed.mainloop()
