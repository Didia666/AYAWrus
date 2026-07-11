import requests
import json

with open("config.json", "r") as f:
    config = json.load(f)
bot_token = config["telegram_bot_token"]

# Try to get updates
url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
response = requests.get(url)
data = response.json()

print("Telegram API Response:")
print(json.dumps(data, indent=4))

if data["ok"]:
    if len(data["result"]) == 0:
        print("\nNo messages found yet")
        print("1. Open Telegram")
        print("2. Search for @AYAWRus_Bot")
        print("3. Send 'Hello' to the bot")
        print("4. Wait 10 seconds, then run this script again")
    else:
        for update in reversed(data["result"]):
            if "message" in update:
                cid = update["message"]["chat"]["id"]
                print("\nFound chat ID:", cid)
                config["telegram_chat_id"] = cid
                with open("config.json", "w") as f:
                    json.dump(config, f, indent=4)
                print("Updated config.json!")
                break
