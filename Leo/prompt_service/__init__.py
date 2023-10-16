# This class is a PromptService that uses the command line interface to
# interact with the user. It extends the print_service class.
# The user will be prompted to first select a Github repository, then
# a branch, then a file. The user will then be prompted to enter a
# max_tokens value. The user will then be prompted to enter a
# temperature value. The user will then be prompted to enter a
# number of completions value. The user will then be prompted to
# enter a model value.
# There are methods that generate different menus. There is a method
# that generates a menu for selecting a Github repository. There is a
# method that generats a command to summarize a file that the user
# should have previously selected, or to generate a prompt for a
# producing new code given the summarizations created earlier in the
# process.

import re
import os
import keyboard
from github import Github
from dotenv import load_dotenv
from wrangler_service import WranglerService
from github_service import GithubService

load_dotenv()  # This will load the environment variables from the .env file


class PromptService:
    def __init__(self, *args, **kwargs):
        self.github_service = kwargs.get('github_service')
        self.wrangler_service = kwargs.get('wrangler_service')
        self.target_repo = None
        self.target_file = None

    @staticmethod
    def build():
        return PromptService(
            github_service=GithubService.build(),
            wrangler_service=WranglerService.build()
        )

    def get_target_locations(self):
        print('Target Repo: ', self.target_repo)
        print('Target File: ', self.target_file)

    def set_target_repo(self, repo):
        self.target_repo = repo

    def set_target_file(self, file):
        self.target_file = file

    def get_action_menu(self):
        while True:
            action_menu = """
            Choose an action (number)
            1. Summarize a file
            2. Generate a prompt
            3. Exit
            """
            print(action_menu)
            action = input("Action: ")
            if action == "1":
                return self.wrangler_service.summarize_file(self.target_file)
            elif action == "2":
                return self.wrangler_service.generate_completion(self.target_file)
            elif action == "3":
                return "exit"
            else:
                print("Invalid action")

    def get_file_selection_menu(self):
        while True:
            selection_menu = """
            Choose a file to summarize (filename)
            1. Show Files
            2. Exit
            """
            print(selection_menu)
            action = input("Action: ")
            if action == "1":
                return self.github_service.traverse_github_repo()
            elif action == "2":
                return "exit"
            else:
                print("Invalid action")

    def get_github_repo_menu(self):
        while True:
            repo_menu = """
            1. Type a Github repository
            e.g. https://github.com/TobiahRex/E-commerce-Serverless
            """
            print(repo_menu)
            repo_url = input("Repo Name: ")
            if not self.validate_repo_name(repo_url):
                print("Invalid Github repository name, Try again")
                continue
            else:
                result = self.github_service.validate_repo_exists(repo_url)
                if not result:
                    print("Repo not found on Github. Please try again")
                else:
                    print(f"\nValid Github repository...\n{repo_url}\n\n")
                    return repo_url

    def get_repo_file(self, repo_data):
        # Get the repo name and owner from the repo URL
        repo = repo_data

        current_path = "/"
        while True:
            contents = repo.get_contents(current_path)
            print(f"Path: {current_path} \nFolders and Files:")
            for content in contents:
                print(content.name)
            user_input = input("Enter the name of the next folder: ")
            next_content = None
            for content in contents:
                if content.name == user_input:
                    next_content = content
                    break
            if next_content is None:
                print(f"{user_input} does not exist in this directory.")
                continue
            if next_content.type == "dir":
                current_path = next_content.path
            else:
                print(f"You selected a file: {next_content.name}")
                return next_content.name

    def get_stop_event(self, stop_event):
        while not stop_event.is_set():
            if keyboard.is_pressed("s"):
                stop_event.set()

    @ staticmethod
    def validate_repo_name(repo_url):
        if not repo_url:
            return False
        pattern = re.compile(r"https://github.com/[\w.-]+/[\w.-]+")
        match = pattern.match(repo_url)
        return True if match else False


if __name__ == '__main__':
    prompt_service = PromptService.build()
    repo_url = prompt_service.get_github_repo_menu()
    print(repo_url)
