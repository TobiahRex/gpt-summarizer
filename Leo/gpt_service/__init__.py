import os
import openai
import threading


class GptService:
    def __init__(self, *args, **kwargs):
        self.openai_service = kwargs.get('openai_service')
        self.text_model = 'text-davinci-002'
        self.code_model = 'code-davinci-002'
        self.temperture = 0.4
        self.max_response_tokens = 1000

    @staticmethod
    def build():
        openai.api_key = os.getenv('GPT_SECRET_KEY')
        return GptService(
            openai_service=openai
        )

    def generate_summary(self, code_text, stream=True):
        prompt = """
        Summarize the following code
        ```
        {code}
        ```
        """.format(code=code_text)
        response = self.openai_service.Completion.create(
            engine="davinci",
            prompt=prompt,
            max_tokens=self.max_response_tokens,
            temperature=self.temperture,
            stop=["\n\n", "\n\t\n", "\n    \n"],
            stream=stream)
        return response

    def generate_code(self, generate_prompt, stream=True):
        response = self.openai_service.Completion.create(
            engine="davinci",
            prompt=generate_prompt,
            max_tokens=self.max_response_tokens,
            temperature=self.temperture,
            stop=["\n\n", "\n\t\n", "\n    \n"],
            stream=stream)
        return response

    def read_stream(self, response_stream, stop_event=threading.Event(), should_print=True):
        text = ""
        for event in response_stream:
            if not stop_event.is_set():
                event_text = event["choices"][0]["text"]
                text += event_text
                if should_print:
                    print(event_text, end="")
            else:
                return text
