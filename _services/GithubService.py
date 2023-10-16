import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # This will load the environment variables from the .env file


class GithubService:
    def __init__(self, *args, **kwargs):
        self.api_key = kwargs.get('api_key')
        self.owner = kwargs.get('owner', kwargs.get('owner'))
        self.repo = kwargs.get('repo')
        self.password = kwargs.get('password')
        self.headers = {'Authorization': 'token ' + self.api_key}
        self.files = []

    @staticmethod
    def build():
        password = os.getenv('GITHUB_PWD')
        api_key = os.getenv('GITHUB_API_KEY')
        owner = os.getenv('GITHUB_OWNER')
        return GithubService(
            api_key=api_key,
            owner=owner,
            password=password)

    def get_files(self):
        return self.files

    def set_repo(self, repo):
        self.repo = repo

    def set_owner(self, owner):
        self.owner = owner

    def fetch_repo_contents(self, repo, owner=None, *args, **kwargs):
        """
        Fetch the contents of a repo given owner & repo name.
        """
        self._verify_class_values(repo=repo, owner=owner)
        url = "https://api.github.com/repos/{owner}/{repo}/contents{path}".format(
            owner=self.owner,
            repo=self.repo,
            path=f"/{kwargs.get('path')}" if kwargs.get('path', '') else ''
        )
        session = requests.Session()
        session.auth = (self.owner, self.api_key)
        response = session.get(url)
        if response.status_code == 200:
            contents = response.json()
            for item in contents:
                if item['type'] == 'dir':
                    self.fetch_repo_contents(self.repo, path=item['path'])
                elif item['type'] == 'file':
                    self.files.append(item.get('download_url'))
        else:
            return None

    def fetch_file_contents(self, file, owner=None, repo=None):
        """
        Fetch the contents of a specific file given a owner, repo name, and file
        """
        self._verify_class_values(owner=owner, repo=repo)
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{file}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def _verify_class_values(self, *args, **kwargs):
        for arg in kwargs:
            if not kwargs.get(arg) and not getattr(self, arg):
                raise Exception(f"Argument {arg} is not defined")
            elif kwargs.get(arg):
                self.__setattr__(arg, kwargs.get(arg))

    def download_files(self):
        """
        Download files from a list of file_urls
        """
        session = requests.Session()
        session.auth = (self.owner, self.api_key)
        for file_url in self.get_files():
            if not file_url:
                raise Exception("File URL is not defined")
            response = session.get(file_url)
            if response.status_code == 200:
                file_path = '.' + file_url.split('.com')[-1].split('?')[0]
                directory = os.path.dirname(file_path)
                if not os.path.exists(directory):
                    os.makedirs(directory)
                with open(file_path, 'w') as f:
                    f.write(response.text)
                    print(f"{file_path} downloaded successfully")
            else:
                raise Exception("Failed to download the file")


if __name__ == '__main__':
    github = GithubService.build()
    content = github.fetch_repo_contents('cointosis')
    github.download_files()
