import json

class Utils:
    def __init__(self):
        pass

    @staticmethod
    def load_json(json_file: str) -> dict:
        with open(json_file, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def save_json(json_file: str, data: dict):
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)
    
    @staticmethod
    def add_record_to_event_log(record: str):
        with open('./data/event.log', 'a') as f:
            f.write(f'{record}\n\n')
    
    @staticmethod
    def read_event_log():
        with open('./data/event.log', 'r') as f:
            return f.read()