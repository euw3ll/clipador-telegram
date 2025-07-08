import sys
import os
import httpx

from core.ambiente import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
class TwitchAPI:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        # Configura o transporte com retentativas para erros de conexão
        transport = httpx.AsyncHTTPTransport(retries=3)
        # Configura o cliente com o transporte e um timeout mais generoso
        self._client = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(15.0, connect=5.0))

    async def get_access_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        response = await self._client.post(url, params=params)
        response.raise_for_status()
        self.token = response.json()["access_token"]

    async def get_headers(self):
        if not self.token:
            await self.get_access_token()
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.token}"
        }

    async def get_user_info(self, username):
        url = f"https://api.twitch.tv/helix/users?login={username}"
        r = await self._client.get(url, headers=await self.get_headers())
        r.raise_for_status()
        data = r.json()["data"]
        return data[0] if data else None

    async def get_stream_info(self, user_id):
        url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
        r = await self._client.get(url, headers=await self.get_headers())
        r.raise_for_status()
        data = r.json()["data"]
        return data[0] if data else None

    async def get_recent_clips(self, user_id, started_at):
        url = f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&started_at={started_at}"
        r = await self._client.get(url, headers=await self.get_headers())
        r.raise_for_status()
        return r.json().get("data", [])

    async def get_latest_vod(self, user_id):
        url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&first=1&type=archive"
        r = await self._client.get(url, headers=await self.get_headers())
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else None

    async def get_top_streamers_brasil(self, quantidade=5):
        url = f"https://api.twitch.tv/helix/streams?first=100&language=pt"
        r = await self._client.get(url, headers=await self.get_headers())
        r.raise_for_status()
        data = r.json().get("data", [])
        return [stream["user_login"] for stream in data[:quantidade]]
