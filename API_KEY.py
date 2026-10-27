import requests
from datetime import datetime

API_URL = "https://mb-api.abuse.ch/api/v1/"
API_KEY = "cbfcc9c5ca31baa03871e4ae1f2cfc4ab9b3912d304a2a02"

START = datetime.fromisoformat("2023-09-24")
END = datetime.fromisoformat("2024-12-14").replace(
    hour=23, minute=59, second=59
)

response = requests.post(
    API_URL,
    headers={"Auth-Key": API_KEY},
    data={
        "query": "get_taginfo",
        "tag": "PE",
        "limit": 1000,
    },
    timeout=60,
)
response.raise_for_status()
result = response.json()

if result.get("query_status") != "ok":
    print("API response:", result.get("query_status"))
else:
    matches = []

    for sample in result.get("data", []):
        first_seen = sample.get("first_seen")
        if not first_seen:
            continue

        date = datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")

        if START <= date <= END:
            matches.append(sample)

    matches.sort(key=lambda x: x["first_seen"])

    for sample in matches:
        print(
            sample["first_seen"],
            sample.get("file_type"),
            sample.get("file_format"),
            sample.get("signature"),
            sample.get("sha256_hash"),
        )

    print(f"\nMatching records returned: {len(matches)}")