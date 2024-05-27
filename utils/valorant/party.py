from discord import Interaction, User, Member
from utils.valorant import cache as Cache, useful, view as View
from utils.valorant.embed import Embed, GetEmbed
import discord

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
        
        return True
    
    def remove_player(self, player_id: str) -> bool:
        self.players.pop(player_id)
        await self.message.edit(embed=GetEmbed.party_list(self.players)) # type: ignore

        return True
    
    async def move_users(self, interaction: Interaction[ValorantBot]):
        await interaction.response.defer()
        try:
            role1 = discord.utils.get(interaction.guild.roles, name="VAL_1") # type: ignore
            role2 = discord.utils.get(interaction.guild.roles, name="VAL_2") # type: ignore
            await interaction.guild.chunk() # type: ignore
            role_members1 = [member for member in interaction.guild.members if role1 in member.roles] # type: ignore
            role_members2 = [member for member in interaction.guild.members if role2 in member.roles] # type: ignore
            for member in role_members1:
                # 음성채널 이동
                if member.voice:
                    await member.move_to(self.voice_channel[0]) # type: ignore

            for member in role_members2:
                # 음성채널 이동
                if member.voice:
                    await member.move_to(self.voice_channel[1]) # type: ignore

            await interaction.followup.send('음성 채널 이동 완료!')
        except Exception as e:
            print(e)
            await interaction.followup.send('음성 채널 이동 실패!')

    async def re_change(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            for member in self.best_team2:
                user = self.players[member]['user']
                # 음성채널 이동
                await user.move_to(self.voice_channel[0])
            
            await interaction.followup.send('음성 채널 이동 완료!')
        except Exception as e:
            print(e)
            await interaction.followup.send('음성 채널 이동 실패!')