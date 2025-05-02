import json

class Utils:
    def __init__(self):
        pass

    @staticmethod
    def load_json(json_file: str) -> dict:
        try:
            with open(json_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            with open(json_file, 'w') as f:
                json.dump({}, f, indent=4)
            return {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {json_file}")
            return {}

    @staticmethod
    def save_json(json_file: str, data: dict):
        try:
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving JSON to {json_file}: {e}")

    @staticmethod
    def add_record_to_event_log(record: str, log_path="./data/event.log"):
        try:
            with open(log_path, 'a') as f:
                f.write(f'{record}\n\n')
        except Exception as e:
            print(f"Error writing to event log: {e}")

    @staticmethod
    def read_event_log(log_path="./data/event.log"):
        try:
            with open(log_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Event log file {log_path} not found.")
            return ""
