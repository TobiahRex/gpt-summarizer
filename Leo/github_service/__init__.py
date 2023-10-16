import os
from github import Github
from dotenv import load_dotenv

load_dotenv()  # This will load the environment variables from the .env file


class GithubService:
    def __init__(self, *args, **kwargs):
        self.github_api = kwargs.get('github_api')

    @staticmethod
    def build():
        return GithubService(
            github_api=Github(os.getenv('GITHUB_API_KEY'))
        )

    def validate_repo_exists(self, repo_url):
        try:
            repo_name = repo_url.split('/')[-1]
            repo_owner = repo_url.split('/')[-2]
            repo = self.github_api.get_repo(f"{repo_owner}/{repo_name}")
            return repo
        except:
            return None

    def get_repo(self, repo_url):
        try:
            repo_name = repo_url.split('/')[-1]
            repo_owner = repo_url.split('/')[-2]
            return self.github_api.get_repo(f"{repo_owner}/{repo_name}")
        except:
            return None
