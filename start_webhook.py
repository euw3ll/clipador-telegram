# start_webhook.py

from core.gateway.webhook_kirvano import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)