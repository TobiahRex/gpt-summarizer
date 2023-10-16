import os
import openai
from dotenv import load_dotenv


load_dotenv()  # This will load the environment variables from the .env file

openai.api_key = os.getenv('GPT_SECRET_KEY')
# Upload the file to the OpenAI File API
file_id = openai.File.create(
    file=open("Tobiahrex/cointosis/main/README.md", "rb"),
    purpose="fine-"
).id

# Upload the file to the OpenAI File API
with open("path/to/file.txt", "rb") as file:
    data = file.read()
    file_id = openai.File.create(
        file={}).id

# Create a prompt that includes a reference to the file ID
prompt = f"What is the main idea of the content in file {file_id}?"

# Send the prompt to the Completion API
response = openai.Completion.create(
    engine="text-davinci-002", prompt=prompt, max_tokens=1024, temperature=0.5)

# Print the response
print(response["choices"][0]["text"])
