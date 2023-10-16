

class TextExtractor:
    def __init__(self, model_engine="text-davinci-003", max_tokens=3000, doctype=""):
        self.model_engine = model_engine
        self.max_tokens = max_tokens
        self.doctype = doctype

    def download_file(self, url):
        url = url.split("?")[0]
        html_path = download_html(url)
        print(html_path)
        url = url.rstrip("/")
        base_name = "/tmp/" + url.split("/")[-1]
        print(base_name)
        return html_path, base_name

    def extract_text_from_file(self, file_path):
        if file_path.startswith("http"):
            self.doctype = "article"
            html_path, base_name = self.download_file(file_path)
            if file_path.endswith(".pdf"):
                text = extract_text_from_pdf(html_path)
            else:
                text = extract_text_from_html(html_path)
        elif file_path.endswith(".pdf"):
            pdf_path = file_path
            self.doctype = "paper"
            text = extract_text_from_pdf(pdf_path)
        elif file_path.endswith(".html") or file_path.endswith(".htm"):
            html_path = file_path
            self.doctype = "article"
            text = extract_text_from_html(html_path)
        else:
            text_path = file_path
            with open(text_path, "r") as text_file:
                text = text_file.read()
        return text, base_name

    def write_to_file(self, text, base_name):
        with open(base_name + ".full.txt", 'w') as f:
            f.write(text)
        print(
            f"Text extracted from {file_path} and written to {base_name}.full.txt")

    def extract_text(self, file_path):
        text, base_name = self.extract_text_from_file(file_path)
        self.write_to_file(text, base_name)

        try:
            arg = sys.argv[2]
            output_language_prompt = " Please use " + \
                sys.argv[2]+" language for the output."
        except IndexError:
            output_language_prompt = ""

        sections = split_into_sections(text)

        enc = GPT2TokenizerFast.from_pretrained("gpt2")
        tokens = enc.encode(text)

        print(f"Total token count: {len(tokens)}")

        for header, content in sections:
            print("Header: ", header)
            sections = split_section_into_subsections(header, content, enc)
            combined_subsections = combine_subsections(subsections)
            subheader_count = 1

            for subheader, subcontent in combined_subsections:
                if subheader == header:
                    subheader = subheader + " " + str(subheader_count)
                    subheader_count += 1
                tokens = enc.encode(subcontent)
                if len(tokens) > self.max_tokens:
                    print(f"{subheader} has more than {self.max_tokens} tokens.")
                else:
                    with open(base_name + "." + subheader + ".txt", 'w') as f:
                        f.write(subcontent)
                    print(f"{subheader} written to {base_name}.{subheader}.txt")
