import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY")
)

response = client.chat.completions.create(
    model="nvidia/Nemotron-3_5-Lightning",
    messages=[
        {
            "role": "system",
            "content": """SYSTEM_PROMPT"""
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """USER_MESSAGE"""
                }
            ]
        }
    ]
)

print(response.to_json())