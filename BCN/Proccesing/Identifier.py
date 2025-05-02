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
        This method generates an identification address for a computer.
        """
        io = Utils()

        for f in range(256):
            for s in range(256):
                for t in range(256):
                    address = f"{f}.{s}.{t}"
                    if address not in self.twmcd:
                        self.twmcd[address] = computerInfo
                        io.save_json("./data/twmcd.json", self.twmcd)
                        return address
        raise ValueError("No available addresses in the network.")

    def remove_address(self, address: str):
        """
        This method removes an identification address of a computer.
        """
        io = Utils()
        if address in self.twmcd:
            del self.twmcd[address]
            io.save_json("./data/twmcd.json", self.twmcd)
        else:
            print(f"Address {address} not found in the dictionary.")

    def get_os_by_address(self, address: str):
        """
        This method gets the OS of a computer by address.
        """
        return self.twmcd.get(address, {}).get("os", "Unknown")