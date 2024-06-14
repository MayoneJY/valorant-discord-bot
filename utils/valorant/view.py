from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

# Standard
import discord
from discord import ButtonStyle, Interaction, TextStyle, ui

from ..errors import ValorantBotError
from ..locale_v2 import ValorantTranslator
from .resources import get_item_type, emoji_icon_assests
from .party import CustomParty
from .useful import GetEmoji
from utils.valorant.embed import Embed, GetEmbed
# Local
from .useful import JSON, GetEmoji, GetItems, format_relative
import inspect

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot

    from .db import DATABASE


class TwoFA_Button_UI(ui.View):
    def __init__ (self, db, cookies, message, label, response): # type: ignore
        super().__init__(timeout=None)
        self.db = db
        self.cookies = cookies
        self.message = message
        self.label = label
        self.response = response


    @ui.button(label='2차 인증 코드 입력', style=ButtonStyle.primary)
    async def button_callback(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(TwoFA_UI(interaction, self.db, self.cookies, self.message, self.label, self.response))

class LoginModal(ui.Modal):
    def __init__(self, msg, valorantCog, login, command_name = None): # type: ignore
        self.valorantCog = valorantCog
        self.msg = msg
        self.command_name = command_name
        
        if login == "val":
            super().__init__(title="발로란트 로그인", timeout=None)
            self.add_item(ui.TextInput(label='아이디', placeholder='아이디를 입력하세요', style=TextStyle.short))
            self.add_item(ui.TextInput(label='비밀번호', placeholder='비밀번호를 입력하세요', style=TextStyle.short))
        elif login == "cookie":
            super().__init__(title="쿠키 로그인", timeout=None)
            self.add_item(ui.TextInput(label='쿠키', placeholder='쿠키를 입력하세요', style=TextStyle.short))
            self.add_item(ui.TextInput(label='쿠키 로그인 방법', default='https://youtu.be/cFMNHEHEp2A', style=TextStyle.short)) # type: ignore
        elif command_name == None and login == "no_login":
            super().__init__(title="비로그인(최소 기능)", timeout=None)
            self.add_item(ui.TextInput(label='티어', placeholder="티어를 입력하세요.(예: '플3', '언랭', '레디')", style=TextStyle.short))

    async def on_submit(self, interaction: Interaction[ValorantBot]) -> None:
        try:
            if self.title == "발로란트 로그인":
                await self.valorantCog.commands_dict['로그인'].callback(self.valorantCog, interaction, self.children[0].value, self.children[1].value) # type: ignore
            elif self.title == "쿠키 로그인":
                await self.valorantCog.commands_dict['쿠키'].callback(self.valorantCog, interaction, self.children[0].value) # type: ignore

            await self.delete()

            if self.command_name == None:
                if self.title == "발로란트 로그인":
                    await self.valorantCog.party[interaction.channel].join_view.join2(interaction)
                elif self.title == "쿠키 로그인":
                    await self.valorantCog.party[interaction.channel].join_view.join2(interaction)
                elif self.title == "비로그인(최소 기능)":
                    await self.valorantCog.party_join2(interaction, self.children[0].value) # type: ignore
            else:
                try:
                    await self.valorantCog.commands_dict[self.command_name].callback(self.valorantCog, interaction)
                except Exception as e:
                    print(f"LoginModal.on_submit_method:{e}")
        except Exception as e:
            print(f"LoginModal.on_submit:{e}")

    async def delete(self) -> None:
        await self.msg.delete()


class LoginView(ui.View):
    def __init__(self, valorantCog = None, command_name = None) -> None: # type: ignore
        super().__init__(timeout=None)
        self.valorantCog = valorantCog
        self.command_name = command_name
        if command_name:
            options=[
                discord.SelectOption(label='발로란트 로그인', value='id_pw'),
                discord.SelectOption(label='쿠키', value='cookie')
            ]
        else:
            options=[
                discord.SelectOption(label='발로란트 로그인', value='id_pw'),
                discord.SelectOption(label='쿠키', value='cookie'),
                discord.SelectOption(label='비로그인(최소 기능)', value='no_login')
            ]
        self.select = ui.Select(placeholder='로그인 방법 선택', min_values=1, max_values=1, options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    def init(self, msg) -> None: # type: ignore
        self.msg = msg

    async def select_callback(self, interaction: Interaction[ValorantBot]) -> None:
        try:
            if self.select.values[0] == 'id_pw':
                await interaction.response.send_modal(LoginModal(self.msg, self.valorantCog, "val", self.command_name))
            elif self.select.values[0] == 'cookie':
                await interaction.response.send_modal(LoginModal(self.msg, self.valorantCog, "cookie", self.command_name))
            elif self.select.values[0] == 'no_login':
                await interaction.response.send_modal(LoginModal(self.msg, self.valorantCog, "no_login", self.command_name))
        except Exception as e:
            print(f"LoginView.login:{e}")


class CustomPartySpactorButtons(ui.View):
    def __init__(self, custom_party: CustomParty, interaction: Interaction[ValorantBot]) -> None:
        super().__init__(timeout=None)
        self.custom_party = custom_party
        self.interaction = interaction
        self.msg = None
        self.team1 = []
        self.team2 = []

    @ui.button(label='1팀 관전', style=ButtonStyle.green)
    async def spactor_team_one(self, interaction: Interaction[ValorantBot], button: ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        
        if interaction.user.name in self.custom_party.players:
            await interaction.followup.send('파티에 참여된 상태에서 관전자로 변경할 수 없습니다.', ephemeral=True)
            return

        role1 = discord.utils.get(interaction.guild.roles, name="VAL_1") # type: ignore
        role2 = discord.utils.get(interaction.guild.roles, name="VAL_2") # type: ignore
        if role1 in interaction.user.roles: # type: ignore
            await interaction.followup.send('이미 1팀에 속해있습니다.', ephemeral=True)
            return
        if role2 in interaction.user.roles: # type: ignore
            await interaction.user.remove_roles(role2) # type: ignore
        self.team1.append(f"{interaction.user.global_name}")
        await interaction.user.add_roles(role1) # type: ignore

        await interaction.followup.send('1팀 관전자로 설정되었습니다.', ephemeral=True)

        await self.msg_embed()
        
    @ui.button(label='2팀 관전', style=ButtonStyle.primary)
    async def spactor_team_two(self, interaction: Interaction[ValorantBot], button: ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        
        if interaction.user.name in self.custom_party.players:
            await interaction.followup.send('파티에 참여된 상태에서 관전자로 변경할 수 없습니다.', ephemeral=True)
            return

        role1 = discord.utils.get(interaction.guild.roles, name="VAL_1") # type: ignore
        role2 = discord.utils.get(interaction.guild.roles, name="VAL_2") # type: ignore
        if role2 in interaction.user.roles: # type: ignore
            await interaction.followup.send('이미 2팀에 속해있습니다.', ephemeral=True)
            return
        if role1 in interaction.user.roles: # type: ignore
            await interaction.user.remove_roles(role1) # type: ignore
        self.team2.append(f"{interaction.user.global_name}")
        await interaction.user.add_roles(role2) # type: ignore

        await interaction.followup.send('2팀 관전자로 설정되었습니다.', ephemeral=True)

        await self.msg_embed()


    @ui.button(label='관전 퇴장', style=ButtonStyle.red)
    async def leave(self, interaction: Interaction[ValorantBot], button: ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)

        role1 = discord.utils.get(interaction.guild.roles, name="VAL_1") # type: ignore
        role2 = discord.utils.get(interaction.guild.roles, name="VAL_2") # type: ignore
        check = False
        if role1 in interaction.user.roles: # type: ignore
            await interaction.user.remove_roles(role1) # type: ignore
            self.team1.remove(f"{interaction.user.global_name}")
            check = True
        elif role2 in interaction.user.roles: # type: ignore
            await interaction.user.remove_roles(role2) # type: ignore
            self.team2.remove(f"{interaction.user.global_name}")
            check = True

        if check:
            await interaction.followup.send('관전자에서 퇴장했습니다.', ephemeral=True)
            if len(self.team1) == 0 and len(self.team2) == 0:
                await self.msg.delete() # type: ignore
                self.msg = None
        else:
            await interaction.followup.send('관전자로 설정되어 있지 않습니다.', ephemeral=True)

    async def msg_embed(self) -> None:

        embeds = []

        embeds.append(discord.Embed(title=f"팀 1 관전자", color=0xff0000))
        embeds[1].add_field(name="", value="\n".join(self.team1), inline=False)

        embeds.append(discord.Embed(title=f"팀 2 관전자", color=0x0000ff))
        embeds[2].add_field(name="", value="\n".join(self.team2), inline=False)
        if self.msg == None:
            self.msg = await self.interaction.followup.send(embeds=embeds)
        else:
            await self.msg.edit(embeds=embeds) # type: ignore

class CustomPartyJoinButtons(ui.View):
    def __init__(self, interaction:Interaction[ValorantBot], custom_party: CustomParty, valorantCog, bot: ValorantBot) -> None: # type: ignore
        super().__init__(timeout=None)
        self.custom_party = custom_party
        self.valorantCog = valorantCog
        self.bot = bot
        self.interaction = interaction

    async def on_timeout(self) -> None:
        """Called when the view times out"""
        await self.interaction.edit_original_response(view=self)

    @ui.button(label='참여', style=ButtonStyle.green)
    async def join(self, interaction: Interaction[ValorantBot], button: ui.Button | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        p_msg = await interaction.followup.send('파티 입장중..' , ephemeral=True)
        try:
            user = interaction.user
            player_id = str(user.name)
            rank = await self.valorantCog.get_tier_rank(interaction)
            if rank == -1:
                return
            emoji = discord.utils.get(self.bot.emojis, name=f'competitivetiers{rank}') # type: ignore
            player_info, player_puuid = await self.valorantCog.get_player_info(interaction)
            get_player_headers = await self.valorantCog.get_player_headers(interaction)

            
            if await self.custom_party.add_player(player_id, {"displayName": str(user.global_name), "rank": rank, "user": user, "emoji": emoji, "headers": get_player_headers, "username": player_info.split("#")[0], "tag": player_info.split("#")[1], "puuid": player_puuid}):
                await p_msg.edit(content="참여 완료!") # type: ignore
            else:
                await p_msg.edit(content="참여 실패..") # type: ignore
        except Exception as e:
            await interaction.followup.send(f'참여 실패.. \n {e}')

    async def join2(self, interaction: Interaction[ValorantBot]) -> None:
        p_msg = await interaction.followup.send('파티 입장중..' , ephemeral=True)
        try:
            user = interaction.user
            player_id = str(user.name)
            rank = await self.valorantCog.get_tier_rank(interaction)
            if rank == -1:
                return
            emoji = discord.utils.get(self.bot.emojis, name=f'competitivetiers{rank}') # type: ignore
            player_info, player_puuid = await self.valorantCog.get_player_info(interaction)
            get_player_headers = await self.valorantCog.get_player_headers(interaction)

            
            if await self.custom_party.add_player(player_id, {"displayName": str(user.global_name), "rank": rank, "user": user, "emoji": emoji, "headers": get_player_headers, "username": player_info.split("#")[0], "tag": player_info.split("#")[1], "puuid": player_puuid}):
                await p_msg.edit(content="참여 완료!") # type: ignore
            else:
                await p_msg.edit(content="참여 실패..") # type: ignore
        except Exception as e:
            await interaction.followup.send(f'참여 실패.. \n {e}')

    @ui.button(label='퇴장', style=ButtonStyle.red)
    async def leave(self, interaction: Interaction[ValorantBot], button: ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)

        await self.custom_party.remove_player(str(interaction.user.name))

        await interaction.followup.send('파티에 퇴장했어요!', ephemeral=True)

class CustomPartyStartButtons(ui.View):
    def __init__(self, interaction: Interaction[ValorantBot], custom_party: CustomParty, bot: ValorantBot,
                 is_started: bool = False, is_voice_channel_set: bool = False, is_select: bool = True, is_buttons: bool = True) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.custom_party = custom_party
        self.selected_channels = []
        
        self.is_started = is_started
        self.is_voice_channel_set = is_voice_channel_set

        self.is_select = is_select
        self.is_buttons = is_buttons
        self.is_move_button = is_buttons
        self.is_re_change_button = is_buttons
        self.is_invite_button = is_buttons
        
        self.msg = None


        if self.is_select:
            options = [
                discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in interaction.guild.voice_channels # type: ignore
                ]
            self.select = ui.Select(placeholder='음성 채널 선택 (2개):', min_values=2, max_values=2, options=options)
            self.select.callback = self.select_callback
            self.add_item(self.select)
        
        self.move_button = ui.Button(label="음성 채널 이동", style=discord.ButtonStyle.success, disabled=self.is_move_button)
        self.move_button.callback = self.move_users
        self.add_item(self.move_button)
        
        self.re_change_button = ui.Button(label="원래 통화방으로", style=discord.ButtonStyle.red, disabled=self.is_re_change_button)
        self.re_change_button.callback = self.re_change
        self.add_item(self.re_change_button)
        
        self.invite_button = ui.Button(label="초대하기", style=discord.ButtonStyle.primary, disabled=self.is_invite_button)
        self.invite_button.callback = self.invite
        self.add_item(self.invite_button)
        
        self.interaction = interaction

    def init(self, msg) -> None: # type: ignore
        self.msg = msg


    async def on_timeout(self) -> None:
        """Called when the view times out"""
        button = CustomPartyStartButtons(self.interaction, self.custom_party, self.bot, self.is_started, self.is_voice_channel_set, self.is_select, self.is_buttons)
        msg = await self.interaction.followup.send(ephemeral=True, view=button)
        button.init(msg)
        if self.msg:
            await self.msg.delete() # type: ignore
        else:
            await self.interaction.edit_original_response(view=None)


    @ui.button(label='시작', style=ButtonStyle.green)
    async def start(self, interaction: Interaction[ValorantBot], button: ui.Button) -> None:
        try:
            await interaction.response.defer()
            msg = await interaction.followup.send('팀 분배 중...')
            def find_best_split(current_index, current_team1, current_team2, current_score1, current_score2): # type: ignore
                global best_difference, best_team1, best_team2, count
                count += 1
                
                # 모든 플레이어를 처리했을 때
                if current_index == len(player_scores):
                    if abs(len(current_team1) - len(current_team2)) <= 1:  # 각 팀의 크기 차이가 1 이하일 때
                        # 현재 점수 차이가 최소인지 확인
                        if abs(current_score1 - current_score2) < best_difference:
                            best_difference = abs(current_score1 - current_score2)
                            best_team1 = current_team1[:]
                            best_team2 = current_team2[:]
                    return

                # 현재 플레이어
                player, score = player_scores[current_index]

                # 팀 1에 플레이어 추가
                if len(current_team1) < (len(player_scores) + 1) // 2:
                    find_best_split(current_index + 1, current_team1 + [player], current_team2, current_score1 + score, current_score2)

                # 팀 2에 플레이어 추가
                if len(current_team2) < (len(player_scores)) // 2:
                    find_best_split(current_index + 1, current_team1, current_team2 + [player], current_score1, current_score2 + score)

            global player

            global best_difference, best_team1, best_team2, count
            best_difference = float('inf')
            best_team1 = []
            best_team2 = []
            count = 0
            # 플레이어의 랭크를 점수로 변환
            player_scores = [(name, data['rank']) for name, data in self.custom_party.players.items()]
            
            await msg.edit(content=f'역할을 분배합니다..') # type: ignore
            # 백트래킹 시작
            find_best_split(0, [], [], 0, 0)

            self.custom_party.best_team1 = best_team1
            self.custom_party.best_team2 = best_team2

            role1 = discord.utils.get(interaction.guild.roles, name="VAL_1") # type: ignore
            role2 = discord.utils.get(interaction.guild.roles, name="VAL_2") # type: ignore

            if len(best_team1) != 0:
                # 1팀 평균 랭크
                avg_rank1 = int(sum([self.custom_party.players[member]["rank"] for member in best_team1]) / len(best_team1))
            else:
                avg_rank1 = 0

            if len(best_team2) != 0:
                # 2팀 평균 랭크
                avg_rank2 = int(sum([self.custom_party.players[member]["rank"] for member in best_team2]) / len(best_team2))
            else:
                avg_rank2 = 0
            print(avg_rank1, avg_rank2)

            modifed_best_team1 = []
            for member in best_team1:
                await self.custom_party.players[member]["user"].add_roles(role1)
                value = f"{self.custom_party.players[member]['displayName']} - {self.custom_party.players[member]['emoji']}"
                if 'headers' not in self.custom_party.players[member]:
                    value += ' - 비로그인'
                
                modifed_best_team1.append(value)

            modifed_best_team2 = []
            for member in best_team2:
                await self.custom_party.players[member]["user"].add_roles(role2)
                value = f"{self.custom_party.players[member]['displayName']} - {self.custom_party.players[member]['emoji']}"
                if 'headers' not in self.custom_party.players[member]:
                    value += ' - 비로그인'

                modifed_best_team2.append(value)
            await msg.delete() # type: ignore
            embeds = []
            embeds.append(discord.Embed(title="내전 팀 분배", description=f"팀 분배가 완료되었습니다.\n`{count}`번의 경우의 수로 밸런스를 맞췄습니다.", color=0x00ff00))

            embeds.append(discord.Embed(title=f"팀 1", color=0xff0000))
            embeds[1].set_thumbnail(url=emoji_icon_assests[f"competitivetiers{avg_rank1}"])
            embeds[1].add_field(name="", value="\n".join(modifed_best_team1), inline=False)

            embeds.append(discord.Embed(title=f"팀 2", color=0x0000ff))
            embeds[2].set_thumbnail(url=emoji_icon_assests[f"competitivetiers{avg_rank2}"])
            embeds[2].add_field(name="", value="\n".join(modifed_best_team2), inline=False)
            self.is_started = True

            await interaction.followup.send(embeds=embeds, view=CustomPartySpactorButtons(self.custom_party, interaction))
            await self.check(interaction)
            await self.custom_party.delete_party_list_message()

        except Exception as e:
            print(f"CustomPartyStartButtons.start:{e}")


    @ui.button(label='취소', style=ButtonStyle.red)
    async def cancel(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        await interaction.followup.send('파티가 취소되었어요.. :sob:')
        if self.msg:
            await self.msg.delete()
        else:
            await interaction.edit_original_response(content="취소 된 파티 메시지입니다.", view=None)
        
        await self.custom_party.delete_party_list_message()

        self.custom_party.delete()

    async def check(self, interaction: Interaction[ValorantBot]):
        if self.is_started and self.is_voice_channel_set:
            self.move_button.disabled = False
            self.re_change_button.disabled = False
            self.invite_button.disabled = False
            self.is_buttons = False

            if not interaction.response.is_done():
                if self.msg:
                    await self.msg.edit(view=self) # type: ignore
                else:
                    await interaction.response.edit_message(view=self)


    async def select_callback(self, interaction: Interaction[ValorantBot]):
        self.selected_channels = [interaction.guild.get_channel(int(channel_id)) for channel_id in self.select.values] # type: ignore
        self.custom_party.voice_channel = self.selected_channels

        if len(self.selected_channels) == 2:
            self.is_voice_channel_set = True
            self.is_select = False
            self.remove_item(self.select)  # 드롭다운 삭제
            await self.check(interaction)

        if not interaction.response.is_done():
            if self.msg:
                await self.msg.edit(view=self) # type: ignore
            else:
                await interaction.response.edit_message(view=self)
        

    async def move_users(self, interaction: Interaction[ValorantBot]):
        await interaction.response.defer()
        await self.custom_party.move_users(interaction)


    async def re_change(self, interaction: Interaction[ValorantBot]) -> None:
        await interaction.response.defer()
        await self.custom_party.re_change(interaction)
        

    async def invite(self, interaction: Interaction[ValorantBot]) -> None:
        await interaction.response.defer()
        await self.custom_party.valorantCog.party_room_create(interaction)


class share_button(ui.View):
    def __init__(self, interaction: Interaction, embeds: list[discord.Embed]) -> None:
        self.interaction: Interaction = interaction
        self.embeds = embeds
        super().__init__(timeout=300)

    async def on_timeout(self) -> None:
        """Called when the view times out"""
        await self.interaction.edit_original_response(view=None)

    @ui.button(label='Share to friends', style=ButtonStyle.primary)
    async def button_callback(self, interaction: Interaction, button: ui.Button):
        await interaction.channel.send(embeds=self.embeds)  # type: ignore
        await self.interaction.edit_original_response(content='\u200b', embed=None, view=None)


class NotifyView(discord.ui.View):
    def __init__(self, user_id: int, uuid: str, name: str, response: dict) -> None:
        self.user_id = user_id
        self.uuid = uuid
        self.name = name
        self.response = response
        super().__init__(timeout=600)
        self.remove_notify.label = response.get('REMOVE_NOTIFY')

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id == int(self.user_id):
            return True
        await interaction.response.send_message(
            'This pagination menu cannot be controlled by you, sorry!', ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        """Called when the view times out"""

        with contextlib.suppress(Exception):
            self.remve_notify.disabled = True  # type: ignore
            await self.message.edit_original_response(view=self)  # type: ignore

    @discord.ui.button(label='Remove Notify', emoji='✖️', style=ButtonStyle.red)
    async def remove_notify(self, interaction: Interaction, button: ui.Button):
        data = JSON.read('notifys')

        for i in range(len(data)):
            if data[i]['uuid'] == self.uuid and data[i]['id'] == str(self.user_id):  # type: ignore
                data.pop(i)  # type: ignore
                break

        JSON.save('notifys', data)

        self.remove_notify.disabled = True
        await interaction.response.edit_message(view=self)

        removed_notify = self.response.get('REMOVED_NOTIFY')
        await interaction.followup.send(removed_notify.format(skin=self.name), ephemeral=True)  # type: ignore


class _NotifyListButton(ui.Button):
    def __init__(self, label: str, custom_id: str) -> None:
        super().__init__(label=label, style=ButtonStyle.red, custom_id=str(custom_id))

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        data: dict[str, Any] = JSON.read('notifys')
        for i in range(len(data)):
            if data[i]['uuid'] == self.custom_id and data[i]['id'] == str(self.view.interaction.user.id):  # type: ignore
                data.pop(i)  # type: ignore
                break

        JSON.save('notifys', data)

        del self.view.skin_source[self.custom_id]  # type: ignore
        self.view.update_button()  # type: ignore
        embed = self.view.main_embed()  # type: ignore
        await self.view.interaction.edit_original_response(embed=embed, view=self.view)  # type: ignore


class NotifyViewList(ui.View):
    skin_source: dict

    def __init__(self, interaction: Interaction[ValorantBot], response: dict[str, Any]) -> None:
        self.interaction: Interaction = interaction
        self.response = response
        self.bot: ValorantBot = interaction.client
        self.default_language = 'en-US'
        super().__init__(timeout=600)

    async def on_timeout(self) -> None:
        """Called when the view times out."""
        embed = discord.Embed(color=0x2F3136, description='🕙 Timeout')
        await self.interaction.edit_original_response(embed=embed, view=None)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message(
            'This pagination menu cannot be controlled by you, sorry!', ephemeral=True
        )
        return False

    def update_button(self) -> None:
        self.clear_items()
        self.create_button()

    def create_button(self) -> None:
        data = self.skin_source
        for index, skin in enumerate(data, start=1):
            self.add_item(_NotifyListButton(label=str(index), custom_id=skin))

    def get_data(self) -> None:
        """Gets the data from the cache."""

        database = JSON.read('notifys')
        notify_skin = [x['uuid'] for x in database if x['id'] == str(self.interaction.user.id)]  # type: ignore
        skin_source = {}

        for uuid in notify_skin:
            skin = GetItems.get_skin(uuid)
            name = skin['names'][str(VLR_locale)]
            icon = skin['icon']

            skin_source[uuid] = {
                'name': name,
                'icon': icon,
                'price': GetItems.get_skin_price(uuid),
                'emoji': GetEmoji.tier_by_bot(uuid, self.bot),
            }
        self.skin_source = skin_source

    def main_embed(self) -> discord.Embed:
        """Main embed for the view"""

        skin_list = self.skin_source
        vp_emoji = discord.utils.get(self.bot.emojis, name='ValorantPointIcon')

        title = self.response.get('TITLE')
        embed = discord.Embed(description='\u200b', title=title, color=0xFD4554)

        click_for_remove = self.response.get('REMOVE_NOTIFY')

        if len(skin_list) == 0:
            description = self.response.get('DONT_HAVE_NOTIFY')
            embed.description = description
        else:
            embed.set_footer(text=click_for_remove)
            count = 0
            text_format = []
            for count, skin in enumerate(skin_list):
                name = skin_list[skin]['name']
                icon = skin_list[skin]['icon']
                price = skin_list[skin]['price']
                emoji = skin_list[skin]['emoji']
                text_format.append(f'**{count + 1}.** {emoji} **{name}**\n{vp_emoji} {price}')
            else:
                embed.description = '\n'.join(text_format)
                if len(skin_list) == 1:
                    embed.set_thumbnail(url=icon)

        return embed

    async def start(self) -> None:
        """Starts the view."""
        self.get_data()
        self.create_button()
        embed = self.main_embed()
        await self.interaction.followup.send(embed=embed, view=self)


class TwoFA_UI(ui.Modal, title='Two-factor authentication'):
    """Modal for riot login with multifactorial authentication"""

    def __init__(
        self,
        interaction: Interaction,
        db: DATABASE,
        cookie: dict[str, Any],
        message: str,
        label: str,
        response: dict[str, Any],
    ) -> None:
        super().__init__(timeout=600)
        self.interaction: Interaction = interaction
        self.db = db
        self.cookie = cookie
        self.response = response
        self.two2fa.placeholder = message
        self.two2fa.label = label
    
        self.add_item(ui.TextInput(label='2차 인증 코드 얻는 방법', 
                     default='https://playvalorant.com/ 에서 로그인하면 이메일로 2차 인증 코드를 받을 수 있습니다.', 
                     style=TextStyle.long, required=False))

    two2fa = ui.TextInput(label='Input 2FA Code', max_length=6, style=TextStyle.long)

    async def on_submit(self, interaction: Interaction) -> None:
        """Called when the user submits the modal."""

        code = self.two2fa.value
        if code:
            cookie = self.cookie
            user_id = self.interaction.user.id
            auth = self.db.auth
            auth.locale_code = self.interaction.locale  # type: ignore

            async def send_embed(content: str) -> None:
                embed = discord.Embed(description=content, color=0xFD4554)
                if interaction.response.is_done():
                    return await interaction.followup.send(embed=embed, ephemeral=True)
                await interaction.response.send_message(embed=embed, ephemeral=True)

            if not code.isdigit():
                return await send_embed(f'`{code}` is not a number')

            auth = await auth.give2facode(code, cookie)

            if auth['auth'] == 'response':
                login = await self.db.login(user_id, auth, self.interaction.locale)  # type: ignore
                if login['auth']:  # type: ignore
                    return await send_embed(f"{self.response.get('SUCCESS')} **{login['player']}!**")  # type: ignore

                return await (login['error'])  # type: ignore

            elif auth['auth'] == 'failed':
                return await send_embed(auth['error'])

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        """Called when the user submits the modal with an error."""
        print('TwoFA_UI:', error)
        embed = discord.Embed(description='Oops! Something went wrong.', color=0xFD4554)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# inspired by https://github.com/giorgi-o
class BaseBundle(ui.View):
    def __init__(
        self, interaction: Interaction[ValorantBot], entries: dict[str, Any], response: dict[str, Any]
    ) -> None:
        self.interaction: Interaction = interaction
        self.entries = entries
        self.response = response
        self.language = str(VLR_locale)
        self.bot: ValorantBot = interaction.client
        self.current_page: int = 0
        self.embeds: list[list[discord.Embed]] = []
        self.page_format = {}
        super().__init__()
        self.clear_items()

    def fill_items(self, force: bool = False) -> None:
        self.clear_items()
        if len(self.embeds) > 1 or force:
            self.add_item(self.back_button)
            self.add_item(self.next_button)

    def base_embed(self, title: str, description: str, icon: str, color: int = 0x0F1923) -> discord.Embed:
        """Base embed for the view"""

        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_thumbnail(url=icon)
        return embed

    def build_embeds(self, selected_bundle: int = 1) -> None:
        """Builds the bundle embeds"""

        vp_emoji = discord.utils.get(self.bot.emojis, name='ValorantPointIcon')

        embeds_list = []
        embeds = []

        collection_title = self.response.get('TITLE')

        for index, bundle in enumerate(sorted(self.entries, key=lambda c: c['names'][self.language]), start=1):  # type: ignore
            if index == selected_bundle:
                embeds.append(
                    discord.Embed(
                        title=bundle['names'][self.language] + f' {collection_title}',  # type: ignore
                        description=f"{vp_emoji} {bundle['price']}",  # type: ignore
                        color=0xFD4554,
                    ).set_image(url=bundle['icon'])  # type: ignore
                )

                for items in sorted(bundle['items'], key=lambda x: x['price'], reverse=True):  # type: ignore
                    item = GetItems.get_item_by_type(items['type'], items['uuid'])  # type: ignore
                    item_type = get_item_type(items['type'])  # type: ignore

                    emoji = GetEmoji.tier_by_bot(items['uuid'], self.bot) if item_type == 'Skins' else ''  # type: ignore
                    icon = item['icon'] if item_type != 'Player Cards' else item['icon']['large']
                    color = 0xFD4554 if item_type == 'Skins' else 0x0F1923

                    embed = self.base_embed(
                        f"{emoji} {item['names'][self.language]}",
                        f"{vp_emoji} {items['price']}",  # type: ignore
                        icon,
                        color,  # type: ignore
                    )
                    embeds.append(embed)

                    if len(embeds) == 10:
                        embeds_list.append(embeds)
                        embeds = []

                if len(embeds) != 0:
                    embeds_list.append(embeds)

        self.embeds = embeds_list

    def build_featured_bundle(self, bundle: list[dict]) -> list[discord.Embed]:
        """Builds the featured bundle embeds"""

        vp_emoji = discord.utils.get(self.bot.emojis, name='ValorantPointIcon')

        name = bundle['names'][self.language]  # type: ignore

        featured_bundle_title = self.response.get('TITLE')

        duration = bundle['duration']  # type: ignore
        duration_text = self.response.get('DURATION').format(  # type: ignore
            duration=format_relative(datetime.utcnow() + timedelta(seconds=duration))
        )

        bundle_price = bundle['price']  # type: ignore
        bundle_base_price = bundle['base_price']  # type: ignore
        bundle_price_text = (
            f"**{bundle_price}** {(f'~~{bundle_base_price}~~' if bundle_base_price != bundle_price else '')}"
        )

        embed = discord.Embed(
            title=featured_bundle_title.format(bundle=name),  # type: ignore
            description=f'{vp_emoji} {bundle_price_text}' f' ({duration_text})',
            color=0xFD4554,
        )
        embed.set_image(url=bundle['icon'])  # type: ignore

        embed_list = []

        embeds = [embed]

        for items in sorted(bundle['items'], reverse=True, key=lambda c: c['base_price']):  # type: ignore
            item = GetItems.get_item_by_type(items['type'], items['uuid'])
            item_type = get_item_type(items['type'])
            emoji = GetEmoji.tier_by_bot(items['uuid'], self.bot) if item_type == 'Skins' else ''
            icon = item['icon'] if item_type != 'Player Cards' else item['icon']['large']
            color = 0xFD4554 if item_type == 'Skins' else 0x0F1923

            item_price = items['price']
            item_base_price = items['base_price']
            item_price_text = f"**{item_price}** {(f'~~{item_base_price}~~' if item_base_price != item_price else '')}"

            embed = self.base_embed(
                f"{emoji} {item['names'][self.language]}", f'**{vp_emoji}** {item_price_text}', icon, color
            )

            embeds.append(embed)

            if len(embeds) == 10:
                embed_list.append(embeds)
                embeds = []

        if len(embeds) != 0:
            embed_list.append(embeds)

        return embed_list

    def build_select(self) -> None:
        """Builds the select bundle"""
        for index, bundle in enumerate(sorted(self.entries, key=lambda c: c['names']['en-US']), start=1):  # type: ignore
            self.select_bundle.add_option(label=bundle['names'][self.language], value=index)  # type: ignore

    @ui.select(placeholder='Select a bundle:')
    async def select_bundle(self, interaction: Interaction, select: ui.Select):
        # TODO: fix freeze
        self.build_embeds(int(select.values[0]))
        self.fill_items()
        self.update_button()
        embeds = self.embeds[0]
        await interaction.response.edit_message(embeds=embeds, view=self)

    @ui.button(label='Back')
    async def back_button(self, interaction: Interaction, button: ui.Button):
        self.current_page = 0
        embeds = self.embeds[self.current_page]
        self.update_button()
        await interaction.response.edit_message(embeds=embeds, view=self)

    @ui.button(label='Next')
    async def next_button(self, interaction: Interaction, button: ui.Button):
        self.current_page = 1
        embeds = self.embeds[self.current_page]
        self.update_button()
        await interaction.response.edit_message(embeds=embeds, view=self)

    def update_button(self) -> None:
        """Updates the button"""
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
        self.back_button.disabled = self.current_page == 0

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message('This menus cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start(self) -> None:
        """Starts the bundle view"""

        if len(self.entries) == 1:
            self.build_embeds()
            self.fill_items()
            self.update_button()
            embeds = self.embeds[0]
            await self.interaction.followup.send(embeds=embeds, view=self)
            return
        elif len(self.entries) != 0:
            self.add_item(self.select_bundle)
            placeholder = self.response.get('DROPDOWN_CHOICE_TITLE')
            self.select_bundle.placeholder = placeholder
            self.build_select()
            await self.interaction.followup.send('\u200b', view=self)
            return

        not_found_bundle = self.response.get('NOT_FOUND_BUNDLE')
        raise ValorantBotError(not_found_bundle)

    async def start_furture(self) -> None:
        """Starts the featured bundle view"""

        BUNDLES = []
        FBundle = self.entries['FeaturedBundle']['Bundles']

        for fbd in FBundle:
            get_bundle = GetItems.get_bundle(fbd['DataAssetID'])

            bundle_payload = {
                'uuid': fbd['DataAssetID'],
                'icon': get_bundle['icon'],
                'names': get_bundle['names'],
                'duration': fbd['DurationRemainingInSeconds'],
                'items': [],
            }

            price = 0
            baseprice = 0

            for items in fbd['Items']:
                item_payload = {
                    'uuid': items['Item']['ItemID'],
                    'type': items['Item']['ItemTypeID'],
                    'item': GetItems.get_item_by_type(items['Item']['ItemTypeID'], items['Item']['ItemID']),
                    'amount': items['Item']['Amount'],
                    'price': items['DiscountedPrice'],
                    'base_price': items['BasePrice'],
                    'discount': items['DiscountPercent'],
                }
                price += int(items['DiscountedPrice'])
                baseprice += int(items['BasePrice'])
                bundle_payload['items'].append(item_payload)

            bundle_payload['price'] = price
            bundle_payload['base_price'] = baseprice

            BUNDLES.append(bundle_payload)

        if len(BUNDLES) > 1:
            return await self.interaction.followup.send('\u200b', view=SelectionFeaturedBundleView(BUNDLES, self))

        self.embeds = self.build_featured_bundle(BUNDLES[0])  # type: ignore
        self.fill_items()
        self.update_button()
        await self.interaction.followup.send(embeds=self.embeds[0], view=self)  # type: ignore


class SelectionFeaturedBundleView(ui.View):
    def __init__(self, bundles: list[dict[str, Any]], other_view: ui.View | BaseBundle | None = None):  # type: ignore
        self.bundles = bundles
        self.other_view = other_view
        super().__init__(timeout=120)
        self.__build_select()
        self.select_bundle.placeholder = self.other_view.response.get('DROPDOWN_CHOICE_TITLE')  # type: ignore

    def __build_select(self) -> None:
        """Builds the select bundle"""
        for index, bundle in enumerate(self.bundles):
            self.select_bundle.add_option(label=bundle['names'][str(VLR_locale)], value=str(index))

    @ui.select(placeholder='Select a bundle:')
    async def select_bundle(self, interaction: Interaction, select: ui.Select):
        value = select.values[0]
        bundle = self.bundles[int(value)]
        embeds = self.other_view.build_featured_bundle(bundle)  # type: ignore
        self.other_view.fill_items()  # type: ignore
        self.other_view.update_button()  # type: ignore
        await interaction.response.edit_message(content=None, embeds=embeds[0], view=self.other_view)  # type: ignore
