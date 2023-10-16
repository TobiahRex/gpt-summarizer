import sys
from dotenv import load_dotenv

from GptService import GPTService
from FileService import FileService
from ContentWranglingService import ContentWranglingService

load_dotenv()  # This will load the environment variables from the .env file


class DocumentSummarizer:
    def __init__(self, *args, **kwargs):
        self.gpt_service = kwargs.get('gpt_service')
        self.file_service = kwargs.get('file_service')
        self.content_service = kwargs.get('content_service')

    @staticmethod
    def build(*args, **kwargs):
        model_engine = kwargs.get('model_engine', 'text-davinci-003')
        max_tokens = kwargs.get('max_tokens', 3000)
        doctype = kwargs.get('doctype', 'article')
        gpt_service = GPTService.build(model_engine, max_tokens, doctype)
        content_service = ContentWranglingService.build()
        logging_service = LoggingMessagingService.build()
        return DocumentSummarizer(gpt_service, content_service, logging_service)

    def summarize_document(self, file_path, output_language):
        # Strip any trailing /'s from the end of the URL
        stripped_url = file_path.rstrip("/")

        # Get the base name of the URL
        base_name = stripped_url.split("/")[-1]

        if file_path.startswith("http"):
            # Download the HTML file
            html_path = self.file_folder_manipulation.download_html(file_path)
            if file_path.endswith(".pdf"):
                text = self.file_folder_manipulation.extract_text_from_pdf(
                    html_path)
            else:
                # Extract the text
                text = self.file_folder_manipulation.extract_text_from_html(
                    html_path)
        elif file_path.endswith(".pdf"):
            # Extract the text from the PDF file
            text = self.file_folder_manipulation.extract_text_from_pdf(
                file_path)
        elif file_path.endswith(".html") or file_path.endswith(".htm"):
            # Extract the text from the HTML file
            text = self.file_folder_manipulation.extract_text_from_html(
                file_path)
        else:
            # Read the text file
            with open(file_path, "r") as text_file:
                text = text_file.read()

        # Split the text into sections
        sections = self.content_wrangling.split_into_sections(text)

        # encode the text as a sequence of tokens
        tokens = self.gpt.get_encoding(text)

        # Write the extracted text to the output file
        with open(base_name + ".full.txt", 'w') as f:
            f.write(text)

        self.logging_messaging.print_message(
            f"Text extracted from {file_path} and written to {base_name}.full.txt")

        self.logging_messaging.print_message(
            f"Total token count: {len(tokens)}")

        # Write each section to a separate text file
        for header, content in sections:
            self.logging_messaging.print_message("Header: ", header)
            # Split the section into subsections if necessary
            subsections = self.gpt.split_into_subsections(header, content)

            # Combine adjacent tuples with less than 1000 tokens until they exceed 1000 tokens
            combined_subsections = self.content_wrangling.combine_subsections(
                subsections)

            # Initialize the counter for numbering sequential identical subheaders
            subheader_count = 1

            # Process each combined subsection
            for subheader, subcontent in combined_subsections:
                # Update the subheader if there are multiple sequential identical subheaders
            if subheader == last_subheader:
                subheader = subheader + \
                    " " + str(subheader_count)
                subheader_count += 1
            else:
                subheader_count = 1
            last_subheader = subheader
            # Get the summary of the section
            summary = get_summary(subcontent, model_engine, max_tokens)
            # Write the summary to the output file
            with open(base_name + "." + subheader + ".summary.txt", 'w') as f:
                f.write(summary)
            print(
                f"Summary of {subheader} written to {base_name}.{subheader}.summary.txt")

       # Create the HTML file
       create_html_file(base_name, url)


if __name__ == '__main__':
    model_engine = "text-davinci-003"
    max_tokens = 3000
    doctype = ""
    # get the base filename of the first argument without the extension
    base_name = os.path.splitext(sys.argv[1])[0]
    # If the command line argument starts with http, use curl to download it to an HTML file
    if sys.argv[1].startswith("http"):
            # Get the URL from the command line arguments
            url = sys.argv[1]
            doctype = "article"
            # Strip any query parameters from the URL
            url = url.split("?")[0]
             # Process each combined subsection
             for subheader, subcontent in combined_subsections:
                 # Update the subheader if there are multiple sequential identical subheaders
                 if subheader == previous_subheader:
                     subheader += " " + str(
