from asyncio import sleep, run
import pandas as pd
import requests
from dotenv import load_dotenv
import os

load_dotenv()

# Load the CSV file
file_path = "data.csv"
df = pd.read_csv(file_path)

# Define the Discord webhook URL
webhook_url = os.getenv("WEBHOOK_URL") or "https://discord.com/api/webhooks/1234567890/ABCDEFGHIJKL"

# Function to send data via Discord webhook
def send_to_discord(name, email, team_id):
    message = f"!register {name} {email} {team_id}"
    # print(message)
    # Uncomment to send data to Discord
    data = {"content": message}
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print(f"Successfully sent: {message}")
    else:
        print(f"Failed to send: {message} - Status code: {response.status_code}")

async def aarambh():
    # Drop rows with missing values in any of the required columns
    df_clean = df.dropna(subset=['name', 'email', 'team'])
    
    for _, row in df_clean.iterrows():
        name = row['name']
        email = row['email']
        team_id = row['team']
        send_to_discord(name, email, team_id)
        await sleep(10)  # Sleep for 3 seconds to avoid rate limiting

# Entry point for running the async function
if __name__ == "__main__":
    run(aarambh())
    print("Data sent to Discord successfully!")