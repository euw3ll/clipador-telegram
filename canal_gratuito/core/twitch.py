import requests
from ..config import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET

class TwitchAPI:
    def __init__(self):
        self.client_id = TWITCH_CLIENT_ID
        self.client_secret = TWITCH_CLIENT_SECRET
        self.token = self.get_access_token()

    def get_access_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        response = requests.post(url, params=params)
        response.raise_for_status()
        return response.json()["access_token"]

    def get_headers(self):
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.token}"
        }

    def get_user_info(self, username):
        url = f"https://api.twitch.tv/helix/users?login={username}"
        r = requests.get(url, headers=self.get_headers())
        r.raise_for_status()
        data = r.json()["data"]
        return data[0] if data else None

    def get_stream_info(self, user_id):
        url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
        r = requests.get(url, headers=self.get_headers())
        r.raise_for_status()
        data = r.json()["data"]
        return data[0] if data else None

    def get_stream_status(self, user_id):
        return "ONLINE" if self.get_stream_info(user_id) else "OFFLINE"

    def get_recent_clips(self, user_id, started_at):
        url = f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&started_at={started_at}"
        r = requests.get(url, headers=self.get_headers())
        r.raise_for_status()
        return r.json().get("data", [])

    def get_latest_vod(self, user_id):
        url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&first=1&type=archive"
        r = requests.get(url, headers=self.get_headers())
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else None
