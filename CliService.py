import os
import openai
from dotenv import load_dotenv

load_dotenv()  # This will load the environment variables from the .env file


class CLIInterface:
    def __init__(self):
        self.running = True
        openai.api_key = os.getenv('GPT_SECRET_KEY')
        self.max_tokens = 2048
        self.root_dir = ""

    @staticmethod
    def build():
        # create local file if it doesn't already exist
        if not os.path.exists("stream.txt"):
            f = open("stream.txt", "w")
            f.write('')
            f.close()
        return CLIInterface()

    def start(self):
        while self.running:
            self.root_dir = input("Enter the path to the file tree: ")
            self.max_tokens = int(input("Enter the max tokens value: "))
            choice = input("Enter '1' to continue or '2' for settings: ")
            if choice == "1":
                with open('stream.txt', 'w') as write_file:
                    # Iterate over all the files in the file tree
                    for dirpath, dirnames, filenames in os.walk(self.root_dir):
                        for filename in filenames:
                            # Concatenate the contents of each file
                            with open(os.path.join(dirpath, filename), "r") as file:
                                file_text = file.read()
                                while file_text:
                                    text = file_text[:self.max_tokens]
                                    file_text = file_text[self.max_tokens:]
                                    response = openai.Completion.create(
                                        engine="text-davinci-002",
                                        prompt=text,
                                        max_tokens=1024,
                                        temperature=0.5,
                                        n=1,
                                        stream=True)
                                    # Stream the response
                                    for event in openai.Completion.stream(response.id):
                                        write_file.write(event.get('text'))
                                        print(event.get('text'))
                                        print("\n")
                                        write_file.write('\n')
                                    should_continue = input(
                                        'Continue? (y/n): ')
                                    if should_continue == 'n':
                                        break
            elif choice == "2":
                while True:
                    print("\n# Settings")
                    print("1. change max tokens (current value: {})".format(
                        self.max_tokens))
                    print("2. change root folder (current value: {})".format(
                        self.root_dir))
                    print("3. exit settings")
                    settings_choice = input("Enter your choice: ")
                    if settings_choice == "1":
                        self.max_tokens = int(
                            input("Enter the new max tokens value: "))
                    elif settings_choice == "2":
                        self.root_dir = input(
                            "Enter the new path to the file tree: ")
                    elif settings_choice == "3":
                        break
                    else:
                        print("Invalid choice, please try again.")

            else:
                print("Invalid choice, please try again.")


if __name__ == '__main__':
    cli = CLIInterface.build()
    cli.start()
