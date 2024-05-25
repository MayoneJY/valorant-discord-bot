from discord import Interaction, User, Member
from utils.valorant import cache as Cache, useful, view as View
from utils.valorant.embed import Embed, GetEmbed

from typing import TYPE_CHECKING, Any


from bot import ValorantBot

class CustomParty():
    def __init__(self, valorantCog, interaction: Interaction[ValorantBot], bot: ValorantBot): # type: ignore
        self.bot = bot
        self.interaction = interaction
        self.players = {} # dict[str, dict[str, int|User]] - dict[player_id, dict["rank", tier, "user", interaction.user]]
        self.voice_channel = [] # list[interaction.voice_channel] - max 2
        self.map = None # str - map name
        self.message = None
        self.valorantCog = valorantCog
        self.best_team1 = []
        self.best_team2 = []
        self.best_difference = float('inf')

    async def initialize(self):
        await self.interaction.followup.send(content="모든 참여자가 참가했을 때, 시작 버튼을 눌러주세요.", ephemeral=True, view=View.CustomPartyStartButtons(self.interaction ,self, self.bot))
        
        self.message = await self.interaction.followup.send(content="파티에 참여하세요!", embed=GetEmbed.party_list(), view=View.CustomPartyJoinButtons(self.interaction, self, self.valorantCog, self.bot))


    async def add_player(self, player_id: str, player: dict) -> bool:
        self.players[player_id] = player
        await self.message.edit(embed=GetEmbed.party_list(self.players)) # type: ignore
        print(self.players)
        return True
    
    def remove_player(self, player_id: str) -> bool:
        self.players.pop(player_id)

        return True