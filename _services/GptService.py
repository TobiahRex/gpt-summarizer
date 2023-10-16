
import openai
api_key = os.getenv("GPT_SECRET_KEY")
openai.api_key = api_key


class GPTService:
    def __init__(self, *args, **kwargs):
        self.model_engine = kwargs.get('model_engine', 'text-davinci-003')
        self.temperature = kwargs.get('temperature', 0)
        self.max_tokens = kwargs.get('max_tokens', 3000)
        self.frequency_penalty = kwargs.get('frequency_penalty', 0)
        self.presence_penalty = kwargs.get('presence_penalty', 0)
        self.user = kwargs.get('user', '')
        self.doctype = kwargs.get('doctype', 'article')

    @staticmethod
    def build(*args, **kwargs):
        model_engine = kwargs.get('model_engine', 'text-davinci-003')
        max_tokens = kwargs.get('max_tokens', 3000)
        temperature = kwargs.get('temperature', 0)
        doctype = kwargs.get('doctype', 'article')
        return GPTService(model_engine, max_tokens, doctype, temperature)

    def set_doc_type(self, doctype):
        self.doctype = doctype

    def answer_question(self, prompt, max_tokens=100, temperature=0.5):
        # Generate completions
        completions = openai.Completion.create(
            engine=self.model_engine,
            prompt=prompt,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
        )
