# Network Automation Telegram Bot

An interactive Telegram bot for Cisco network device configuration.

## Features

- 🔌 **Device Connection Management**: Connect to Cisco devices via SSH
- ⚙️ **Interface Configuration**: Configure IP addresses on interfaces interactively
- 📊 **Show Commands**: View interface status with `show ip interface brief`
- 🔐 **Secure**: Passwords are automatically deleted from chat
- 💬 **Interactive**: Button-based navigation for ease of use

## Setup and Installation

1. **Install Dependencies**
```bash
cd /home/alpha-lencho/Networking/App
source venv/bin/activate
pip install -r requirements.txt
```

2. **Run the Bot**
```bash
python telegram_bot.py
```

## Using the Bot

### 1. Start the Bot
- Open Telegram and search for your bot
- Send `/start` to begin
- The bot will guide you through the process

### 2. Connect to a Device
- Click "🔌 Connect to Device"
- Enter device details step by step:
  - IP Address (e.g., 192.168.122.5)
  - Username (e.g., admin)
  - Password (automatically deleted for security)
  - Enable password (optional, type 'skip' if not needed)

### 3. Configure an Interface
Once connected:
- Click "⚙️ Configure Interface"
- Provide the following information:
  - Interface name (e.g., GigabitEthernet0/1)
  - IP address (e.g., 192.168.1.1)
  - Subnet mask (e.g., 255.255.255.0)
  - Description (optional, type 'skip' if not needed)
- Review the configuration summary
- Click "✅ Execute" to apply or "❌ Cancel" to abort

### 4. Check Interface Status
- Click "📊 Show Interface Status"
- View the output of `show ip interface brief`

### 5. Disconnect
- Click "🔌 Disconnect" when finished

## Bot Commands

- `/start` - Start the bot and show main menu
- `/help` - Show help information
- `/cancel` - Cancel current operation

## Example Interaction Flow

```
User: /start
Bot: Welcome to Network Automation Bot!
     [Connect to Device button]

User: [Clicks Connect to Device]
Bot: Please enter the device IP address:

User: 192.168.122.5
Bot: IP Address: 192.168.122.5
     Now, please enter the username:

User: admin
Bot: Username: admin
     Please enter the password:

User: [enters password]
Bot: [Deletes password message]
     Password received and deleted for security.
     Do you need an enable password?

User: skip
Bot: Connecting to device...
     ✅ Successfully connected!
     Device prompt: Router#
     
     [Configure Interface] [Show Interface Status] [Disconnect]
```

## Security Considerations

1. **Password Handling**: 
   - Passwords are deleted from chat history immediately
   - No passwords are logged or stored permanently
   
2. **Session Management**:
   - User sessions are temporary (stored in memory)
   - Sessions are lost when bot restarts
   
3. **Recommendations**:
   - Use the bot in private chats only
   - Run on a secure server
   - Consider implementing user authentication
   - Use environment variables for the bot token in production

## Customization

### Adding New Features

To add new configuration options:

1. Add new conversation states in the state definitions
2. Create handler methods for each state
3. Update the conversation handler with new states
4. Add buttons to the main menu

### Example: Adding VLAN Configuration

```python
# Add state
VLAN_ID = 11

# Add handler
async def configure_vlan(self, update, context):
    # VLAN configuration logic
    pass

# Add to main menu
keyboard.append([InlineKeyboardButton("🏷️ Configure VLAN", callback_data='configure_vlan')])
```

## Troubleshooting

### Bot Not Responding
- Check if the bot is running: `ps aux | grep telegram_bot.py`
- Check logs for errors
- Verify bot token is correct

### Connection Issues
- Ensure device is reachable: `ping <device-ip>`
- Verify SSH is enabled on the device
- Check credentials are correct

### Configuration Errors
- Review the command preview before executing
- Check device compatibility with commands
- Ensure interface names are correct

## Production Deployment

For production use:

1. **Use Environment Variables**:
```python
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```

2. **Implement Database Storage**:
- Replace in-memory session storage with database
- Store device configurations securely

3. **Add Authentication**:
- Implement user whitelist
- Add role-based access control

4. **Enable Logging**:
- Log all configuration changes
- Implement audit trails

5. **Use Webhook Instead of Polling**:
```python
application.run_webhook(
    listen="0.0.0.0",
    port=8443,
    url_path=BOT_TOKEN,
    webhook_url=f"https://yourdomain.com/{BOT_TOKEN}"
)
```


