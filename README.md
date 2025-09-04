# Network Automation Tool

A comprehensive network automation solution for Cisco devices featuring a web interface, REST API, Telegram bot integration, and AI-powered command interpretation.

## 🚀 Features

### Web Interface
- **Professional Navigation**: Multi-page interface with dedicated sections for different network operations
- **Device Management**: Connect to Cisco devices via SSH with secure credential handling
- **Configuration Tools**:
  - Interface IP Configuration
  - Sub-interface (VLAN) Configuration
  - Routing Configuration (Static, OSPF, EIGRP)
  - Access Control Lists
  - DHCP Configuration
- **Show Commands**: Execute and view various show commands with syntax highlighting
- **AI Integration**: OpenAI-powered interpretation of show command outputs for better insights

### Telegram Bot
- **Interactive Configuration**: Button-based navigation for easy network configuration
- **Secure Communication**: Passwords are automatically deleted from chat history
- **Real-time Feedback**: See command execution results instantly
- **Mobile Access**: Configure networks from anywhere using Telegram

### API Features
- **RESTful Endpoints**: Full API for programmatic access
- **Command Templates**: Pre-built templates for common configurations
- **Error Handling**: Comprehensive error messages and status codes
- **Session Management**: Handle multiple device connections

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Network Library**: Netmiko
- **AI Integration**: OpenAI GPT-3.5
- **Telegram Bot**: python-telegram-bot
- **Database**: In-memory session storage (upgradeable to persistent DB)

## 📋 Prerequisites

- Python 3.8 or higher
- Network access to Cisco devices
- Valid device credentials
- OpenAI API key (for AI features)
- Telegram Bot Token (for Telegram integration)

## 🔧 Installation

1. **Clone the repository**
```bash
git clone https://github.com/Alpha-Mintamir/Network-Automation.git
cd Network-Automation
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configuration** (Optional)
- For AI features: Set your OpenAI API key in the code or use environment variables
- For Telegram bot: Update the bot token in `telegram_bot.py`

## 🚀 Usage

### Web Interface

1. **Start the web application**
```bash
python main.py
```

2. **Access the interface**
- Open your browser and navigate to `http://localhost:8000`
- Connect to a device using the sidebar
- Use the navigation menu to access different features

### Telegram Bot

1. **Start the Telegram bot**
```bash
python telegram_bot.py
```

2. **Use the bot**
- Open Telegram and search for your bot
- Send `/start` to begin
- Follow the interactive prompts

### API Usage

The API is available at `http://localhost:8000` when the main application is running.

**Example API calls:**

```bash
# Test connection
curl -X POST http://localhost:8000/api/test-connection \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "cisco_ios",
    "host": "192.168.1.1",
    "username": "admin",
    "password": "password"
  }'

# Execute commands
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device": {
      "device_type": "cisco_ios",
      "host": "192.168.1.1",
      "username": "admin",
      "password": "password"
    },
    "commands": [
      "show ip interface brief",
      "show version"
    ]
  }'
```

## 📁 Project Structure

```
Network-Automation/
├── main.py                 # FastAPI web application
├── telegram_bot.py         # Telegram bot implementation
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── config_example.py      # Configuration example
├── static/                # Frontend assets
│   ├── style.css         # CSS styling
│   └── script.js         # JavaScript functionality
└── templates/            # HTML templates
    └── index.html        # Main web interface
```

## 🔒 Security Considerations

- **Credentials**: Never hardcode credentials in production
- **API Keys**: Use environment variables for sensitive keys
- **HTTPS**: Use HTTPS in production environments
- **Authentication**: Implement proper user authentication for production use
- **Network Security**: Ensure secure network connectivity to devices

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Netmiko library for excellent network device connectivity
- FastAPI for the modern web framework
- OpenAI for AI-powered interpretations
- The open-source community for various tools and libraries

## 📞 Support

For issues, questions, or contributions, please open an issue in the GitHub repository.

---

**Note**: This tool is intended for authorized network administration only. Always ensure you have proper authorization before accessing network devices.