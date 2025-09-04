import logging
import asyncio
import os
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token - Set TELEGRAM_BOT_TOKEN environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
    print("Please set your Telegram bot token as an environment variable.")
    print("Example: export TELEGRAM_BOT_TOKEN='your-bot-token-here'")
    exit(1)

# Conversation states
(MAIN_MENU, DEVICE_IP, DEVICE_USERNAME, DEVICE_PASSWORD, DEVICE_SECRET,
 INTERFACE_NAME, INTERFACE_IP, INTERFACE_MASK, INTERFACE_DESC, CONFIRM_CONFIG) = range(10)

# User sessions storage (in production, use a database)
user_sessions: Dict[int, Dict] = {}

class NetworkBot:
    """Telegram bot for network automation"""
    
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup command and conversation handlers"""
        
        # Conversation handler for the main flow
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                MAIN_MENU: [
                    CallbackQueryHandler(self.connect_device, pattern='^connect$'),
                    CallbackQueryHandler(self.configure_interface, pattern='^configure_interface$'),
                    CallbackQueryHandler(self.show_status, pattern='^show_status$'),
                    CallbackQueryHandler(self.disconnect_device, pattern='^disconnect$'),
                    CallbackQueryHandler(self.show_main_menu, pattern='^main_menu$'),
                ],
                DEVICE_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.device_ip)],
                DEVICE_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.device_username)],
                DEVICE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.device_password)],
                DEVICE_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.device_secret)],
                INTERFACE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.interface_name)],
                INTERFACE_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.interface_ip)],
                INTERFACE_MASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.interface_mask)],
                INTERFACE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.interface_desc)],
                CONFIRM_CONFIG: [
                    CallbackQueryHandler(self.execute_config, pattern='^execute$'),
                    CallbackQueryHandler(self.cancel_config, pattern='^cancel$'),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler('help', self.help_command))
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start command handler"""
        user_id = update.effective_user.id
        
        # Initialize user session if not exists
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                'connected': False,
                'device': None,
                'connection': None,
                'config': {}
            }
        
        await update.message.reply_text(
            "🌐 *Welcome to Network Automation Bot!*\n\n"
            "I can help you configure Cisco network devices.\n"
            "Let's start by connecting to a device.",
            parse_mode='Markdown'
        )
        
        return await self.show_main_menu(update, context)
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show main menu"""
        user_id = update.effective_user.id
        session = user_sessions.get(user_id, {})
        
        keyboard = []
        status_text = ""
        
        if not session.get('connected'):
            keyboard.append([InlineKeyboardButton("🔌 Connect to Device", callback_data='connect')])
            status_text = "Please connect to a device to start."
        else:
            device = session.get('device', {})
            status_text = f"✅ Connected to {device.get('host', 'Unknown')}"
            
            keyboard.extend([
                [InlineKeyboardButton("⚙️ Configure Interface", callback_data='configure_interface')],
                [InlineKeyboardButton("📊 Show Interface Status", callback_data='show_status')],
                [InlineKeyboardButton("🔌 Disconnect", callback_data='disconnect')]
            ])
        
        message_text = f"{status_text}\n\nWhat would you like to do?" if status_text else "What would you like to do?"
        
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return MAIN_MENU
    
    async def connect_device(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start device connection flow"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "Let's connect to your device.\n\n"
            "Please enter the *device IP address*:",
            parse_mode='Markdown'
        )
        
        return DEVICE_IP
    
    async def device_ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle device IP input"""
        user_id = update.effective_user.id
        ip = update.message.text.strip()
        
        # Basic IP validation
        if not self._validate_ip(ip):
            await update.message.reply_text(
                "❌ Invalid IP address format. Please enter a valid IP address:"
            )
            return DEVICE_IP
        
        user_sessions[user_id]['device'] = {'host': ip, 'device_type': 'cisco_ios'}
        
        await update.message.reply_text(
            f"IP Address: `{ip}`\n\n"
            "Now, please enter the *username*:",
            parse_mode='Markdown'
        )
        
        return DEVICE_USERNAME
    
    async def device_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle username input"""
        user_id = update.effective_user.id
        username = update.message.text.strip()
        
        user_sessions[user_id]['device']['username'] = username
        
        await update.message.reply_text(
            f"Username: `{username}`\n\n"
            "Please enter the *password*:\n"
            "_(Your password will not be stored)_",
            parse_mode='Markdown'
        )
        
        return DEVICE_PASSWORD
    
    async def device_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle password input"""
        user_id = update.effective_user.id
        password = update.message.text.strip()
        
        user_sessions[user_id]['device']['password'] = password
        
        # Delete the password message for security
        await update.message.delete()
        
        await update.message.reply_text(
            "Password received and deleted for security.\n\n"
            "Do you need an *enable password*?\n"
            "Reply with the enable password or type 'skip' to continue:",
            parse_mode='Markdown'
        )
        
        return DEVICE_SECRET
    
    async def device_secret(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle enable password input"""
        user_id = update.effective_user.id
        secret = update.message.text.strip()
        
        if secret.lower() != 'skip':
            user_sessions[user_id]['device']['secret'] = secret
            await update.message.delete()
        
        # Try to connect
        await update.message.reply_text("🔄 Connecting to device...")
        
        device_info = user_sessions[user_id]['device']
        device_info['port'] = 22
        
        try:
            connection = ConnectHandler(**device_info)
            user_sessions[user_id]['connection'] = connection
            user_sessions[user_id]['connected'] = True
            
            prompt = connection.find_prompt()
            
            await update.message.reply_text(
                f"✅ *Successfully connected!*\n\n"
                f"Device prompt: `{prompt}`",
                parse_mode='Markdown'
            )
            
            return await self.show_main_menu(update, context)
            
        except NetMikoTimeoutException:
            await update.message.reply_text(
                "❌ Connection timeout. Please check the device IP and try again."
            )
        except NetMikoAuthenticationException:
            await update.message.reply_text(
                "❌ Authentication failed. Please check credentials and try again."
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Connection error: {str(e)}"
            )
        
        return await self.show_main_menu(update, context)
    
    async def configure_interface(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start interface configuration flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if not user_sessions[user_id].get('connected'):
            await query.edit_message_text(
                "❌ Please connect to a device first!"
            )
            return await self.show_main_menu(update, context)
        
        # Reset config
        user_sessions[user_id]['config'] = {}
        
        await query.edit_message_text(
            "⚙️ *Interface Configuration*\n\n"
            "Please enter the *interface name*:\n"
            "Examples: GigabitEthernet0/1, FastEthernet0/0",
            parse_mode='Markdown'
        )
        
        return INTERFACE_NAME
    
    async def interface_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle interface name input"""
        user_id = update.effective_user.id
        interface = update.message.text.strip()
        
        user_sessions[user_id]['config']['interface'] = interface
        
        await update.message.reply_text(
            f"Interface: `{interface}`\n\n"
            "Please enter the *IP address* for this interface:",
            parse_mode='Markdown'
        )
        
        return INTERFACE_IP
    
    async def interface_ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle interface IP input"""
        user_id = update.effective_user.id
        ip = update.message.text.strip()
        
        if not self._validate_ip(ip):
            await update.message.reply_text(
                "❌ Invalid IP address format. Please enter a valid IP address:"
            )
            return INTERFACE_IP
        
        user_sessions[user_id]['config']['ip_address'] = ip
        
        await update.message.reply_text(
            f"IP Address: `{ip}`\n\n"
            "Please enter the *subnet mask*:\n"
            "Example: 255.255.255.0",
            parse_mode='Markdown'
        )
        
        return INTERFACE_MASK
    
    async def interface_mask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle subnet mask input"""
        user_id = update.effective_user.id
        mask = update.message.text.strip()
        
        if not self._validate_ip(mask):
            await update.message.reply_text(
                "❌ Invalid subnet mask format. Please enter a valid subnet mask:"
            )
            return INTERFACE_MASK
        
        user_sessions[user_id]['config']['subnet_mask'] = mask
        
        await update.message.reply_text(
            f"Subnet Mask: `{mask}`\n\n"
            "Please enter an *interface description* (or type 'skip'):",
            parse_mode='Markdown'
        )
        
        return INTERFACE_DESC
    
    async def interface_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle interface description input"""
        user_id = update.effective_user.id
        desc = update.message.text.strip()
        
        if desc.lower() != 'skip':
            user_sessions[user_id]['config']['description'] = desc
        
        # Show configuration summary
        config = user_sessions[user_id]['config']
        
        summary = (
            "📋 *Configuration Summary*\n\n"
            f"Interface: `{config['interface']}`\n"
            f"IP Address: `{config['ip_address']}`\n"
            f"Subnet Mask: `{config['subnet_mask']}`\n"
        )
        
        if 'description' in config:
            summary += f"Description: `{config['description']}`\n"
        
        summary += "\n*Commands to be executed:*\n```\n"
        commands = self._generate_interface_commands(config)
        summary += "\n".join(commands)
        summary += "\n```"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Execute", callback_data='execute'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
            ]
        ]
        
        await update.message.reply_text(
            summary,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CONFIRM_CONFIG
    
    async def execute_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Execute the configuration"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        config = user_sessions[user_id]['config']
        connection = user_sessions[user_id]['connection']
        
        await query.edit_message_text("🔄 Executing configuration...")
        
        try:
            commands = self._generate_interface_commands(config)
            output = connection.send_config_set(commands)
            
            # Save configuration
            save_output = connection.save_config()
            
            # Create a button to return to main menu
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            
            await query.edit_message_text(
                "✅ *Configuration completed successfully!*\n\n"
                f"*Output:*\n```\n{output}\n```\n\n"
                f"*Save Result:*\n```\n{save_output}\n```",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            await query.edit_message_text(
                f"❌ Configuration failed: {str(e)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        # Don't automatically return to main menu - wait for user to click button
        return MAIN_MENU
    
    async def cancel_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel configuration"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
        
        await query.edit_message_text(
            "❌ Configuration cancelled.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return MAIN_MENU
    
    async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show interface status"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        connection = user_sessions[user_id]['connection']
        
        await query.edit_message_text("🔄 Getting interface status...")
        
        try:
            output = connection.send_command("show ip interface brief")
            
            # Create a button to return to main menu
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            
            await query.edit_message_text(
                "📊 *Interface Status*\n\n"
                f"```\n{output}\n```",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            await query.edit_message_text(
                f"❌ Failed to get status: {str(e)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return MAIN_MENU
    
    async def disconnect_device(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Disconnect from device"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        try:
            if user_sessions[user_id].get('connection'):
                user_sessions[user_id]['connection'].disconnect()
            
            user_sessions[user_id]['connected'] = False
            user_sessions[user_id]['connection'] = None
            
            await query.edit_message_text(
                "✅ Disconnected from device.\n\n"
                "You'll need to connect again to use the bot."
            )
            
            # Small delay before showing main menu
            await asyncio.sleep(1.5)
            
        except Exception as e:
            await query.edit_message_text(f"Error disconnecting: {str(e)}")
            await asyncio.sleep(1.5)
        
        return await self.show_main_menu(update, context)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel current operation"""
        await update.message.reply_text("Operation cancelled.")
        return await self.show_main_menu(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = (
            "🌐 *Network Automation Bot Help*\n\n"
            "*Available Commands:*\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/cancel - Cancel current operation\n\n"
            "*Features:*\n"
            "• Connect to Cisco devices via SSH\n"
            "• Configure interface IP addresses\n"
            "• View interface status\n"
            "• Interactive button-based navigation\n\n"
            "*Security Notes:*\n"
            "• Passwords are deleted after receipt\n"
            "• Sessions are temporary\n"
            "• Use in secure environments only"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    def _validate_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        try:
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except ValueError:
            return False
    
    def _generate_interface_commands(self, config: dict) -> list:
        """Generate interface configuration commands"""
        commands = [
            'configure terminal',
            f"interface {config['interface']}"
        ]
        
        if 'description' in config:
            commands.append(f"description {config['description']}")
        
        commands.extend([
            f"ip address {config['ip_address']} {config['subnet_mask']}",
            "no shutdown",
            "exit",
            "write memory"
        ])
        
        return commands
    
    def run(self):
        """Run the bot"""
        self.application.run_polling()

if __name__ == '__main__':
    logger.info("Starting Network Automation Bot...")
    bot = NetworkBot()
    bot.run()
