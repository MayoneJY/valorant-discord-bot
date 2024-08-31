# from __future__ import annotations

# Standard
from secrets import token_urlsafe
import contextlib
import ctypes
import json
import re
import ssl
from datetime import datetime, timedelta
import sys
from typing import Any, Optional
import warnings

# Third
import aiohttp
import requests

from ..errors import AuthenticationError
from ..locale_v2 import ValorantTranslator
from ..errors import ValorantBotError

# Local
from .local import LocalErrorResponse, ResponseLanguage


vlr_locale = ValorantTranslator()


def _extract_tokens(data: str) -> str:
    """Extract tokens from data"""

    pattern = re.compile(
        r'access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)'
    )
    response = pattern.findall(data['response']['parameters']['uri'])[0]  # type: ignore
    return response


def _extract_tokens_from_uri(url: str) -> tuple[str, str]:
    try:
        access_token = url.split('access_token=')[1].split('&scope')[0]
        token_id = url.split('id_token=')[1].split('&')[0]
        return access_token, token_id
    except IndexError as e:
        raise AuthenticationError('Cookies Invalid') from e


# https://developers.cloudflare.com/ssl/ssl-tls/cipher-suites/

CIPHERS13 = ":".join(  # https://docs.python.org/3/library/ssl.html#tls-1-3
        (
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
        )
    )
CIPHERS = ":".join(
    (
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-AES128-SHA",
        "ECDHE-RSA-AES128-SHA",
        "ECDHE-ECDSA-AES256-SHA",
        "ECDHE-RSA-AES256-SHA",
        "AES128-GCM-SHA256",
        "AES256-GCM-SHA384",
        "AES128-SHA",
        "AES256-SHA",
        "DES-CBC3-SHA",  # most likely not available
    )
)
SIGALGS = ":".join(
    (
        "ecdsa_secp256r1_sha256",
        "rsa_pss_rsae_sha256",
        "rsa_pkcs1_sha256",
        "ecdsa_secp384r1_sha384",
        "rsa_pss_rsae_sha384",
        "rsa_pkcs1_sha384",
        "rsa_pss_rsae_sha512",
        "rsa_pkcs1_sha512",
        "rsa_pkcs1_sha1",  # will get ignored and won't be negotiated
    )
)

class ClientSession(aiohttp.ClientSession):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        # ctx.set_ciphers(':'.join(FORCED_CIPHERS))
        # ctx.set_alpn_protocols(CIPH)
        # super().__init__(*args, **kwargs, cookie_jar=aiohttp.CookieJar(), connector=aiohttp.TCPConnector(ssl=ctx))
        ssl_ctx = ssl.create_default_context()

        # https://github.com/python/cpython/issues/88068
        addr = id(ssl_ctx) + sys.getsizeof(object())
        ssl_ctx_addr = ctypes.cast(addr, ctypes.POINTER(ctypes.c_void_p)).contents

        libssl: Optional[ctypes.CDLL] = None
        if sys.platform.startswith("win32"):
            for dll_name in (
                "libssl-3.dll",
                "libssl-3-x64.dll",
                "libssl-1_1.dll",
                "libssl-1_1-x64.dll",
            ):
                with contextlib.suppress(FileNotFoundError, OSError):
                    libssl = ctypes.CDLL(dll_name)
                    break
        elif sys.platform.startswith(("linux", "darwin")):
            libssl = ctypes.CDLL(ssl._ssl.__file__)  # type: ignore

        if libssl is None:
            raise NotImplementedError(
                "Failed to load libssl. Your platform or distribution might be unsupported, please open an issue."
            )

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1  # deprecated since 3.10
        ssl_ctx.set_alpn_protocols(["http/1.1"])
        ssl_ctx.options |= 1 << 19  # SSL_OP_NO_ENCRYPT_THEN_MAC
        ssl_ctx.options |= 1 << 14  # SSL_OP_NO_TICKET
        libssl.SSL_CTX_set_ciphersuites(ssl_ctx_addr, CIPHERS13.encode())
        libssl.SSL_CTX_set_cipher_list(ssl_ctx_addr, CIPHERS.encode())
        # setting SSL_CTRL_SET_SIGALGS_LIST
        libssl.SSL_CTX_ctrl(ssl_ctx_addr, 98, 0, SIGALGS.encode())
        # setting SSL_CTRL_SET_GROUPS_LIST
        libssl.SSL_CTX_ctrl(ssl_ctx_addr, 92, 0, ":".join(
            (
                "x25519",
                "secp256r1",
                "secp384r1",
            )
        ).encode())
        super().__init__(*args, **kwargs, cookie_jar=aiohttp.CookieJar(), connector=aiohttp.TCPConnector(ssl=ssl_ctx), raise_for_status=True)


