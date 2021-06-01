"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines utility classes for tic-tac-toe mini game
"""
# TODO: Document this module more

import discord
from pgbot import ui_utils, common


# TODO: Generalize this class more, add more utils specific to minigames.
class Game:
    def __init__(self, resp_msg, players, title):
        self.buttons = []
        self.view = discord.ui.View(360)
        self.msg = resp_msg  # bot response message
        self.players = players  # list of discord.Member involved in the game
        self.current_player = 0
        self.style = {}
        self.title = title

    async def setup(self):
        await self.msg.edit(content=self.title, view=self.view, embed=None)

    async def callback(self, *_):
        """Dummy function, subclasses override this"""

    async def _callback(self, button, interaction):
        if interaction.user.id != self.players[self.current_player].id:
            return

        await self.callback(button, interaction)

    def add_button(self, *args, **kwargs):
        button = ui_utils.Button(func=self._callback, *args, **kwargs)
        self.buttons.append(button)
        self.view.add_item(button)

    def game_over(self):
        """Dummy function, subclasses overwrite this"""

    def update(self):
        self.view.clear_items()
        for button in self.buttons:
            self.view.add_item(button)

        if all([btn.disabled for btn in self.buttons]):
            self.game_over()

    def change_button(self, button, disabled=True, n=None):
        if n is None:
            n = self.current_player

        button.disabled = disabled
        if self.style:
            if self.style.get("colors"):
                button.style = self.style["colors"][n]

            if self.style.get("emojis"):
                button.emoji = self.style["emojis"][n]
                if not self.style.get("texts"):
                    button.label = common.ZERO_SPACE

            if self.style.get("texts"):
                button.label = self.style["texts"][n]


# TODO: Add rules, check winner, that stuff.
# TODO: Add more options to the game like board size, colors.
class TicTacToe(Game):
    def __init__(self, resp_msg, player1, player2, title):
        super().__init__(resp_msg, [player1, player2], title)
        n = 3
        for i in range(n):
            for j in range(n):
                self.add_button(label="_", style=2, row=i, custom_id=str(j + i * n))

        self.style = {
            "colors": [1, 3],
            "emojis": ["⭕", "❌"],
        }
        self.board = [[None for _ in range(3)] for _ in range(3)]

    async def callback(self, button, _):
        self.current_player += 1
        self.current_player = self.current_player % len(self.players)

        button = self.buttons[int(button.custom_id)]
        self.change_button(button)
        self.update()

        await self.msg.edit(view=self.view)
