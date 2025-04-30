def compile_command(flag: str, data=None):
    """
    This method compiles command based on the provided flag and data.
    """
    if flag == "IC":
        command = f"IC::::{data}"
    elif flag == "FIN":
        command = "FIN::::0.0.0"
    elif flag == "ACK":
        command = "ACK::::0.0.0"
    elif flag == "EDCN":
        command = "EDCN::::0.0.0"
    elif flag == "INF":
        command = f"INF::::{data}"
    elif flag == "ERR":
        command = f"ERR::::{data}"
    else:
        raise ValueError(f"Unknown flag: {flag}")
    return command