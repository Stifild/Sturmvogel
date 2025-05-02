# BCN
## How to use?  
1. Download the latest release or clone the repository.  
2. Create an `env.json` file in the ./data/ directory.  
3. [Configure](#how-do-i-configure-the-env-file?) the env file.  
4. You are now ready to use it! Just run the server and suboard! Use `python3 run.py server` or `python3 run.py suboard`.  

## How do I configure the env file?  
To do this, you need to do some tasks:  
1. Create a new mailbox (currently, only mail.ru is supported).  
2. Make a new Telegram bot in [BotFather](https://t.me/botFather).  
Now it's time to fill in the env file! Here is a template:
```json  
{  
  "MAIN_USER_ID": "Your Telegram ID in int format",  
  "BOT_TOKEN": "Token from BotFather",  
    "email": {  
        "address": "Email address",  
        "password": "App Pasword",  
        "smtp": {"host": "smtp.mail.ru", "port": 465}, 
        "imap": {"host": "imap.mail.ru", "port": 993}
    }
}
```
Make sure you fill in all the fields correctly. Only the user ID should be without quotation marks.


## This documentation describes the basics of BCN.

### What is BCN?
BullfinchControl is a network based on the email protocol. It is created for communication between computers to control them remotely from the main server.

#### How it works?
BCN is based on the email protocol. It uses email messages to send commands to computers and receive responses from them.

#### User track:
1. The user sends a Telegram message to the main server through a Telegram bot with a command and destination computer.
2. The main server sends an email message to the destination computer with the command.
3. The destination computer executes the command and sends a response to the main server.
4. The main server sends the response to the user through the Telegram bot.

### BCN protocol
#### Email format
```
From: <Configured email address>
To: <Configured email address>
Subject: <Sender>:<Destination>:<Flag>
Body: <Log message>(|||)<Command>
```

##### Description
- **From** and **To** must be the same email address.
- **Subject** contains information about the sender, destination, and flag.
- **Body** contains the log message and command, separated by `(|||)`.

###### Flags
- **IC** - Incoming command
- **IR** - Incoming response
- **FIN** - Finish connection
- **ERR** - Error
- **EDCN** - Emergency disconnection from the network
- **IND** - Request for identification
- **INF** - Information message
- **ACK** - Acknowledgment

###### Commands
- **IC** - Bash or CMD command
- **IR** - Response
- **FIN** - Sender address
- **ERR** - Error message
- **EDCN** - Sender address
- **IND** - Computer name
- **INF** - Data
- **ACK** - Sender address

###### Computer identification address
All computers have a unique identification address. It looks like a base IPv4 address but uses only 3 octets. For example: `0.0.1`. The network has a reserved address `0.0.0` for the main server and `255.255.255` for broadcast messages.

#### BCNCD
BCNCD _(BullfinchControlNetworkComputerDictionary)_ is a dictionary that contains all computers connected to the network. It is stored on the server in JSON format.

##### Example
```json
{
    "0.0.1": {
        "name": "Computer1",
        "os": "Windows"
    },
    "0.0.2": {
        "name": "Computer2",
        "os": "Linux"
    }
}
```

