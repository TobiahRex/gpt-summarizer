# https://github.com/TobiahRex/nj2jp

import threading
import keyboard
from wrangler_service import WranglerService
from github_service import GithubService
from prompt_service import PromptService
from gpt_service import GptService


class Leo:
    def __init__(self, *args, **kwargs):
        self.prompt_service = kwargs.get('prompt_service')
        self.wrangler_service = kwargs.get('wrangler_service')
        self.github_service = kwargs.get('github_service')
        self.gpt_service = kwargs.get('gpt_service')

    @staticmethod
    def build():
        return Leo(
            prompt_service=PromptService.build(),
            wrangler_service=WranglerService.build(),
            github_service=GithubService.build(),
            gpt_service=GptService.build(),
        )

    def run(self):
        repo_url = None
        target_file = None
        action = None
        while True:
            if not repo_url:
                repo_url = self.prompt_service.get_github_repo_menu()
            if not target_file:
                repo_data = self.github_service.get_repo(repo_url)
                target_file = self.prompt_service.get_repo_file(repo_data)
            self.prompt_service.get_target_locations()
            if not action:
                action = self.prompt_service.get_action_menu()
            if action == "summarize":
                self.summarize_file(target_file)
            elif action == "generate":
                self.generate_prompt(repo_url, target_file)
            elif action == "change_repo":
                repo_url = None
            elif action == "change_file":
                target_file = None
            elif action == "restart":
                repo_url = None
                target_file = None
            elif action == "exit":
                print('\nGoodbye...')
                break

    def summarize_file(self, repo_url, target_file):
        local_filename = self.github_service.download_file(target_file)
        sections = self.wrangler_service.get_sections(local_filename)
        stop_event = threading.Event()
        thread_1 = threading.Thread(
            target=self.gpt_service.summarize_sections,
            args=(sections, stop_event))
        thread_2 = threading.Thread(
            target=self.prompt_service.get_stop_event,
            args=(stop_event))
        self.gpt_service.summarize_sections(sections, stop_event)
        thread_1.start()
        thread_2.start()
        thread_1.join()
        thread_2.join()


if __name__ == '__main__':
    leo = Leo.build()
    leo.run()
