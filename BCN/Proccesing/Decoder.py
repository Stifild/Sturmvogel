import base64

def get_flag_from_command(command: str):
    """
    This method gets the flag from the command.
    """
    try:
        return command.split("::::")[0]
    except IndexError:
        print(f"Invalid command format: {command}")
        return None

def get_command_from_command(command: str):
    """
    This method gets the command from the command.
    Automatically decodes base64 for IC and IR flags.
    """
    try:
        flag = get_flag_from_command(command)
        command_content = command.split("::::")[1]
        
        # Декодируем команду из base64, если она имеет флаг IC или IR
        if flag in ["IC", "IR"] and command_content != "None":
            try:
                command_bytes = base64.b64decode(command_content)
                return command_bytes.decode('utf-8')
            except Exception as e:
                print(f"Error decoding base64 message: {e}")
                return command_content  # Возвращаем исходное содержимое в случае ошибки
        else:
            return command_content
    except IndexError:
        print(f"Invalid command format: {command}")
        return None

def get_subject_from_email(email: str):
    """
    This method gets the subject from the email.
    """
    try:
        return email.split("\n")[2].split(":")[1]
    except IndexError:
        print(f"Invalid email format: {email}")
        return None