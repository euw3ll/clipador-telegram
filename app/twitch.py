import requests
from config import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET

class TwitchAPI:
    def __init__(self):
        self.base_url = "https://api.twitch.tv/helix"
        self.token = self.get_access_token()

    def get_access_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        response = requests.post(url, params=params)
        response.raise_for_status()
        access_token = response.json()["access_token"]
        return access_token

    def get_headers(self):
        return {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self.token}"
        }

    def get_user_info(self, username):
        url = f"{self.base_url}/users"
        params = {"login": username}
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        data = response.json()["data"]
        if data:
            return data[0]  # Retorna info do streamer
        return None

    def get_recent_clips(self, user_id, started_at=None):
        url = f"{self.base_url}/clips"
        params = {
            "broadcaster_id": user_id,
            "first": 100,  # máximo permitido por chamada
        }
        if started_at:
            params["started_at"] = started_at  # formato ISO 8601 (ex: 2025-04-08T00:00:00Z)

        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        return response.json()["data"]
    
    def get_stream_status(self, user_id):
        url = f"{self.base_url}/streams"
        params = {"user_id": user_id}
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        data = response.json()["data"]
        return "ONLINE" if data else "OFFLINE"


    def update_channel_description(self, description):
        url = "https://api.twitch.tv/helix/users"
        headers = self.get_headers()
        headers["Content-Type"] = "application/json"

        payload = {"description": description}
        response = requests.put(url, headers=headers, json=payload)

        if response.status_code == 200:
            print("✅ Descrição do canal atualizada com sucesso!")
        else:
            print("❌ Erro ao atualizar descrição:", response.text)

    def get_latest_vod(self, user_id):
        url = f"{self.base_url}/videos"
        params = {
            "user_id": user_id,
            "first": 1,
            "type": "archive"  # Apenas VODs de lives
        }
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        data = response.json()["data"]
        return data[0] if data else None

    def get_video_by_id(self, video_id):
        url = f"{self.base_url}/videos"
        params = {"id": video_id}
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        data = response.json().get("data", [])
        return data[0] if data else None

    def get_stream_info(self, user_id):
        url = f"{self.base_url}/streams"
        params = {"user_id": user_id}
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        data = response.json().get("data", [])
        return data[0] if data else None
