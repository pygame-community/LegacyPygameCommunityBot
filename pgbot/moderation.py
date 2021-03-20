import asyncio
import random

import discord

from . import common, emotion, util


async def check_sus(msg: discord.Message):
    if isinstance(msg.channel, discord.DMChannel):
        return False

    has_a_competence_role = False
    for role in msg.author.roles:
        if role.id in common.COMPETENCE_ROLES:
            has_a_competence_role = True

    if not has_a_competence_role and msg.channel.id in common.PYGAME_CHANNELS:
        muted_role = discord.utils.get(msg.guild.roles, id=common.MUTED_ROLE)
        await msg.author.add_roles(muted_role)

        response_msg = await util.send_embed(
            msg.channel,
            random.choice(common.ROLE_PROMPT["title"]),
            random.choice(common.ROLE_PROMPT["message"]).format(msg.author.mention)
        )
        await asyncio.sleep(30)
        await msg.author.remove_roles(muted_role)
        await response_msg.delete()
        return True

    if common.BONK in msg.content and not msg.content.startswith(common.PREFIX):
        emotion.boncc_count += msg.content.count(common.BONK)
        if msg.content.count(common.BONK) > common.BONCC_THRESHOLD / 2 or emotion.boncc_count > common.BONCC_THRESHOLD:
            await util.send_embed(
                msg.channel,
                "Did you hit the snek?",
                "You mortal mammal! How you dare to boncc a snake?"
            )
            await msg.channel.send(common.PG_ANGRY_AN)

        if emotion.boncc_count > 2 * common.BONCC_THRESHOLD:
            emotion.boncc_count = 2 * common.BONCC_THRESHOLD

    return False
