import discord
import asyncio

# TODO: Custom UIView class that can use on_timeout, has an
# add_components(*args) and remove_components(*args)

# TODO: Document this module more

__all__ = ["Button"]


# TODO: More options for buttons?
class Button(discord.ui.Button):
    """Discord button but with an additional callback function."""

    def __init__(
        self,
        *,
        func,
        style,
        label,
        disabled=False,
        custom_id=None,
        url=None,
        emoji=None,
        row=None,
    ):
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )
        self.func = func

    async def callback(self, interaction):
        await self.func(self, interaction)
