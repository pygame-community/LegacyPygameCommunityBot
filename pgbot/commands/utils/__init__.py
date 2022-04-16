from typing import TYPE_CHECKING, Any, Optional, Union
import discord
from discord.ext import commands

from pgbot import common

from . import clock, docs, help, sandbox, vibecheck


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
            if role.id in common.ServerConstants.ADMIN_ROLES:
                return True, True
            elif role.id in common.ServerConstants.PRIV_ROLES:
                is_priv = True

    return False, is_priv