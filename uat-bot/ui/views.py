from __future__ import annotations

import discord

from ui.embeds import EMBED_COLOR


class PaginationView(discord.ui.View):
    def __init__(
        self,
        *,
        author_id: int,
        pages: list[discord.Embed],
        timeout: float = 120.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.pages = pages
        self.index = 0
        self.message: discord.Message | None = None

        self.prev_btn = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, row=0)
        self.next_btn = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, row=0)
        self.prev_btn.callback = self._prev
        self.next_btn.callback = self._next
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.index <= 0
        self.next_btn.disabled = self.index >= len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "Only the command user can use these buttons.", ephemeral=True
        )
        return False

    async def _prev(self, interaction: discord.Interaction) -> None:
        self.index = max(0, self.index - 1)
        self._update_buttons()
        e = self.pages[self.index]
        e.color = EMBED_COLOR
        await interaction.response.edit_message(embed=e, view=self)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._update_buttons()
        e = self.pages[self.index]
        e.color = EMBED_COLOR
        await interaction.response.edit_message(embed=e, view=self)

    async def on_timeout(self) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
