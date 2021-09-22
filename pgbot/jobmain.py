"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file includes job classes that run at bot startup.
"""
import datetime
import discord

from pgbot import common
from pgbot.jobs import core
from pgbot.jobs.core import events
from pgbot.jobs.core import serializers as serials
from pgbot.jobs.utils import messaging
from pgbot.utils import embed_utils


class MessagingTest1(core.ClientEventJob):
    EVENT_TYPES = (events.OnMessageBase,)

    async def on_init(self):
        if "target_channel" not in self.DATA:
            self.DATA.target_channel = common.guild.get_channel(822650791303053342)
            self.DATA.response_count = 0
            self.DATA.interval_job_test = None

    async def on_run(self, event: events.OnMessageBase, *args, **kwargs):
        if isinstance(event, events.OnMessage):
            if event.message.channel == self.DATA.target_channel:
                event: events.OnMessage
                if event.message.content.lower().startswith("hi"):
                    await self.DATA.target_channel.send(
                        f"Hi, {event.message.author.mention}"
                    )

                    self.DATA.response_count += 1
                    if self.DATA.response_count == 3:
                        self.DATA.interval_job_test = IntervalJobTest()
                        self.manager.add_job(self.DATA.interval_job_test)

                elif (
                    event.message.content.lower().startswith(("shut up", "shutup"))
                    and self.DATA.response_count >= 3
                ):
                    self.DATA.interval_job_test.kill()
                    await self.DATA.target_channel.send(
                        f"Sorry, {event.message.author.mention}, I won't annoy you anymore, {event.message.author.mention}"
                    )
                    self.kill()

        elif isinstance(event, events.OnMessageEdit):
            event: events.OnMessageEdit
            if event.before.channel == self.DATA.target_channel:
                await self.DATA.target_channel.send(
                    f"Hi, {event.before.author.mention}, did you just change this message to:",
                    reference=event.before,
                )
                await embed_utils.send(
                    self.DATA.target_channel,
                    title="...this?",
                    description=event.after.content,
                )

        elif isinstance(event, events.OnMessageDelete):
            event: events.OnMessageDelete
            if event.message.channel == self.DATA.target_channel:
                await self.DATA.target_channel.send(
                    f"Hi, {event.message.author.mention}, did you just delete:"
                )
                await embed_utils.send(
                    self.DATA.target_channel,
                    title="...this?",
                    description=event.message.content,
                )


class IntervalJobTest(core.IntervalJob):
    default_seconds = 10

    async def on_init(self):
        if "target_channel" not in self.DATA:
            self.DATA.target_channel = common.guild.get_channel(822650791303053342)
            self.DATA.introduced = False

    async def on_run(self, *args, **kwargs):
        if not self.DATA.introduced:
            await self.DATA.target_channel.send("Hello everyone!")
            self.DATA.introduced = True
        else:
            await self.DATA.target_channel.send("*Are you annoyed yet?*")


class MessagingTest2(core.ClientEventJob):
    EVENT_TYPES = (events.OnMessage,)

    def __init__(self, target_channel: discord.TextChannel):
        super().__init__()
        self.DATA.target_channel = target_channel

    async def on_init(self):
        if "target_channel" not in self.DATA:
            self.DATA.target_channel = common.guild.get_channel(822650791303053342)

    def check_event(self, event: events.ClientEvent):
        return event.message.channel.id == self.DATA.target_channel.id

    async def on_run(self, event: events.OnMessage, *args, **kwargs):
        if event.message.content.lower().startswith("hi"):
            await self.DATA.target_channel.send("Hi, what's your name?")

            author = event.message.author
            user_name = None

            check = (
                lambda x: x.message.author == author
                and x.message.channel == self.DATA.target_channel
                and x.message.content
            )

            name_event = await self.wait_for_event(events.OnMessage, check=check)
            user_name = name_event.message.content

            await self.DATA.target_channel.send(f"Hi, {user_name}")


class MessageTestSpawner(core.OneTimeJob):
    async def on_run(self):
        for job in (
            MessagingTest2(target_channel=common.guild.get_channel(822650791303053342)),
            MessagingTest2(target_channel=common.guild.get_channel(841726972841558056)),
            MessagingTest2(target_channel=common.guild.get_channel(844492573912465408)),
            MessagingTest2(target_channel=common.guild.get_channel(849259216195420170)),
            MessagingTest2(target_channel=common.guild.get_channel(844492623636725820)),
        ):
            await job.initialize()

            self.manager.add_job(job)


class Main(core.OneTimeJob):
    async def on_run(self):
        self.manager.add_jobs(
            await core.DelayJob(
                10.0,
                messaging.MessageSend(
                    channel=822650791303053342, content="This will only happen once."
                ),
            ).as_initialized(),
            await MessageTestSpawner().as_initialized(),
        )

        self.manager.schedule_job(
            messaging.MessageSend,
            timestamp=datetime.datetime.now(),
            recur_interval=datetime.timedelta(seconds=10),
            max_recurrences=2,
            job_kwargs=dict(
                channel=822650791303053342,
                content="This will occur every 10 seconds, but only 2 times.",
            ),
        )

        self.manager.schedule_job(
            messaging.MessageSend,
            timestamp=datetime.datetime.now() + datetime.timedelta(seconds=10),
            job_kwargs=dict(
                channel=841726972841558056,
                content="Say 'I am cool.'",
            ),
        )

        msg_event: events.OnMessage = await self.manager.wait_for_client_event(
            events.OnMessage,
            check=(
                lambda x: x.message.channel.id == 841726972841558056
                and x.message.content == "I am cool."
            ),
        )

        self.manager.schedule_job(
            messaging.ReactionAdd,
            timestamp=datetime.datetime.now(),
            job_kwargs=dict(
                channel=None,
                message=serials.MessageSerial(msg_event.message),
                emoji=853327268474126356,
            ),
        )


__all__ = [
    "Main",
]
