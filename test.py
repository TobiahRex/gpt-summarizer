import os
import openai
from dotenv import load_dotenv

load_dotenv()  # This will load the environment variables from the .env file

openai.api_key = os.getenv("GPT_SECRET_KEY")


class TestClass:
    def main():
        prompt = "Can you tell me about a dataset you know?"
        conversation_id = ""

        while True:
            # Send a request to the API
            response = openai.Completion.create(
                engine="text-davinci-002",
                prompt=prompt,
                conversation_id=conversation_id,
                max_tokens=3000
            )
            # Print the response
            print(response["choices"][0]["text"])
            # Update the context and prompt for the next request
            conversation_id = response["conversation_id"]
            prompt = "What else can you tell me about this dataset?"

    def test():
        print('something')


class TestClass2:
    def __init__(self) -> None:
        pass

    @staticmethod
    def static_method():
        print('something else')

    def method1(self):
        print('something')
