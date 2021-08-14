"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file includes task classes that run at bot startup.
"""

import discord

from pgbot import common
from pgbot.tasks import events, core
from pgbot.utils import embed_utils


class MessagingTest1(core.ClientEventTask):
    EVENT_TYPES = (events.OnMessageBase,)

    async def before_run(self):
        if "target_channel" not in self.data:
            self.data.target_channel = common.guild.get_channel(822650791303053342)
            self.data.response_count = 0
            self.data.interval_task_test = None

    async def run(self, event: events.OnMessageBase, *args, **kwargs):
        if isinstance(event, events.OnMessage):
            if event.message.channel == self.data.target_channel:
                event: events.OnMessage
                if event.message.content.lower().startswith("hi"):
                    await self.data.target_channel.send(
                        f"Hi, {event.message.author.mention}"
                    )

                    self.data.response_count += 1
                    if self.data.response_count == 3:
                        self.data.interval_task_test = IntervalTaskTest()
                        self.manager.add_task(self.data.interval_task_test)

                elif (
                    event.message.content.lower().startswith(("shut up", "shutup"))
                    and self.data.response_count >= 3
                ):
                    self.data.interval_task_test.kill()
                    await self.data.target_channel.send(
                        f"Sorry, {event.message.author.mention}, I won't annoy you anymore, {event.message.author.mention}"
                    )
                    self.kill()

        elif isinstance(event, events.OnMessageEdit):
            event: events.OnMessageEdit
            if event.before.channel == self.data.target_channel:
                await self.data.target_channel.send(
                    f"Hi, {event.before.author.mention}, did you just change this message to:",
                    reference=event.before,
                )
                await embed_utils.send(
                    self.data.target_channel,
                    title="...this?",
                    description=event.after.content,
                )

        elif isinstance(event, events.OnMessageDelete):
            event: events.OnMessageDelete
            if event.message.channel == self.data.target_channel:
                await self.data.target_channel.send(
                    f"Hi, {event.message.author.mention}, did you just delete:"
                )
                await embed_utils.send(
                    self.data.target_channel,
                    title="...this?",
                    description=event.message.content,
                )


class IntervalTaskTest(core.IntervalTask):
    default_seconds = 10

    async def before_run(self):
        if "target_channel" not in self.data:
            self.data.target_channel = common.guild.get_channel(822650791303053342)
            self.data.introduced = False

    async def run(self, *args, **kwargs):
        if not self.data.introduced:
            await self.data.target_channel.send("Hello everyone!")
            self.data.introduced = True
        else:
            await self.data.target_channel.send("*Are you annoyed yet?*")


class MessagingTest2(core.ClientEventTask):
    EVENT_TYPES = (events.OnMessage,)

    async def before_run(self):
        if "target_channel" not in self.data:
            self.data.target_channel = common.guild.get_channel(822650791303053342)

    async def run(self, event: events.OnMessage, *args, **kwargs):
        if event.message.channel == self.data.target_channel:
            if event.message.content.lower().startswith("hi"):
                await self.data.target_channel.send("Hi, what's your name?")

                author = event.message.author
                user_name = None

                check = (
                    lambda x: x.message.author == author
                    and x.message.channel == self.data.target_channel
                    and x.message.content
                )

                while user_name is None:
                    name_event = await self.wait_for(
                        self.manager.wait_for_client_event(
                            events.OnMessage, check=check
                        )
                    )
                    user_name = name_event.message.content

                await self.data.target_channel.send(f"Hi, {user_name}")


class MessageTestSpawner(core.IntervalTask):
    async def run(self):
        self.manager.add_tasks(
            MessagingTest2(
                data=core.TaskNamespace(
                    target_channel=common.guild.get_channel(822650791303053342)
                )
            ),
            MessagingTest2(
                data=core.TaskNamespace(
                    target_channel=common.guild.get_channel(841726972841558056)
                )
            ),
            MessagingTest2(
                data=core.TaskNamespace(
                    target_channel=common.guild.get_channel(844492573912465408)
                )
            ),
            MessagingTest2(
                data=core.TaskNamespace(
                    target_channel=common.guild.get_channel(849259216195420170)
                )
            ),
            MessagingTest2(
                data=core.TaskNamespace(
                    target_channel=common.guild.get_channel(844492623636725820)
                )
            ),
        )
        self.kill()


EXPORTS = (MessageTestSpawner(),)
