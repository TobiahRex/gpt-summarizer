import requests
import pandas as pd

url = "https://api.github.com/repos/{OWNER}/{REPO}/contents"
response = requests.get(url)
data = response.json()
df = pd.DataFrame(data)
df.to_csv("data.csv", index=False)
