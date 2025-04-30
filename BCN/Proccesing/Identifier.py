from BCN.Proccesing.utils import Utils

class Identifier:
    """
    Class for identification of computer.
    """
    def __init__(self):
        io = Utils()
        self.twmcd = io.load_json("./data/twmcd.json")

    def generate_address(self, computerInfo: dict):
        """
        This method generate identification address of computer.
        """
        io = Utils()

        for address, data, f in self.twmcd.items(), range(255):
            for s in range(255):
                for t in range(255):
                    if address == f"{f}.{s}.{t}":
                        continue
                    else:
                        self.twmcd[f"{f}.{s}.{t}"] = computerInfo
                        io.save_json("./data/twmcd.json", self.twmcd)
                        return f"{f}.{s}.{t}"

    def remove_address(self, address: str):
        """
        This method remove identification address of computer.
        """
        io = Utils()
        del self.twmcd[address]
        io.save_json("./data/twmcd.json", self.twmcd)

    def get_os_by_address(self, address: str):
        """
        This method get OS of computer by address.
        """
        return self.twmcd[address]["os"]