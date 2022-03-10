"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file includes job classes that run at bot startup.
"""
import asyncio
import datetime
from typing import Type
import discord
from time import perf_counter

from pgbot import common, db, serializers
from pgbot.jobs import core
from pgbot.jobs.core import events, PERMISSION_LEVELS
from pgbot.jobs.utils import messaging
from pgbot.utils import embed_utils


class MessagingTest1(core.ClientEventJob):
    EVENT_TYPES = (events.OnMessageBase,)

    def __init__(self, target_channel: discord.TextChannel):
        super().__init__()
        self.data.target_channel = target_channel

    async def on_init(self):
        if "target_channel" not in self.data:
            self.data.target_channel = common.guild.get_channel(822650791303053342)
            self.data.response_count = 0
            self.data.interval_job_test = None

    async def on_run(self, event: events.OnMessageBase, *args, **kwargs):
        if isinstance(event, events.OnMessage):
            if event.message.channel == self.data.target_channel:
                event: events.OnMessage
                if event.message.content.lower().startswith(("hi", "hello")):
                    await self.data.target_channel.send(
                        f"Hi, {event.message.author.mention}"
                    )

                    self.data.response_count += 1
                    if self.data.response_count == 3:
                        self.data.interval_job_test = self.manager.create_job(
                            IntervalJobTest
                        )
                        await self.manager.register_job(self.data.interval_job_test)

                elif (
                    event.message.content.lower().startswith(("shut"))
                    and self.data.response_count >= 3
                ):
                    self.manager.kill_job(self.data.interval_job_test)
                    await self.data.target_channel.send(
                        f"Sorry, {event.message.author.mention}, I won't annoy you anymore, {event.message.author.mention}"
                    )
                    self.STOP_LOOP()

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

    async def on_stop(self, *args, **kwargs):
        self.COMPLETE()


class IntervalJobTest(core.IntervalJob):
    default_seconds = 10

    async def on_init(self):
        if "target_channel" not in self.data:
            self.data.target_channel = common.guild.get_channel(822650791303053342)
            self.data.introduced = False

    async def on_run(self, *args, **kwargs):
        if not self.data.introduced:
            await self.data.target_channel.send("Hello everyone!")
            self.data.introduced = True
        else:
            await self.data.target_channel.send("*Are you annoyed yet?*")


class MessagingTest2(core.ClientEventJob):
    EVENT_TYPES = (events.OnMessage,)


    class TestNamespace(core.JobNamespace):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.target_channel: discord.TextChannel = None

    NAMESPACE_CLASS = TestNamespace

    def __init__(self, target_channel: discord.TextChannel):
        super().__init__()
        self.data: MessagingTest2.TestNamespace
        self.data.target_channel = target_channel

    async def on_init(self):
        if "target_channel" not in self.data:
            self.data.target_channel = common.guild.get_channel(822650791303053342)

    def check_event(self, event: events.ClientEvent):
        return event.message.channel.id == self.data.target_channel.id

    async def on_run(self, event: events.OnMessage, *args, **kwargs):
        if event.message.content.lower().startswith("hi"):
            await self.data.target_channel.send("Hi, what's your name?")

            author = event.message.author
            user_name = None

            check = (
                lambda x: x.message.author == author
                and x.message.channel == self.data.target_channel
                and x.message.content
            )

            name_event = await self.manager.wait_for_event(
                events.OnMessage, check=check
            )
            user_name = name_event.message.content

            await self.data.target_channel.send(f"Hi, {user_name}")


class MemberReminderJob(core.IntervalJob, permission_level=PERMISSION_LEVELS.MEDIUM):
    DEFAULT_SECONDS = 3

    async def on_run(self):
        async with db.DiscordDB("reminders") as reminder_obj:
            reminders = reminder_obj.get({})
            new_reminders = {}
            for mem_id, reminder_dict in reminders.items():
                for dt, (msg, chan_id, msg_id) in reminder_dict.items():
                    if datetime.datetime.utcnow() >= dt:
                        content = f"__**Reminder for you:**__\n>>> {msg}"

                        channel = None
                        if common.guild is not None:
                            channel = common.guild.get_channel(chan_id)
                        if not isinstance(channel, discord.TextChannel):
                            # Channel does not exist in the guild, DM the user
                            try:
                                user = await common.bot.fetch_user(mem_id)
                                if user.dm_channel is None:
                                    await user.create_dm()

                                await user.dm_channel.send(content=content)
                            except discord.HTTPException:
                                pass
                            continue

                        allowed_mentions = discord.AllowedMentions.none()
                        allowed_mentions.replied_user = True
                        try:
                            message = await channel.fetch_message(msg_id)
                            await message.reply(
                                content=content, allowed_mentions=allowed_mentions
                            )
                        except discord.HTTPException:
                            # The message probably got deleted, try to resend in channel
                            allowed_mentions.users = [discord.Object(mem_id)]
                            content = f"__**Reminder for <@!{mem_id}>:**__\n>>> {msg}"
                            try:
                                await channel.send(
                                    content=content,
                                    allowed_mentions=allowed_mentions,
                                )
                            except discord.HTTPException:
                                pass
                    else:
                        if mem_id not in new_reminders:
                            new_reminders[mem_id] = {}

                        new_reminders[mem_id][dt] = (msg, chan_id, msg_id)

            if reminders != new_reminders:
                reminder_obj.write(new_reminders)


class Main(core.SingleRunJob, permission_level=PERMISSION_LEVELS.HIGHEST):
    DEFAULT_RECONNECT = False

    async def on_start(self):
        self.remove_from_exception_whitelist(asyncio.TimeoutError)

    async def on_run(self):

        for job in (
            self.manager.create_job(
                MessagingTest2,
                target_channel=common.guild.get_channel(822650791303053342),
            ),
            self.manager.create_job(
                MessagingTest2,
                target_channel=common.guild.get_channel(841726972841558056),
            ),
            self.manager.create_job(
                MessagingTest2,
                target_channel=common.guild.get_channel(844492573912465408),
            ),
            self.manager.create_job(
                MessagingTest2,
                target_channel=common.guild.get_channel(849259216195420170),
            ),
            self.manager.create_job(
                MessagingTest2,
                target_channel=common.guild.get_channel(844492623636725820),
            ),
        ):

            await self.manager.register_job(job)

        await self.manager.create_and_register_job(
            core.RegisterDelayedJob,
            10.0,
            self.manager.create_job(
                messaging.MessageSend,
                channel=822650791303053342,
                content="This will only happen once.",
            ),
        )

        if not self.manager.job_scheduling_is_initialized():
            await self.manager.wait_for_job_scheduling_initialization()

        await self.manager.create_job_schedule(
            messaging.MessageSend,
            timestamp=datetime.datetime.now(),
            recur_interval=datetime.timedelta(seconds=10),
            max_recurrences=2,
            job_kwargs=dict(
                channel=822650791303053342,
                content="This will occur once. Then every 10 seconds, but only 2 times.",
            ),
        )

        await self.manager.create_and_register_job(MemberReminderJob)

        await self.manager.create_job_schedule(
            messaging.MessageSend,
            timestamp=datetime.datetime.now() + datetime.timedelta(seconds=10),
            job_kwargs=dict(
                channel=841726972841558056,
                content="Say 'I am cool.'",
            ),
        )

        msg_event: events.OnMessage = await self.manager.wait_for_event(
            events.OnMessage,
            check=(
                lambda x: x.message.channel.id == 841726972841558056
                and x.message.content == "I am cool."
            ),
        )

        t0 = perf_counter()
        reaction_add_job = self.manager.create_job(
            messaging.ReactionsAdd,
            None,
            msg_event.message,
            *tuple("🇳🇴⬛🇲🇪"),
            853327268474126356,
            848212253017636895,
            848212380059566130,
            848212610733572168,
            848211974370099230,
            848212574213767208,
        )
        dt = perf_counter()-t0
        print(dt)

        await self.manager.register_job(reaction_add_job)
        print("\n".join(str(j) for j in self.manager.find_jobs(is_being_killed=False)))
        await self.wait_for(reaction_add_job.await_done())


__all__ = [
    "Main",
]