class Auth:
    RIOT_CLIENT_USER_AGENT = 'RiotClient/1.0.2.1870.3774 rso-auth (Windows;10;;Professional, x64)'

    def __init__(self) -> None:
        self._headers: dict = {
            'Content-Type': 'application/json',
            'User-Agent': Auth.RIOT_CLIENT_USER_AGENT,
            'Accept': 'application/json, text/plain, */*',
            "Accept-Encoding": "deflate, gzip, zstd",
            "Cache-Control": "no-cache",
        }
        self.user_agent = Auth.RIOT_CLIENT_USER_AGENT

        self.locale_code = 'en-US'  # default language
        self.response = {}  # prepare response for local response

    def setup_session(self):
        return ClientSession()
    
    async def setup_auth(self, session: aiohttp.ClientSession) -> aiohttp.ClientResponse:
        data = {
                'client_id': 'riot-client',
                'nonce': '1',
                'redirect_uri': 'http://localhost/redirect',
                'response_type': 'token id_token',
                'scope': 'account openid',
            }
        return await session.post('https://auth.riotgames.com/api/v1/authorization', json=data, headers=self._headers)

    def local_response(self) -> dict[str, Any]:
        """This function is used to check if the local response is enabled."""
        self.response = LocalErrorResponse('AUTH', self.locale_code)
        return self.response

    async def hcaptcha(self, session) -> list[str]: # type: ignore
        # session = ClientSession()
        # data = {
        #     'client_id': 'riot-client',
        #     'nonce': '1',
        #     'redirect_uri': 'https://playvalorant.com/opt_in',
        #     'response_type': 'token id_token',
        #     'scope': 'account openid',
        # }
        # await session.post('https://auth.riotgames.com/api/v1/authorization', json=data, headers=self._headers)

        sdk = requests.get("https://valorant-api.com/v1/version").json()["data"]["riotClientVersion"]
        data = {
            "clientId": "riot-client",
            "language": "",
            "platform": "windows",
            "remember": True,
            "riot_identity": {
                "language": "ko_KR",
                "state": "auth",
            },
            "sdkVersion": sdk,
            "type": "auth",
        }
        r = await session.post("https://authenticate.riotgames.com/api/v1/login", json=data, 
        headers=self._headers)
        data = await r.json()
        # print(data)
        # await session.close()
        return [data["captcha"]["hcaptcha"]["key"], data["captcha"]["hcaptcha"]["data"]]

    async def authenticate(self, session: aiohttp.ClientSession, username: str, password: str, token: str) -> dict[str, Any] | None:
        """This function is used to authenticate the user."""

        # language
        local_response = self.local_response()

        # session = ClientSession()


        # headers = {'Content-Type': 'application/json', 'User-Agent': self.user_agent}

        try:
            r = await self.setup_auth(session)
            # prepare cookies for auth request
            # await session.close()
            cookies = {'cookie': {}}
            for cookie in r.cookies.items():
                cookies['cookie'][cookie[0]] = str(cookie).split('=')[1].split(';')[0]

            
            data = {
                'type': 'auth',
                'language': 'ko_KR',
                'remember': True, 
                'captcha': f'hcaptcha {token}', 
                'username': username, 
                'password': password
                
                }
            # data = {
            #     'type': 'auth',
            #     'language': 'ko_KR',
            #     'remember': True, 
            #     'riot_identity': 
            #         {
            #             'captcha': f'hcaptcha {token}', 
            #             'username': username, 
            #             'password': password
            #         }
            #     }
            
            # cookies = {'cookie': {}}
            async with session.put(
                'https://authenticate.riotgames.com/api/v1/login', json=data, headers=self._headers
            ) as r:
                data = await r.json()
                if 'error' in data and data['error']:
                    raise AuthenticationError(data['error'])
                for cookie in r.cookies.items():
                    cookies['cookie'][cookie[0]] = str(cookie).split('=')[1].split(';')[0]

            # print('Response Status:', r.status)
            # print(data['type'])
            if data['type'] == 'success':
                # expiry_token = datetime.now() + timedelta(hours=1)

                # response = _extract_tokens(data)
                # access_token = response[0]
                # token_id = response[1]
                # print(access_token, token_id)
                # expiry_token = datetime.now() + timedelta(minutes=59)
                # cookies['expiry_token'] = int(datetime.timestamp(expiry_token))  # type: ignore

                # return {'auth': 'response', 'data': {'cookie': cookies, 'access_token': access_token, 'token_id': token_id}}
                login_token = data['success']['login_token']

                data = {
                    "authentication_type": "RiotAuth",
                    "code_verifier": "",
                    "login_token": login_token,
                    "persist_login": True
                }
                await session.post("https://auth.riotgames.com/api/v1/login-token", json=data, headers=self._headers)

                r = await self.setup_auth(session)
                data = await r.json()
                # print(data)
                response = _extract_tokens(data)
                access_token = response[0]
                token_id = response[1]
                # print(access_token, token_id)
                expiry_token = datetime.now() + timedelta(minutes=59)
                cookies['expiry_token'] = int(datetime.timestamp(expiry_token))  # type: ignore

                return {'auth': 'response', 'data': {'cookie': cookies, 'access_token': access_token, 'token_id': token_id}}

            elif data['type'] == 'multifactor':
                if r.status == 429:
                    raise AuthenticationError(local_response.get('RATELIMIT', 'Please wait a few minutes and try again.'))

                label_modal = local_response.get('INPUT_2FA_CODE')
                WaitFor2FA = {'auth': '2fa', 'cookie': cookies, 'label': label_modal}

                if data['multifactor']['method'] == 'email':
                    WaitFor2FA['message'] = (
                        f"{local_response.get('2FA_TO_EMAIL', 'Riot sent a code to')} {data['multifactor']['email']}"
                    )
                    return WaitFor2FA

                WaitFor2FA['message'] = local_response.get('2FA_ENABLE', 'You have 2FA enabled!')
                return WaitFor2FA

        finally:
            await session.close()
        raise AuthenticationError(local_response.get('INVALID_PASSWORD', 'Your username or password may be incorrect!'))
    

    async def get_entitlements_token(self, access_token: str) -> str:
        """This function is used to get the entitlements token."""

        # language
        local_response = self.local_response()

        session = ClientSession()

        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'}

        async with session.post('https://entitlements.auth.riotgames.com/api/token/v1', headers=headers, json={}) as r:
            data = await r.json()

        await session.close()
        try:
            entitlements_token = data['entitlements_token']
        except KeyError as e:
            raise AuthenticationError(
                local_response.get('COOKIES_EXPIRED', 'Cookies is expired, plz /login again!')
            ) from e
        else:
            return entitlements_token

    async def get_userinfo(self, access_token: str) -> tuple[str, str, str]:
        """This function is used to get the user info."""

        # language
        local_response = self.local_response()

        session = ClientSession()

        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'}

        async with session.post('https://auth.riotgames.com/userinfo', headers=headers, json={}) as r:
            data = await r.json()

        await session.close()
        try:
            puuid = data['sub']
            name = data['acct']['game_name']
            tag = data['acct']['tag_line']
        except KeyError as e:
            raise AuthenticationError(
                local_response.get('NO_NAME_TAG', "This user hasn't created a name or tagline yet.")
            ) from e
        else:
            return puuid, name, tag

    async def get_region(self, access_token: str, token_id: str) -> str:
        """This function is used to get the region."""

        # language
        local_response = self.local_response()

        session = ClientSession()

        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'}

        body = {'id_token': token_id}

        async with session.put(
            'https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant', headers=headers, json=body
        ) as r:
            data = await r.json()

        await session.close()
        try:
            region = data['affinities']['live']
        except KeyError as e:
            raise AuthenticationError(
                local_response.get('REGION_NOT_FOUND', 'An unknown error occurred, plz `/login` again')
            ) from e
        else:
            return region

    async def give2facode(self, code: str, cookies: dict[str, Any]) -> dict[str, Any]:
        """This function is used to give the 2FA code."""

        # language
        local_response = self.local_response()

        session = ClientSession()

        # headers = {'Content-Type': 'application/json', 'User-Agent': self.user_agent}

        data = {'type': 'multifactor', 'code': code, 'rememberDevice': True}

        async with session.put(
            'https://auth.riotgames.com/api/v1/authorization',
            headers=self._headers,
            json=data,
            cookies=cookies['cookie'],
        ) as r:
            data = await r.json()

        await session.close()
        if data['type'] == 'response':
            cookies = {'cookie': {}}
            for cookie in r.cookies.items():
                cookies['cookie'][cookie[0]] = str(cookie).split('=')[1].split(';')[0]

            uri = data['response']['parameters']['uri']
            access_token, token_id = _extract_tokens_from_uri(uri)

            return {'auth': 'response', 'data': {'cookie': cookies, 'access_token': access_token, 'token_id': token_id}}

        return {'auth': 'failed', 'error': local_response.get('2FA_INVALID_CODE')}

    async def redeem_cookies(self, cookies: dict) -> tuple[dict[str, Any], str, str]:
        """This function is used to redeem the cookies."""

        # language
        local_response = self.local_response()

        if isinstance(cookies, str):
            cookies = json.loads(cookies)

        session = ClientSession()

        if 'cookie' in cookies:
            cookies = cookies['cookie']

        async with session.get(
            'https://auth.riotgames.com/authorize?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in&client_id=play'
            '-valorant-web-prod&response_type=token%20id_token&scope=account%20openid&nonce=1',
            cookies=cookies,
            allow_redirects=False,
        ) as r:
            data = await r.text()

        if r.status != 303:
            raise AuthenticationError(local_response.get('COOKIES_EXPIRED'))

        if r.headers['Location'].startswith('/login'):
            raise AuthenticationError(local_response.get('COOKIES_EXPIRED'))

        old_cookie = cookies.copy()

        new_cookies = {'cookie': old_cookie}
        for cookie in r.cookies.items():
            new_cookies['cookie'][cookie[0]] = str(cookie).split('=')[1].split(';')[0]

        await session.close()

        access_token, _token_id = _extract_tokens_from_uri(data)
        entitlements_token = await self.get_entitlements_token(access_token)

        return new_cookies, access_token, entitlements_token

    async def temp_auth(self, username: str, password: str) -> dict[str, Any] | None:
        authenticate = await self.authenticate(username, password)
        if authenticate['auth'] == 'response':  # type: ignore
            access_token = authenticate['data']['access_token']  # type: ignore
            token_id = authenticate['data']['token_id']  # type: ignore

            entitlements_token = await self.get_entitlements_token(access_token)
            puuid, name, tag = await self.get_userinfo(access_token)
            region = await self.get_region(access_token, token_id)
            player_name = f'{name}#{tag}' if tag is not None and tag is not None else 'no_username'

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'X-Riot-Entitlements-JWT': entitlements_token,
            }
            user_data = {'puuid': puuid, 'region': region, 'headers': headers, 'player_name': player_name}
            return user_data

        raise AuthenticationError(self.local_response().get('TEMP_LOGIN_NOT_SUPPORT_2FA'))

    # next update

    async def login_with_cookie(self, cookies: dict[str, Any] | str) -> dict[str, Any]:
        """This function is used to log in with cookie."""

        # language
        local_response = ResponseLanguage('cookies', self.locale_code)

        cookie_payload = f'ssid={cookies};' if isinstance(cookies, str) and cookies.startswith('e') else cookies

        self._headers['cookie'] = cookie_payload

        session = ClientSession()

        r = await session.get(
            'https://auth.riotgames.com/authorize'
            '?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in'
            '&client_id=play-valorant-web-prod'
            '&response_type=token%20id_token'
            '&scope=account%20openid'
            '&nonce=1',
            allow_redirects=False,
            headers=self._headers,
        )

        # pop cookie
        self._headers.pop('cookie')

        if r.status != 303:
            raise AuthenticationError(local_response.get('FAILED'))

        await session.close()

        # NEW COOKIE
        new_cookies = {'cookie': {}}
        for cookie in r.cookies.items():
            new_cookies['cookie'][cookie[0]] = str(cookie).split('=')[1].split(';')[0]

        accessToken, tokenID = _extract_tokens_from_uri(await r.text())
        entitlements_token = await self.get_entitlements_token(accessToken)

        data = {'cookies': new_cookies, 'AccessToken': accessToken, 'token_id': tokenID, 'emt': entitlements_token}
        return data

    async def refresh_token(self, cookies: dict) -> tuple[dict[str, Any], str, str]:
        return await self.redeem_cookies(cookies)
