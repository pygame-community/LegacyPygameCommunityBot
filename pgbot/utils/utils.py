"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some important utility functions.
"""

from __future__ import annotations


import discord
import pygame

from pgbot import common, db


async def get_channel_feature(
    name: str, channel: common.Channel, defaultret: bool = False
):
    """
    Get the channel feature. Returns True if the feature name is disabled on
    that channel, False otherwise. Also handles category channel
    """
    async with db.DiscordDB("feature") as db_obj:
        db_dict: dict[int, bool] = db_obj.get({}).get(name, {})

    if channel.id in db_dict:
        return db_dict[channel.id]

    if isinstance(channel, discord.TextChannel):
        if channel.category_id is None:
            return defaultret
        return db_dict.get(channel.category_id, defaultret)

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


def split_wc_scores(scores: dict[int, int]):
    """
    Split wc scoreboard into different categories
    """
    scores_list = [(score, f"<@!{mem}>") for mem, score in scores.items()]
    scores_list.sort(reverse=True)

    for title, category_score in common.WC_SCORING:
        category_list = list(filter(lambda x: x[0] >= category_score, scores_list))
        if not category_list:
            continue

        desc = ">>> " + "\n".join(
            (f"`{score}` **•** {mem} :medal:" for score, mem in category_list)
        )

        yield title, desc, False
        scores_list = scores_list[len(category_list) :]


async def give_wc_roles(member: discord.Member, score: int):
    """
    Updates the WC roles of a member based on their latest total score
    """
    got_role: bool = False
    for min_score, role_id in common.ServerConstants.WC_ROLES:
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
