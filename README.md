# Network Automation Telegram Bot

A Telegram bot for automating Cisco network device configurations, supporting both routers and switches.

## Features

- **Multi-Device Support**: Connect to both routers and switches simultaneously
- **Device Switching**: Easily switch between connected devices
- **Interface Configuration**: Configure IP addresses on interfaces
- **VLAN Management** (Switch only): Create VLANs and assign ports
- **DHCP Configuration** (Router only): Set up DHCP pools with network settings
- **Interactive UI**: Button-based navigation for easy use
- **Secure**: Passwords are deleted immediately after use

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your Telegram bot token as an environment variable:
   ```bash
   export TELEGRAM_BOT_TOKEN='your-bot-token-here'
   ```

## Usage

1. Start the bot:
   ```bash
   python telegram_bot.py
   ```

2. In Telegram, start a conversation with your bot using `/start`

3. Connect to devices:
   - Select "Connect to Device"
   - Choose device type (Router or Switch)
   - Enter device IP (Switch default: 192.168.122.6)
   - Enter credentials (same for both devices)

4. Switch between devices:
   - Use "Change Device" to switch between connected router and switch

5. Configure devices:
   - **Router**: Interface configuration, DHCP setup
   - **Switch**: Interface configuration, VLAN management

## Commands

- `/start` - Start the bot and show main menu
- `/help` - Display help information
- `/cancel` - Cancel current operation

## Device-Specific Features

### Router Features
- Configure interface IP addresses
- Set up DHCP pools with:
  - Network and subnet mask
  - Default gateway
  - DNS servers

### Switch Features
- Configure interface IP addresses  
- Create and manage VLANs:
  - Create VLAN with ID and name
  - Assign ports to VLANs
  - Support for port ranges (e.g., Fa0/1-5)

## Security Notes

- Passwords are automatically deleted from chat
- Sessions are temporary and stored in memory
- Use only in secure, trusted environments
- No credentials are persisted

## Example Workflow

1. Connect to router (e.g., 192.168.1.1)
2. Connect to switch (192.168.122.6)
3. Switch to router and configure DHCP
4. Switch to switch and create VLANs
5. Configure interfaces on either device as needed