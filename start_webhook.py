# start_webhook.py
import os
from core.gateway.webhook_kirvano import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port)