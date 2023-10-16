import ast


class WranglerService:
    def __init__(self) -> None:
        pass

    @staticmethod
    def build():
        return WranglerService()

    def get_sections(self, filename):
        with open(filename, 'r') as file:
            code = file.read()
        tree = ast.parse(code)
        sections = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                start_line = node.lineno
                end_line = node.body[-1].lineno
                decorators = [dec.lineno for dec in node.decorator_list]
                for dec in decorators:
                    if dec < start_line:
                        start_line = dec
                section = code.splitlines()[start_line - 1:end_line]
                sections.append("\n".join(section))
            elif isinstance(node, ast.ClassDef):
                class_section = [node.name]
                for body_node in node.body:
                    if isinstance(body_node, ast.FunctionDef):
                        start_line = body_node.lineno
                        end_line = body_node.body[-1].lineno
                        decorators = [
                            dec.lineno for dec in body_node.decorator_list]
                        for dec in decorators:
                            if dec < start_line:
                                start_line = dec
                        method_section = code.splitlines()[
                            start_line - 1:end_line]
                        class_section.append("\n".join(method_section))
                sections.append(class_section)
        return sections

    def parse_function(self, code, node):
        start_line = node.lineno
        end_line = node.body[-1].lineno
        function_code = code.splitlines()[start_line - 1:end_line]
        function_code = "\n".join(function_code)
        return function_code


if __name__ == '__main__':
    wrangler = WranglerService.build()
    get_sections = wrangler.get_sections('test.py')
