from utils.myjson import deserialize_JSON


class ConfigManager:
    def __init__(self, path: str):
        self.path = path
        with open(self.path, "r") as file:
            content = file.read()
        json = deserialize_JSON(content)
        self.json = json

    def get(self, *args):
        """
        find a collection in the configuration
        :param args: collection of strings to find the section
        """
        section = self.json
        for item in args:
            if not isinstance(section, dict) or item not in section.keys():
                raise ValueError(f"section {item} not found")
            section = section[item]
        return section
