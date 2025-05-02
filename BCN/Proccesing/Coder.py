import base64

def compile_command(flag: str, data=None):
    """
    This method compiles a command based on the provided flag and data.
    
    For IC and IR flags, the data is encoded in base64 before sending.
    """
    if flag == "IC":
        # Кодируем команду в base64 для IC флага
        if data:
            data_bytes = data.encode('utf-8')
            base64_data = base64.b64encode(data_bytes).decode('utf-8')
            command = f"IC::::{base64_data}"
        else:
            command = "IC::::None"
    elif flag == "FIN":
        command = "FIN::::0.0.0"
    elif flag == "ACK":
        command = "ACK::::0.0.0"
    elif flag == "EDCN":
        command = "EDCN::::0.0.0"
    elif flag == "INF":
        command = f"INF::::{data}"
    elif flag == "IR":  # Также кодируем ответ на команду в base64
        if data:
            data_bytes = data.encode('utf-8')
            base64_data = base64.b64encode(data_bytes).decode('utf-8')
            command = f"IR::::{base64_data}"
        else:
            command = "IR::::None"
    elif flag == "ERR":
        command = f"ERR::::{data}"
    elif flag == "IND":
        command = f"IND::::{data}"
    else:
        print(f"Unknown flag: {flag}")
        raise ValueError(f"Unknown flag: {flag}")
    return command