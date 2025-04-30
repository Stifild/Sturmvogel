def get_flag_from_command(command: str):
    """
    This method get flag from command.
    """
    return command.split("::::")[0]
    
def get_command_from_command(command: str):
    """
    This method get command from command.
    """
    return command.split("::::")[1]

def get_subject_from_email(email: str):
    """
    This method get subject from email.
    """
    return email.split("\n")[2].split(":")[1]