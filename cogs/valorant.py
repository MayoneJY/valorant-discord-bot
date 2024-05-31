from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Literal, Tuple

import discord
from discord import Interaction, app_commands, ui, User
from discord.ext import commands, tasks
from discord.utils import MISSING

from utils.checks import owner_only
from utils.errors import ValorantBotError
from utils.locale_v2 import ValorantTranslator
from utils.valorant import cache as Cache, useful, view as View
from utils.valorant.db import DATABASE
from utils.valorant.embed import Embed, GetEmbed
from utils.valorant.endpoint import API_ENDPOINT
from utils.valorant.local import ResponseLanguage
from utils.valorant.resources import setup_emoji
from utils.valorant.party import CustomParty
from utils.valorant.view import LoginView
import json, random

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot

rank_list = ['언랭', '미사용', '미사용', '아1', '아2', '아3', '브1', '브2', '브3', '실1', '실2', '실3', '골1', '골2', '골3', '플1', '플2', '플3', '다1', '다2', '다3', '초1', '초2', '초3', '불1', '불2', '불3', '레디']

    

    

class ValorantCog(commands.Cog, name='Valorant'):
    """Valorant API Commands"""

    def __init__(self, bot: ValorantBot) -> None:
        self.bot: ValorantBot = bot
        self.endpoint: API_ENDPOINT = MISSING
        self.db: DATABASE = MISSING
        self.reload_cache.start()
        self.party = {}
        self.commands_dict = {
            'login': self.login,
            'logout': self.logout,
            'store': self.store,
            'point': self.point,
            'party_create': self.party_create,
            'party_join': self.party_join,
            'party_voice_split': self.party_voice_split,
            'party_voice_rechange': self.party_voice_rechange,
            'party_room_create': self.party_room_create,
            'party_map_recommend': self.party_map_recommend,
            'battlepass': self.battlepass,
            'mission': self.mission,
            'nightmarket': self.nightmarket,
            'battlepass': self.battlepass,
            'bundle': self.bundle,
            'bundles': self.bundles,
            'cookies': self.cookies,
            'debug': self.debug,
        }

    def cog_unload(self) -> None:
        self.reload_cache.cancel()

    def funtion_reload_cache(self, force: bool = False) -> None:
        """Reload the cache"""
        with contextlib.suppress(Exception):
            cache = self.db.read_cache()
            valorant_version = Cache.get_valorant_version()
            if valorant_version != cache['valorant_version'] or force:
                Cache.get_cache()
                cache = self.db.read_cache()
                cache['valorant_version'] = valorant_version
                self.db.insert_cache(cache)
                print('Updated cache')

    @tasks.loop(minutes=30)
    async def reload_cache(self) -> None:
        """Reload the cache every 30 minutes"""
        self.funtion_reload_cache()

    @reload_cache.before_loop
    async def before_reload_cache(self) -> None:
        """Wait for the bot to be ready before reloading the cache"""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """When the bot is ready"""
        self.db = DATABASE()
        self.endpoint = API_ENDPOINT()

    async def get_endpoint(
        self,
        user_id: int,
        locale_code: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> API_ENDPOINT:
        """Get the endpoint for the user"""
        if username is not None and password is not None:
            auth = self.db.auth
            auth.locale_code = locale_code  # type: ignore
            data = await auth.temp_auth(username, password)
        elif username or password:
            raise ValorantBotError('Please provide both username and password!')
        else:
            data = await self.db.is_data(user_id, locale_code)  # type: ignore
        data['locale_code'] = locale_code  # type: ignore
        endpoint = self.endpoint
        endpoint.activate(data)  # type: ignore
        return endpoint

    @app_commands.command(description='Log in with your Riot acoount')
    @app_commands.describe(username='Input username', password='Input password')
    # @dynamic_cooldown(cooldown_5s)
    async def login(self, interaction: Interaction[ValorantBot], username: str, password: str) -> None:
        command_name = 'login'
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        user_id = interaction.user.id
        auth = self.db.auth
        auth.locale_code = interaction.locale  # type: ignore
        authenticate = await auth.authenticate(username, password)

        if authenticate['auth'] == 'response':  # type: ignore
            await interaction.response.defer(ephemeral=True)
            login = await self.db.login(user_id, authenticate, interaction.locale)  # type: ignore

            if login['auth']:  # type: ignore
                embed = Embed(f"{response.get('SUCCESS')} **{login['player']}!**")  # type: ignore
                return await interaction.followup.send(embed=embed, ephemeral=True)

            raise ValorantBotError(f"{response.get('FAILED')}")

        elif authenticate['auth'] == '2fa':  # type: ignore
            cookies = authenticate['cookie']  # type: ignore
            message = authenticate['message']  # type: ignore
            label = authenticate['label']  # type: ignore
            modal = View.TwoFA_UI(interaction, self.db, cookies, message, label, response)
            return await interaction.response.send_modal(modal)

    @app_commands.command(description='Logout and Delete your account from database')
    # @dynamic_cooldown(cooldown_5s)
    async def logout(self, interaction: Interaction[ValorantBot]) -> None:
        await interaction.response.defer(ephemeral=True)

        command_name = 'logout'
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        user_id = interaction.user.id
        if logout := self.db.logout(user_id, interaction.locale):  # type: ignore
            if logout:
                embed = Embed(response.get('SUCCESS'))
                return await interaction.followup.send(embed=embed, ephemeral=True)
            raise ValorantBotError(response.get('FAILED'))

    @app_commands.command(description='Shows your daily store in your accounts')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def store(self, interaction: Interaction[ValorantBot]) -> None:
        command_name = "store"
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # language
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        if not interaction.guild:
            raise ValorantBotError('This command can only be used in a server')

        # setup emoji
        await setup_emoji(self.bot, interaction.guild, interaction.locale)  # type: ignore

        # get endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore

        # fetch skin price
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)

        # data
        data = endpoint.store_fetch_storefront()
        embeds = GetEmbed.store(endpoint.player, data, response, self.bot)
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds))

    @app_commands.command(description='View your remaining Valorant and Riot Points (VP/RP)')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def point(self, interaction: Interaction[ValorantBot]) -> None:
        # check if user is logged in

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        command_name = 'point'
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        if not interaction.guild:
            raise ValorantBotError('This command can only be used in a server')

        # setup emoji
        await setup_emoji(self.bot, interaction.guild, interaction.locale.value)

        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, locale_code=interaction.locale.value)

        # data
        data = endpoint.store_fetch_wallet()
        embed = GetEmbed.point(endpoint.player, data, response, self.bot)

        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]))

    @app_commands.command(name="파티_생성", description='View your player profile')
    @app_commands.guild_only()
    async def party_create(self, interaction: Interaction[ValorantBot]) -> None:
            # check if user is logged in

        self.party[interaction.channel] = None

        try:
            existing_role = discord.utils.get(interaction.guild.roles, name="VAL_1") # type: ignore
            existing_role2 = discord.utils.get(interaction.guild.roles, name="VAL_2") # type: ignore
            if existing_role:
                # 모든 파티원을 제거
                for member in existing_role.members:
                    await member.remove_roles(existing_role)
            else:
                await interaction.guild.create_role(name="VAL_1") # type: ignore
            if existing_role2:
                # 모든 파티원을 제거
                for member in existing_role2.members:
                    await member.remove_roles(existing_role2)
            else:
                await interaction.guild.create_role(name="VAL_2") # type: ignore
        except Exception as e:
            raise ValorantBotError('역할 관리 권한이 없는 거 같아요.. \n역할 관리 권한을 부여해주세요! :sob:')
            return
        
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            self.party[interaction.channel] = CustomParty(self, interaction, self.bot)
            await self.party[interaction.channel].initialize()
        except Exception as e:
            print(e)
            raise ValorantBotError('테스트중인 커맨드입니다. 빠르게 사용할 수 있게 만들게요! :yum:')

    @app_commands.command(name="파티_참여", description='내전에 참여합니다.')
    @app_commands.describe(tier="티어를 입력하세요.(예: '플3', '언랭', '레디')")
    async def party_join(self, interaction: Interaction[ValorantBot], tier: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if interaction.channel not in self.party:
            await interaction.followup.send('파티가 생성되지 않았습니다.', ephemeral=True)
            return

        user = interaction.user
        player_id = str(user.name)
        rank = rank_list.index(tier)
        emoji = discord.utils.get(self.bot.emojis, name=f'competitivetiers{rank}') # type: ignore
        if rank == -1:
            return
        if await self.party[interaction.channel].add_player(player_id, {"displayName": str(user.global_name), "rank": rank, "user": user, "val_id": "test_val_id", "emoji": emoji}):
            await interaction.followup.send('Joined the party!', ephemeral=True)
        else:
            await interaction.followup.send('Failed to join the party.', ephemeral=True)

    async def party_join2(self, interaction: Interaction[ValorantBot], tier: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        user = interaction.user
        player_id = str(user.name)
        rank = rank_list.index(tier)
        emoji = discord.utils.get(self.bot.emojis, name=f'competitivetiers{rank}') # type: ignore
        if rank == -1:
            return
        if await self.party[interaction.channel].add_player(player_id, {"displayName": str(user.global_name), "rank": rank, "user": user, "val_id": "test_val_id", "emoji": emoji}):
            await interaction.followup.send('Joined the party!', ephemeral=True)
        else:
            await interaction.followup.send('Failed to join the party.', ephemeral=True)

    
    @app_commands.command(name="파티_채널_이동", description='내전 음성 채널을 나눕니다.')
    @app_commands.guild_only()
    async def party_voice_split(self, interaction: Interaction[ValorantBot]) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if interaction.channel not in self.party:
            raise ValorantBotError('파티가 생성되지 않았습니다.')
            return
        
        if len(self.party[interaction.channel].voice_channel) != 2:
            raise ValorantBotError('음성 채널을 선택하지 않았습니다.')
            return
        
        if len(self.party[interaction.channel].best_team1) == 0:
            raise ValorantBotError('팀을 나누지 않았습니다.')
            return

        await self.party[interaction.channel].move_users(interaction)

    
    @app_commands.command(name="파티_채널_원위치", description='내전 음성 채팅을 다시 모입니다.')
    @app_commands.guild_only()
    async def party_voice_rechange(self, interaction: Interaction[ValorantBot]) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if interaction.channel not in self.party:
            raise ValorantBotError('파티가 생성되지 않았습니다.')
            return
        
        if len(self.party[interaction.channel].voice_channel) != 2:
            raise ValorantBotError('음성 채널을 선택하지 않았습니다.')
            return
        
        if len(self.party[interaction.channel].best_team1) == 0:
            raise ValorantBotError('팀을 나누지 않았습니다.')
            return

        await self.party[interaction.channel].re_change(interaction)

    
    @app_commands.command(name="파티_방_생성", description='내전 방을 생성합니다.')
    @app_commands.guild_only()
    async def party_room_create(self, interaction: Interaction[ValorantBot]) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()

        if interaction.channel not in self.party:
            raise ValorantBotError('파티가 생성되지 않았습니다.')
            return
        
        if len(self.party[interaction.channel].best_team1) == 0:
            raise ValorantBotError('팀을 나누지 않았습니다.')
            return
        
        if interaction.user.name not in self.party[interaction.channel].players:
            raise ValorantBotError(f'{interaction.user.mention}님이 파티에 참여하지 않아 방을 생성할 수 없습니다.')

        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore

        try:
            partyid = endpoint.fetch_party_id()
            if not partyid:
                raise ValorantBotError(f'{interaction.user.mention}님이 `발로란트`에 로그인되어 있지 않습니다.')
                return
        except Exception as e:
            print(e)
            raise ValorantBotError(f'파티 방 생성에 실패했습니다.\n{e}')
            return
        players, team1, team2 = await self.party[interaction.channel].invite_room(interaction, endpoint.player) # list[puuid]

        print("파티 생성")

        try:
            endpoint.set_party_accessibility(partyid)
        except Exception as e:
            print(e)
            raise ValorantBotError(f'파티 공개 파티 전환에 실패했습니다.\n{e}')
            return
        print("파티 공개 파티 전환")

        try:
            code = endpoint.generate_party_code(partyid)
            if code:
                await interaction.followup.send(f'파티 코드: {code}')
        except Exception as e:
            print(e)
            raise ValorantBotError(f'파티 코드 생성에 실패했습니다.\n{e}')
            return
        print("파티 코드 생성")
        try:
            data = endpoint.fetch_custom_game_map()

            map = random.choice(data) # type: ignore
        except Exception as e:
            map = None
            print(e)
            raise ValorantBotError(f'맵 추천에 실패했습니다.\n{e}')

        try:
            await endpoint.set_change_queue(partyid, endpoint.headers, map['url'])
            await interaction.followup.send(f'맵: {map["name"]}')
        except Exception as e:
            print(e)
            raise ValorantBotError(f'커스텀게임 생성에 실패했습니다.\n{e}')
            return
        print("커스텀게임 생성")

        try:
            await endpoint.join_party_code(interaction, players, code)
        except Exception as e:
            print(e)
            raise ValorantBotError(f'팀원이 파티에 참가하지 못했습니다.\n{e}')
            return
        print("팀원이 파티에 참가")

        try:
            endpoint.change_custom_game_team(partyid, team1, team2 ,endpoint.headers)
        except Exception as e:
            print(e)
            raise ValorantBotError(f'팀 변경에 실패했습니다.\n{e}')
            return
        print("팀 변경")


    @app_commands.command(name="맵_추천", description='내전 맵을 추천합니다.')
    @app_commands.guild_only()
    async def party_map_recommend(self, interaction: Interaction[ValorantBot]) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()

        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale) # type: ignore
        
        data = endpoint.fetch_custom_game_map()

        result = random.choice(data) # type: ignore
        

        if data:
            await interaction.followup.send(f'추천 맵: {result["name"]}')
        else:
            await interaction.followup.send('맵 추천에 실패했습니다.')
    
    # @app_commands.command(name="파티_방_팀변경", description='내전 방 정보를 확인합니다.')
    # @app_commands.describe(test="test")
    # @app_commands.guild_only()
    # async def party_room_team_change(self, interaction: Interaction[ValorantBot], test: str) -> None:
    #     await interaction.response.defer()
    #     endpoint = await self.get_endpoint(interaction.user.id, interaction.locale) # type: ignore
    #     partyid = endpoint.fetch_party_id()
    #     endpoint.change_custom_game_team(partyid, endpoint.puuid ,endpoint.headers, test)



    # @app_commands.command(name="파티_방_정보", description='내전 방 정보를 확인합니다.')
    # @app_commands.guild_only()
    # async def party_room_info(self, interaction: Interaction[ValorantBot]) -> None:
    #     await interaction.response.defer()
    #     endpoint = await self.get_endpoint(interaction.user.id, interaction.locale) # type: ignore
    #     partyid = endpoint.fetch_party_id()
    #     # endpoint.fetch_party_custom_game_config(partyid, endpoint.puuid ,endpoint.headers)
    #     # endpoint.set_custom_game_start(partyid, endpoint.headers)
    #     await endpoint.set_change_queue(partyid, endpoint.headers)
    

    async def get_player_info(self, interaction: Interaction[ValorantBot]) -> Tuple[str, str]:
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore
        return endpoint.player, endpoint.puuid
    
    async def get_player_headers(self, interaction: Interaction[ValorantBot]) -> dict[str, str]:
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore
        return endpoint.headers


    async def get_tier_rank(self, interaction: Interaction[ValorantBot]) -> int:
        
        # check if user is logged in

        # response = ResponseLanguage(interaction.command.name, interaction.locale)  # type: ignore

        if not interaction.guild:
            raise ValorantBotError('This command can only be used in a server')

        # setup emoji
        await setup_emoji(self.bot, interaction.guild, interaction.locale)  # type: ignore

        # get endpoint
        if await self.db.is_login(interaction.user.id, interaction.locale, True): # type: ignore
            endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore
        else:
            # await interaction.followup.send(embed=Embed(str(e)), ephemeral=True)
            view = LoginView(self)
            msg = await interaction.followup.send(content="`비로그인시 자동 입장기능 비활성화.`", view=view, ephemeral=True)
            view.init(msg)
            return -1

        # data
        try:
            data = endpoint.get_player_tier_rank() # dict[str, Any]
        except:
            data = 0

        return int(data)


    @app_commands.command(description='View your daily/weekly mission progress')
    # @dynamic_cooldown(cooldown_5s)
    async def mission(self, interaction: Interaction[ValorantBot]) -> None:
        # check if user is logged in

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        command_name = 'mission'
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore

        # data
        data = endpoint.fetch_contracts()
        embed = GetEmbed.mission(endpoint.player, data, response)

        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]))

    @app_commands.command(description='Show skin offers on the nightmarket')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def nightmarket(self, interaction: Interaction[ValorantBot]) -> None:
        # check if user is logged in

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            raise ValorantBotError('This command can only be used in a server')

        # setup emoji
        await setup_emoji(self.bot, interaction.guild, interaction.locale)  # type: ignore

        # language
        command_name = 'nightmarket'
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore

        # fetch skin price
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)

        # data
        data = endpoint.store_fetch_storefront()
        embeds = GetEmbed.nightmarket(endpoint.player, data, self.bot, response)

        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds))  # type: ignore

    @app_commands.command(description='View your battlepass current tier')
    # @dynamic_cooldown(cooldown_5s)
    async def battlepass(self, interaction: Interaction[ValorantBot]) -> None:
        # check if user is logged in

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        command_name = 'battlepass'
        response = ResponseLanguage(command_name, interaction.locale)  # type: ignore

        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)  # type: ignore

        # data
        data = endpoint.fetch_contracts()
        content = endpoint.fetch_content()
        season = useful.get_season_by_content(content)

        embed = GetEmbed.battlepass(endpoint.player, data, season, response)

        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]))

    # inspired by https://github.com/giorgi-o
    @app_commands.command(description='inspect a specific bundle')
    @app_commands.describe(bundle='The name of the bundle you want to inspect!')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def bundle(self, interaction: Interaction[ValorantBot], bundle: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()

        command_name = 'bundle'
        response = ResponseLanguage(command_name, interaction.locale.value)  # type: ignore

        if not interaction.guild:
            raise ValorantBotError('This command can only be used in a server')

        # setup emoji
        await setup_emoji(self.bot, interaction.guild, interaction.locale.value)

        # cache
        cache = self.db.read_cache()

        # default language language
        default_language = 'en-US'

        # find bundle
        find_bundle_en_US = [
            cache['bundles'][i]
            for i in cache['bundles']
            if bundle.lower() in cache['bundles'][i]['names'][default_language].lower()
        ]
        find_bundle_locale = [
            cache['bundles'][i]
            for i in cache['bundles']
            if bundle.lower() in cache['bundles'][i]['names'][str(VLR_locale)].lower()
        ]
        find_bundle = (find_bundle_en_US if len(find_bundle_en_US) > 0 else find_bundle_locale)[:25]

        # bundle view
        view = View.BaseBundle(interaction, find_bundle, response)  # type: ignore
        await view.start()

    # inspired by https://github.com/giorgi-o
    @app_commands.command(description='Show the current featured bundles')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def bundles(self, interaction: Interaction[ValorantBot]) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()

        command_name = 'bundles'
        response = ResponseLanguage(command_name, interaction.locale.value)  # type: ignore

        if not interaction.guild:
            raise ValorantBotError('This command can only be used in a server')

        # setup emoji
        await setup_emoji(self.bot, interaction.guild, interaction.locale.value)

        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale.value)

        # data
        bundle_entries = endpoint.store_fetch_storefront()

        # bundle view
        view = View.BaseBundle(interaction, bundle_entries, response)
        await view.start_furture()

    # credit https://github.com/giorgi-o
    # https://github.com/giorgi-o/SkinPeek/wiki/How-to-get-your-Riot-cookies
    @app_commands.command()
    @app_commands.describe(cookie='Your cookie')
    async def cookies(self, interaction: Interaction[ValorantBot], cookie: str) -> None:
        """Login to your account with a cookie"""

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # language
        command_name = 'cookies'
        response = ResponseLanguage(command_name, interaction.locale.value)  # type: ignore

        login = await self.db.cookie_login(interaction.user.id, cookie, interaction.locale.value)

        if login['auth']:  # type: ignore
            embed = Embed(f"{response.get('SUCCESS')} **{login['player']}!**")  # type: ignore
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        view = ui.View()
        view.add_item(ui.Button(label='Tutorial', emoji='🔗', url='https://youtu.be/cFMNHEHEp2A'))
        await interaction.followup.send(f"{response.get('FAILURE')}", view=view, ephemeral=True)


    # ---------- ROAD MAP ---------- #

    # @app_commands.command()
    # async def contract(self, interaction: Interaction) -> None:
    #     # change agent contract

    # @app_commands.command()
    # async def party(self, interaction: Interaction) -> None:
    #     # curren party
    #     # pick agent
    #     # current map

    # @app_commands.command()
    # async def career(self, interaction: Interaction) -> None:
    #     # match history

    # ---------- DEBUGs ---------- #

    @app_commands.command(description='The command debug for the bot')
    @app_commands.describe(bug='The bug you want to fix')
    @app_commands.guild_only()
    @owner_only()
    async def debug(
        self,
        interaction: Interaction[ValorantBot],
        bug: Literal['Skin price not loading', 'Emoji not loading', 'Cache not loading'],
    ) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        command_name = 'debug'
        response = ResponseLanguage(command_name, interaction.locale.value)  # type: ignore

        if bug == 'Skin price not loading':
            # endpoint
            endpoint = await self.get_endpoint(interaction.user.id, interaction.locale.value)

            # fetch skin price
            skin_price = endpoint.store_fetch_offers()
            self.db.insert_skin_price(skin_price, force=True)

        elif bug == 'Emoji not loading':
            if not interaction.guild:
                raise ValorantBotError('This command can only be used in a server')

            await setup_emoji(self.bot, interaction.guild, interaction.locale.value, force=True)

        elif bug == 'Cache not loading':
            self.funtion_reload_cache(force=True)

        success: str = response.get('SUCCESS', 'success')
        await interaction.followup.send(embed=Embed(success.format(bug=bug)))


async def setup(bot: ValorantBot) -> None:
    await bot.add_cog(ValorantCog(bot))
    
