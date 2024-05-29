# inspired by https://github.com/colinhartigan/

from __future__ import annotations

# Standard
import json
from typing import Any

import requests

from ..errors import HandshakeError, ResponseError
from .local import LocalErrorResponse

# Local
from .resources import (
    base_endpoint,
    base_endpoint_glz,
    base_endpoint_shared,
    region_shard_override,
    shard_region_override,
)

import asyncio

class API_ENDPOINT:
    def __init__(self) -> None:
        from .auth import Auth

        self.auth = Auth()

        # self.headers = {}
        # self.puuid = ''
        # self.player = ''
        # self.region = ''
        # self.shard = ''
        # self.pd = ''
        # self.shared = ''
        # self.glz = ''

        # client platform
        self.client_platform = 'ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9'

        # language
        self.locale_code = 'en-US'

    def activate(self, auth: dict[str, Any]) -> None:
        """activate api"""

        try:
            headers = self.__build_headers(auth['headers'])
            self.headers = headers
            # self.cookie = auth['cookie']
            self.puuid = auth['puuid']
            self.region = auth['region']
            self.player = auth['player_name']
            self.locale_code = auth.get('locale_code', 'en-US')
            self.headers = auth['headers']
            self.__format_region()
            self.__build_urls()
        except Exception as e:
            print(e)
            raise HandshakeError(self.locale_response().get('FAILED_ACTIVE')) from e

    def locale_response(self) -> dict[str, Any]:
        """This function is used to check if the local response is enabled."""
        self.response = LocalErrorResponse('API', self.locale_code)
        return self.response

    # async def refresh_token(self) -> None:
    # cookies = self.cookie
    # cookies, accessToken, emt = await self.auth.redeem_cookies(cookies)

    # self.__build_headers()

    def fetch(self, endpoint: str = '/', url: str = 'pd', errors: dict[str, Any] | None = None, header: dict[str, Any] | None = None) -> dict[str, Any]:
        """fetch data from the api"""

        self.locale_response()

        endpoint_url = getattr(self, url)

        data = None
        if header is None:
            r = requests.get(f'{endpoint_url}{endpoint}', headers=self.headers)
        else:
            r = requests.get(f'{endpoint_url}{endpoint}', headers=header)

        try:  # noqa: SIM105
            data = json.loads(r.text)
        except Exception:
            pass

        if 'httpStatus' not in data:  # type: ignore
            return data  # type: ignore

        if r.status_code == 400:
            response = LocalErrorResponse('AUTH', self.locale_code)
            raise ResponseError(response.get('COOKIES_EXPIRED'))
            # await self.refresh_token()
            # return await self.fetch(endpoint=endpoint, url=url, errors=errors)
        return {}
    
    def fetch2(self, endpoint: str = '/', url: str = 'pd', errors: dict[str, Any] | None = None, header: dict[str, Any] | None = None) -> dict[str, Any]:
        """fetch data from the api"""


        endpoint_url = "https://glz-kr-1.kr.a.pvp.net"

        data = None

        if header is None:
            r = requests.get(f'{endpoint_url}{endpoint}', headers=self.headers)
        else:
            r = requests.get(f'{endpoint_url}{endpoint}', headers=header)

        try:  # noqa: SIM105
            data = json.loads(r.text)
        except Exception:
            pass

        if 'httpStatus' not in data:  # type: ignore
            return data  # type: ignore
        
        if r.status_code == 400:
            response = LocalErrorResponse('AUTH', self.locale_code)
            raise ResponseError(response.get('COOKIES_EXPIRED'))
            # await self.refresh_token()
            # return await self.fetch(endpoint=endpoint, url=url, errors=errors)
        return {}
        

    def put(
        self,
        endpoint: str = '/',
        url: str = 'pd',
        data: dict[str, Any] | list[Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> Any:
        """put data to the api"""

        self.locale_response()

        endpoint_url = getattr(self, url)

        r = requests.put(f'{endpoint_url}{endpoint}', headers=self.headers, data=data)
        data = json.loads(r.text)

        if data is None:
            raise ResponseError(self.response.get('REQUEST_FAILED'))

        return data
    
    def put2(
        self,
        endpoint: str = '/',
        url: str = 'pd',
        data: dict[str, Any] | list[Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> Any:
        """put data to the api"""

        endpoint_url = "https://glz-kr-1.kr.a.pvp.net"

        r = requests.put(f'{endpoint_url}{endpoint}', headers=self.headers, data=data)
        data = json.loads(r.text)

        if data is None:
            raise ResponseError(self.response.get('REQUEST_FAILED'))

        return data
    
    def post(
        self,
        endpoint: str = '/',
        url: str = 'pd',
        data: dict[str, Any] | list[Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> Any:
        """post data to the api"""

        self.locale_response()

        endpoint_url = getattr(self, url)

        r = requests.post(f'{endpoint_url}{endpoint}', headers=self.headers, data=data)
        data = json.loads(r.text)

        if data is None:
            raise ResponseError(self.response.get('REQUEST_FAILED'))

        return data
    
    def post2(
        self,
        endpoint: str = '/',
        url: str = 'pd',
        data: dict[str, Any] | list[Any] | None = None,
        errors: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None
    ) -> Any:
        """post data to the api"""

        endpoint_url = "https://glz-kr-1.kr.a.pvp.net"
        if headers is not None:
            r = requests.post(f'{endpoint_url}{endpoint}', headers=headers, json=data)
        else:
            r = requests.post(f'{endpoint_url}{endpoint}', headers=self.headers, json=data)
        data = json.loads(r.text)

        if data is None:
            raise ResponseError(self.response.get('REQUEST_FAILED'))

        return data
    

    # contracts endpoints

    def fetch_contracts(self) -> dict[str, Any]:
        """
        Contracts_Fetch
        Get a list of contracts and completion status including match history
        """
        data = self.fetch(endpoint=f'/contracts/v1/contracts/{self.puuid}', url='pd')
        return data

    # PVP endpoints

    def fetch_content(self) -> dict[str, Any]:
        """
        Content_FetchContent
        Get names and ids for game content such as agents, maps, guns, etc.
        """
        data = self.fetch(endpoint='/content-service/v3/content', url='shared')
        return data

    def fetch_account_xp(self) -> dict[str, Any]:
        """
        AccountXP_GetPlayer
        Get the account level, XP, and XP history for the active player
        """
        data = self.fetch(endpoint=f'/account-xp/v1/players/{self.puuid}', url='pd')
        return data

    def fetch_player_mmr(self, puuid: str | None = None) -> dict[str, Any]:
        puuid = self.__check_puuid(puuid)
        data = self.fetch(endpoint=f'/mmr/v1/players/{puuid}', url='pd')
        return data

    def fetch_name_by_puuid(self, puuid: str | None = None) -> dict[str, Any]:
        """
        Name_service
        get player name tag by puuid
        NOTE:
        format ['PUUID']
        """
        if puuid is None:
            puuids = [self.__check_puuid()]
        elif puuid is not None and type(puuid) is str:
            puuids = [puuid]
        data = self.put(endpoint='/name-service/v2/players', url='pd', data=puuids)
        return data

    def fetch_player_loadout(self) -> dict[str, Any]:
        """
        playerLoadoutUpdate
        Get the player's current loadout
        """
        data = self.fetch(endpoint=f'/personalization/v2/players/{self.puuid}/playerloadout', url='pd')
        return data

    def put_player_loadout(self, loadout: dict[str, Any]) -> dict[str, Any]:
        """
        playerLoadoutUpdate
        Use the values from `fetch_player_loadout` excluding properties like `subject` and `version.` Loadout changes take effect when starting a new game
        """
        data = self.put(endpoint=f'/personalization/v2/players/{self.puuid}/playerloadout', url='pd', data=loadout)
        return data

    # store endpoints

    def store_fetch_offers(self) -> dict[str, Any]:
        """
        Store_GetOffers
        Get prices for all store items
        """
        data = self.fetch('/store/v1/offers/', url='pd')
        return data

    def store_fetch_storefront(self) -> dict[str, Any]:
        """
        Store_GetStorefrontV2
        Get the currently available items in the store
        """
        data = self.fetch(f'/store/v2/storefront/{self.puuid}', url='pd')
        return data

    def store_fetch_wallet(self) -> dict[str, Any]:
        """
        Store_GetWallet
        Get amount of Valorant points and Radiant points the player has
        Valorant points have the id 85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741 and Radiant points have the id e59aa87c-4cbf-517a-5983-6e81511be9b7
        """
        data = self.fetch(f'/store/v1/wallet/{self.puuid}', url='pd')
        return data

    def store_fetch_order(self, order_id: str) -> dict[str, Any]:
        """
        Store_GetOrder
        {order id}: The ID of the order. Can be obtained when creating an order.
        """
        data = self.fetch(f'/store/v1/order/{order_id}', url='pd')
        return data

    def store_fetch_entitlements(self, item_type: dict) -> dict[str, Any]:
        """
        Store_GetEntitlements
        List what the player owns (agents, skins, buddies, ect.)
        Correlate with the UUIDs in `fetch_content` to know what items are owned.
        Category names and IDs:

        `ITEMTYPEID:`
        '01bb38e1-da47-4e6a-9b3d-945fe4655707': 'Agents'\n
        'f85cb6f7-33e5-4dc8-b609-ec7212301948': 'Contracts',\n
        'd5f120f8-ff8c-4aac-92ea-f2b5acbe9475': 'Sprays',\n
        'dd3bf334-87f3-40bd-b043-682a57a8dc3a': 'Gun Buddies',\n
        '3f296c07-64c3-494c-923b-fe692a4fa1bd': 'Player Cards',\n
        'e7c63390-eda7-46e0-bb7a-a6abdacd2433': 'Skins',\n
        '3ad1b2b2-acdb-4524-852f-954a76ddae0a': 'Skins chroma',\n
        'de7caa6b-adf7-4588-bbd1-143831e786c6': 'Player titles',\n
        """
        data = self.fetch(endpoint=f'/store/v1/entitlements/{self.puuid}/{item_type}', url='pd')
        return data

    # useful endpoints

    def fetch_mission(self) -> dict[str, Any]:
        """
        Get player daily/weekly missions
        """
        data = self.fetch_contracts()
        mission = data['Missions']
        return mission

    def get_player_level(self) -> dict[str, Any]:
        """
        Aliases `fetch_account_xp` but received a level
        """
        data = self.fetch_account_xp()['Progress']['Level']
        return data

    def get_player_tier_rank(self, puuid: str | None = None) -> str:
        """
        get player current tier rank
        """
        data = self.fetch_player_mmr(puuid)
        season_id = data['LatestCompetitiveUpdate']['SeasonID']
        if len(season_id) == 0:
            season_id = self.__get_live_season()
        current_season = data['QueueSkills']['competitive']['SeasonalInfoBySeasonID']
        current_Tier = current_season[season_id]['CompetitiveTier']
        return current_Tier
    
    # party endpoints

    def fetch_party_id(self) -> str | None:
        """
        Get the party ID of the player
        """
        r = requests.get(f'https://glz-kr-1.kr.a.pvp.net/parties/v1/players/{self.puuid}?aresriot.aws-rclusterprod-ape1-1.ap-gp-hongkong-1=186&aresriot.aws-rclusterprod-ape1-1.ap-gp-hongkong-awsedge-1=122&aresriot.aws-rclusterprod-apne1-1.ap-gp-tokyo-1=147&aresriot.aws-rclusterprod-apne1-1.ap-gp-tokyo-awsedge-1=151&aresriot.aws-rclusterprod-aps1-1.ap-gp-mumbai-awsedge-1=22&aresriot.aws-rclusterprod-apse1-1.ap-gp-singapore-1=77&aresriot.aws-rclusterprod-apse1-1.ap-gp-singapore-awsedge-1=79&aresriot.aws-rclusterprod-apse2-1.ap-gp-sydney-1=258&aresriot.aws-rclusterprod-apse2-1.ap-gp-sydney-awsedge-1=170&preferredgamepods=aresriot.aws-rclusterprod-aps1-1.ap-gp-mumbai-awsedge-1', headers=self.headers)

        data = json.loads(r.text)
        if 'errorCode' in data:
            if data['errorCode'] == 'PLAYER_DOES_NOT_EXIST':
                return None
        # if 'httpStatus' not in data:  # type: ignore
        #     return data  # type: ignore
        
        # data = self.fetch(endpoint=f'/parties/v1/players/{self.puuid}', url='pd')
        # data = self.fetch(endpoint=f'https://glz-kr-1.kr.a.pvp.net/parties/v1/players/{self.puuid}?aresriot.aws-rclusterprod-ape1-1.ap-gp-hongkong-1=186&aresriot.aws-rclusterprod-ape1-1.ap-gp-hongkong-awsedge-1=122&aresriot.aws-rclusterprod-apne1-1.ap-gp-tokyo-1=147&aresriot.aws-rclusterprod-apne1-1.ap-gp-tokyo-awsedge-1=151&aresriot.aws-rclusterprod-aps1-1.ap-gp-mumbai-awsedge-1=22&aresriot.aws-rclusterprod-apse1-1.ap-gp-singapore-1=77&aresriot.aws-rclusterprod-apse1-1.ap-gp-singapore-awsedge-1=79&aresriot.aws-rclusterprod-apse2-1.ap-gp-sydney-1=258&aresriot.aws-rclusterprod-apse2-1.ap-gp-sydney-awsedge-1=170&preferredgamepods=aresriot.aws-rclusterprod-aps1-1.ap-gp-mumbai-awsedge-1')

        return data['CurrentPartyID']
    
    def request_party_invite(self, party_id: str, players: list) -> None:
        """
        Request an invite to a party
        """
        for player in players:
            self.fetch(endpoint=f'/parties/v1/parties/{party_id}/invites/name/{player["name"]}/tag/{player["tag"]}', url='pd')

    def invite_party(self, party_id: str, players: list) -> None:
        """
        Set a party join code
        """
        for player in players:
            self.post2(endpoint=f'/parties/v1/parties/{party_id}/invites/name/{player["username"]}/tag/{player["tag"]}', url='pd')
        
    
    def set_party_accessibility(self, party_id: str) -> None:
        """
        Set party accessibility
        """
        data = self.post2(endpoint=f'/parties/v1/parties/{party_id}/accessibility', url='pd', data={"accessibility": "OPEN"})
        print(data)


    def generate_party_code(self, party_id: str) -> str:
        """
        Generate a party code
        """
        data = self.post2(endpoint=f'/parties/v1/parties/{party_id}/invitecode', url='pd')
        return data['InviteCode']
    
    def request_party_join(self, party_id: str, players: list) -> None:
        """
        Request to join a party
        """
        for player in players:
            headers = self.headers
            headers['Authorization'] = player['headers']['Authorization']
            headers['X-Riot-Entitlements-JWT'] = player['headers']['X-Riot-Entitlements-JWT']
            self.post2(endpoint=f'/parties/v1/parties/{party_id}/request', url='pd', headers=headers)

    def join_party_code(self, players: list, code: str) -> None:
        """
        Join a party using a code
        """
        for player in players:
            headers = self.headers
            headers['Authorization'] = player['headers']['Authorization']
            headers['X-Riot-Entitlements-JWT'] = player['headers']['X-Riot-Entitlements-JWT']
            data = self.post2(endpoint=f'/parties/v1/players/joinbycode/{code}', url='pd')

    def change_custom_game_team(self, party_id: str, team1: list, team2: list, headers: dict[str, Any]) -> None:
        """
        Change the team of a player in a custom game
        """
        def set_team(player: dict, team: str):
            if 'headers' in player:
                header = self.headers
                header['Authorization'] = player['headers']['Authorization']
                header['X-Riot-Entitlements-JWT'] = player['headers']['X-Riot-Entitlements-JWT']
                json_data = {
                    "playerToPutOnTeam": player['puuid']
                }
                self.post2(endpoint=f'/parties/v1/parties/{party_id}/customgamemembership/{team}', url='pd', headers=header, data=json_data)
                
        for player in team1:
            set_team(player, 'TeamSpectate')
        for player in team2:
            set_team(player, 'TeamSpectate')


        for player in team1:
            set_team(player, 'TeamOne')
        for player in team2:
            set_team(player, 'TeamTwo')
    
    def set_custom_game_start(self, party_id: str, headers: dict[str, Any]) -> dict[str, Any]:
        """
        Start a custom game
        """
        header = self.headers
        header['Authorization'] = headers['Authorization']
        header['X-Riot-Entitlements-JWT'] = headers['X-Riot-Entitlements-JWT']
        json_data = {}
        data = self.post2(endpoint=f'/parties/v1/parties/{party_id}/customgamesettings', url='pd', headers=header, data=json_data)
        print(data)
        return data
    
    async def set_change_queue(self, party_id: str, headers: dict[str, Any]) -> None:
        """
        Change the queue of the party
        """
        header = self.headers
        header['Authorization'] = headers['Authorization']
        header['X-Riot-Entitlements-JWT'] = headers['X-Riot-Entitlements-JWT']
        json_data = {
            "Map": "/Game/Maps/Ascent/Ascent",
            "Mode": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
            "UseBots": False,
            "GamePod": "aresriot.aws-apne2-prod.kr-gp-seoul-1",
            "GameRules": {
                "AllowGameModifiers": "false",
                "PlayOutAllRounds": "true",
                "SkipMatchHistory": "true",
                "TournamentMode": "true",
                "IsOvertimeWinByTwo": "true"
            }
        }
        self.post2(endpoint=f'/parties/v1/parties/{party_id}/makecustomgame', url='pd', headers=header)
        self.post2(endpoint=f'/parties/v1/parties/{party_id}/customgamesettings', url='pd', headers=header, data=json_data)

    # local utility functions

    def __get_live_season(self) -> str:
        """Get the UUID of the live competitive season"""
        content = self.fetch_content()
        season_id = [season['ID'] for season in content['Seasons'] if season['IsActive'] and season['Type'] == 'act']
        if not season_id:
            return self.fetch_player_mmr()['LatestCompetitiveUpdate']['SeasonID']
        return season_id[0]

    def __check_puuid(self, puuid: str | None = None) -> str:
        """If puuid passed into method is None make it current user's puuid"""
        return self.puuid if puuid is None else puuid

    def __build_urls(self) -> None:
        """
        generate URLs based on region/shard
        """
        self.pd = base_endpoint.format(shard=self.shard)
        self.shared = base_endpoint_shared.format(shard=self.shard)
        self.glz = base_endpoint_glz.format(region=self.region, shard=self.shard)

    def __build_headers(self, headers: dict[str, Any]) -> dict[str, Any]:
        """build headers"""
        headers['X-Riot-ClientPlatform'] = self.client_platform
        headers['X-Riot-ClientVersion'] = self._get_client_version()
        return headers

    def __format_region(self) -> None:
        """Format region to match from user input"""

        self.shard = self.region
        if self.region in region_shard_override:
            self.shard = region_shard_override[self.region]
        if self.shard in shard_region_override:
            self.region = shard_region_override[self.shard]

    def _get_client_version(self) -> str:
        """Get the client version"""
        r = requests.get('https://valorant-api.com/v1/version')
        data = r.json()['data']
        return f"{data['branch']}-shipping-{data['buildVersion']}-{data['version'].split('.')[3]}"  # return formatted version string

    def _get_valorant_version(self) -> str | None:
        """Get the valorant version"""
        r = requests.get('https://valorant-api.com/v1/version')
        if r.status_code != 200:
            return None
        data = r.json()['data']
        return data['version']
