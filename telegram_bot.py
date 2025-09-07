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
(MAIN_MENU, DEVICE_TYPE, DEVICE_IP, DEVICE_USERNAME, DEVICE_PASSWORD, DEVICE_SECRET,
 INTERFACE_NAME, INTERFACE_IP, INTERFACE_MASK, INTERFACE_DESC, CONFIRM_CONFIG,
 VLAN_ID, VLAN_NAME, VLAN_PORTS, CONFIRM_VLAN,
 DHCP_POOL_NAME, DHCP_NETWORK, DHCP_MASK, DHCP_DEFAULT_ROUTER, DHCP_DNS, CONFIRM_DHCP) = range(21)

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
                    CallbackQueryHandler(self.change_device, pattern='^change_device$'),
                    CallbackQueryHandler(self.select_device, pattern='^select_(router|switch)$'),
                    CallbackQueryHandler(self.configure_vlan, pattern='^configure_vlan$'),
                    CallbackQueryHandler(self.configure_dhcp, pattern='^configure_dhcp$'),
                    CallbackQueryHandler(self.show_main_menu, pattern='^main_menu$'),
                ],
                DEVICE_TYPE: [
                    CallbackQueryHandler(self.device_type_selected, pattern='^device_(router|switch)$'),
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
                VLAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vlan_id)],
                VLAN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vlan_name)],
                VLAN_PORTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vlan_ports)],
                CONFIRM_VLAN: [
                    CallbackQueryHandler(self.execute_vlan_config, pattern='^execute_vlan$'),
                    CallbackQueryHandler(self.cancel_config, pattern='^cancel$'),
                ],
                DHCP_POOL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dhcp_pool_name)],
                DHCP_NETWORK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dhcp_network)],
                DHCP_MASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dhcp_mask)],
                DHCP_DEFAULT_ROUTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dhcp_default_router)],
                DHCP_DNS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dhcp_dns)],
                CONFIRM_DHCP: [
                    CallbackQueryHandler(self.execute_dhcp_config, pattern='^execute_dhcp$'),
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
                'devices': {
                    'router': {'connected': False, 'device': None, 'connection': None},
                    'switch': {'connected': False, 'device': None, 'connection': None}
                },
                'current_device': None,
                'config': {}
            }
        
        await update.message.reply_text(
            "🌐 *Welcome to Network Automation Bot!*\n\n"
            "I can help you configure Cisco network devices (routers and switches).\n"
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
        
        # Check if any device is connected
        router_connected = session.get('devices', {}).get('router', {}).get('connected', False)
        switch_connected = session.get('devices', {}).get('switch', {}).get('connected', False)
        current_device = session.get('current_device')
        
        if not router_connected and not switch_connected:
            keyboard.append([InlineKeyboardButton("🔌 Connect to Device", callback_data='connect')])
            status_text = "Please connect to a device to start."
        else:
            # Show connection status
            status_lines = []
            if router_connected:
                router_info = session['devices']['router']['device']
                status_lines.append(f"Router: ✅ {router_info.get('host', 'Unknown')}")
            if switch_connected:
                switch_info = session['devices']['switch']['device']
                status_lines.append(f"Switch: ✅ {switch_info.get('host', 'Unknown')}")
            
            if current_device:
                status_lines.append(f"\n📍 Current: {current_device.title()}")
            
            status_text = "\n".join(status_lines)
            
            # Add connection option if not both devices are connected
            if not (router_connected and switch_connected):
                keyboard.append([InlineKeyboardButton("🔌 Connect Another Device", callback_data='connect')])
            
            # Add device-specific options if a device is selected
            if current_device:
                keyboard.extend([
                    [InlineKeyboardButton("⚙️ Configure Interface", callback_data='configure_interface')],
                    [InlineKeyboardButton("📊 Show Interface Status", callback_data='show_status')],
                ])
                
                # Add device-specific configuration options
                if current_device == 'switch':
                    keyboard.append([InlineKeyboardButton("🔧 Configure VLAN", callback_data='configure_vlan')])
                elif current_device == 'router':
                    keyboard.append([InlineKeyboardButton("📡 Configure DHCP", callback_data='configure_dhcp')])
            
            # Add change device option if both are connected or at least one is connected
            if (router_connected and switch_connected) or current_device:
                keyboard.append([InlineKeyboardButton("🔄 Change Device", callback_data='change_device')])
            
            # Add disconnect option
            keyboard.append([InlineKeyboardButton("🔌 Disconnect Current Device", callback_data='disconnect')])
        
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
        
        user_id = update.effective_user.id
        session = user_sessions[user_id]
        
        # Check which devices are already connected
        router_connected = session['devices']['router']['connected']
        switch_connected = session['devices']['switch']['connected']
        
        keyboard = []
        if not router_connected:
            keyboard.append([InlineKeyboardButton("🌐 Router", callback_data='device_router')])
        if not switch_connected:
            keyboard.append([InlineKeyboardButton("🔧 Switch", callback_data='device_switch')])
        
        await query.edit_message_text(
            "Which type of device would you like to connect to?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return DEVICE_TYPE
    
    async def device_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle device type selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        device_type = query.data.split('_')[1]  # Extract 'router' or 'switch' from callback data
        
        # Store the device type being configured
        context.user_data['configuring_device'] = device_type
        
        # Set default IP for switch
        default_ip = ""
        if device_type == 'switch':
            default_ip = " (Default: 192.168.122.6)"
        
        await query.edit_message_text(
            f"Connecting to *{device_type.title()}*\n\n"
            f"Please enter the *device IP address*{default_ip}:",
            parse_mode='Markdown'
        )
        
        return DEVICE_IP
    
    async def device_ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle device IP input"""
        user_id = update.effective_user.id
        ip = update.message.text.strip()
        device_type = context.user_data.get('configuring_device', 'router')
        
        # Use default IP for switch if empty
        if not ip and device_type == 'switch':
            ip = "192.168.122.6"
        
        # Basic IP validation
        if not self._validate_ip(ip):
            await update.message.reply_text(
                "❌ Invalid IP address format. Please enter a valid IP address:"
            )
            return DEVICE_IP
        
        # Store device info in the appropriate device slot
        user_sessions[user_id]['devices'][device_type]['device'] = {
            'host': ip,
            'device_type': 'cisco_ios'
        }
        
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
        device_type = context.user_data.get('configuring_device', 'router')
        
        user_sessions[user_id]['devices'][device_type]['device']['username'] = username
        
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
        device_type = context.user_data.get('configuring_device', 'router')
        
        user_sessions[user_id]['devices'][device_type]['device']['password'] = password
        
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
        device_type = context.user_data.get('configuring_device', 'router')
        
        if secret.lower() != 'skip':
            user_sessions[user_id]['devices'][device_type]['device']['secret'] = secret
            await update.message.delete()
        
        # Try to connect
        await update.message.reply_text(f"🔄 Connecting to {device_type}...")
        
        device_info = user_sessions[user_id]['devices'][device_type]['device']
        device_info['port'] = 22
        
        try:
            connection = ConnectHandler(**device_info)
            user_sessions[user_id]['devices'][device_type]['connection'] = connection
            user_sessions[user_id]['devices'][device_type]['connected'] = True
            
            # Set as current device if it's the first one or no current device
            if not user_sessions[user_id]['current_device']:
                user_sessions[user_id]['current_device'] = device_type
            
            prompt = connection.find_prompt()
            
            await update.message.reply_text(
                f"✅ *Successfully connected to {device_type}!*\n\n"
                f"Device prompt: `{prompt}`",
                parse_mode='Markdown'
            )
            
            # Clear the device type from context
            context.user_data.pop('configuring_device', None)
            
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
        
        # Clear the device type from context
        context.user_data.pop('configuring_device', None)
        return await self.show_main_menu(update, context)
    
    async def change_device(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Change current device"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = user_sessions[user_id]
        
        # Build keyboard with connected devices
        keyboard = []
        router_connected = session['devices']['router']['connected']
        switch_connected = session['devices']['switch']['connected']
        current_device = session['current_device']
        
        if router_connected and current_device != 'router':
            router_info = session['devices']['router']['device']
            keyboard.append([InlineKeyboardButton(
                f"🌐 Router ({router_info['host']})", 
                callback_data='select_router'
            )])
        
        if switch_connected and current_device != 'switch':
            switch_info = session['devices']['switch']['device']
            keyboard.append([InlineKeyboardButton(
                f"🔧 Switch ({switch_info['host']})", 
                callback_data='select_switch'
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data='main_menu')])
        
        current_info = ""
        if current_device:
            device_info = session['devices'][current_device]['device']
            current_info = f"Currently connected to: *{current_device.title()} ({device_info['host']})*\n\n"
        
        await query.edit_message_text(
            f"{current_info}Select a device to switch to:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return MAIN_MENU
    
    async def select_device(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle device selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        device_type = query.data.split('_')[1]  # Extract 'router' or 'switch'
        
        user_sessions[user_id]['current_device'] = device_type
        
        device_info = user_sessions[user_id]['devices'][device_type]['device']
        
        await query.edit_message_text(
            f"✅ Switched to *{device_type.title()}* ({device_info['host']})",
            parse_mode='Markdown'
        )
        
        # Small delay before showing main menu
        await asyncio.sleep(1)
        
        return await self.show_main_menu(update, context)
    
    async def configure_interface(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start interface configuration flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        current_device = user_sessions[user_id].get('current_device')
        
        if not current_device:
            await query.edit_message_text(
                "❌ Please select a device first!"
            )
            return await self.show_main_menu(update, context)
        
        # Reset config
        user_sessions[user_id]['config'] = {}
        
        device_info = user_sessions[user_id]['devices'][current_device]['device']
        
        await query.edit_message_text(
            f"⚙️ *Interface Configuration on {current_device.title()}*\n"
            f"Device: {device_info['host']}\n\n"
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
        current_device = user_sessions[user_id]['current_device']
        connection = user_sessions[user_id]['devices'][current_device]['connection']
        
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
        current_device = user_sessions[user_id]['current_device']
        
        if not current_device:
            await query.edit_message_text(
                "❌ Please select a device first!"
            )
            return await self.show_main_menu(update, context)
        
        connection = user_sessions[user_id]['devices'][current_device]['connection']
        device_info = user_sessions[user_id]['devices'][current_device]['device']
        
        await query.edit_message_text("🔄 Getting interface status...")
        
        try:
            output = connection.send_command("show ip interface brief")
            
            # Create a button to return to main menu
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            
            await query.edit_message_text(
                f"📊 *Interface Status - {current_device.title()} ({device_info['host']})*\n\n"
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
        """Disconnect from current device"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        current_device = user_sessions[user_id].get('current_device')
        
        if not current_device:
            await query.edit_message_text(
                "❌ No device selected to disconnect!"
            )
            return await self.show_main_menu(update, context)
        
        try:
            device_session = user_sessions[user_id]['devices'][current_device]
            if device_session.get('connection'):
                device_session['connection'].disconnect()
            
            device_session['connected'] = False
            device_session['connection'] = None
            device_info = device_session['device']
            
            # Check if there's another connected device to switch to
            other_device = 'switch' if current_device == 'router' else 'router'
            if user_sessions[user_id]['devices'][other_device]['connected']:
                user_sessions[user_id]['current_device'] = other_device
                await query.edit_message_text(
                    f"✅ Disconnected from {current_device} ({device_info['host']}).\n\n"
                    f"Switched to {other_device}."
                )
            else:
                user_sessions[user_id]['current_device'] = None
                await query.edit_message_text(
                    f"✅ Disconnected from {current_device} ({device_info['host']}).\n\n"
                    "You'll need to connect to a device to continue."
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
    
    async def configure_vlan(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start VLAN configuration flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        current_device = user_sessions[user_id].get('current_device')
        
        if not current_device or current_device != 'switch':
            await query.edit_message_text(
                "❌ VLAN configuration is only available for switches!"
            )
            return await self.show_main_menu(update, context)
        
        # Reset config
        user_sessions[user_id]['config'] = {}
        
        device_info = user_sessions[user_id]['devices'][current_device]['device']
        
        await query.edit_message_text(
            f"🔧 *VLAN Configuration on Switch*\n"
            f"Device: {device_info['host']}\n\n"
            "Please enter the *VLAN ID* (1-4094):",
            parse_mode='Markdown'
        )
        
        return VLAN_ID
    
    async def vlan_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle VLAN ID input"""
        user_id = update.effective_user.id
        vlan_id = update.message.text.strip()
        
        try:
            vlan_num = int(vlan_id)
            if vlan_num < 1 or vlan_num > 4094:
                raise ValueError()
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid VLAN ID. Please enter a number between 1 and 4094:"
            )
            return VLAN_ID
        
        user_sessions[user_id]['config']['vlan_id'] = vlan_id
        
        await update.message.reply_text(
            f"VLAN ID: `{vlan_id}`\n\n"
            "Please enter a *VLAN name* (or type 'skip'):",
            parse_mode='Markdown'
        )
        
        return VLAN_NAME
    
    async def vlan_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle VLAN name input"""
        user_id = update.effective_user.id
        vlan_name = update.message.text.strip()
        
        if vlan_name.lower() != 'skip':
            user_sessions[user_id]['config']['vlan_name'] = vlan_name
        
        await update.message.reply_text(
            "Please enter the *ports to assign* to this VLAN:\n"
            "Format: interface range (e.g., 'Fa0/1-5' or 'Gi0/1,Gi0/3')\n"
            "Or type 'skip' to create VLAN without assigning ports:",
            parse_mode='Markdown'
        )
        
        return VLAN_PORTS
    
    async def vlan_ports(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle VLAN ports input"""
        user_id = update.effective_user.id
        ports = update.message.text.strip()
        
        if ports.lower() != 'skip':
            user_sessions[user_id]['config']['vlan_ports'] = ports
        
        # Show configuration summary
        config = user_sessions[user_id]['config']
        
        summary = (
            "📋 *VLAN Configuration Summary*\n\n"
            f"VLAN ID: `{config['vlan_id']}`\n"
        )
        
        if 'vlan_name' in config:
            summary += f"VLAN Name: `{config['vlan_name']}`\n"
        
        if 'vlan_ports' in config:
            summary += f"Ports: `{config['vlan_ports']}`\n"
        
        summary += "\n*Commands to be executed:*\n```\n"
        commands = self._generate_vlan_commands(config)
        summary += "\n".join(commands)
        summary += "\n```"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Execute", callback_data='execute_vlan'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
            ]
        ]
        
        await update.message.reply_text(
            summary,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CONFIRM_VLAN
    
    async def execute_vlan_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Execute VLAN configuration"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        config = user_sessions[user_id]['config']
        current_device = user_sessions[user_id]['current_device']
        connection = user_sessions[user_id]['devices'][current_device]['connection']
        
        await query.edit_message_text("🔄 Executing VLAN configuration...")
        
        try:
            commands = self._generate_vlan_commands(config)
            output = connection.send_config_set(commands)
            
            # Save configuration
            save_output = connection.save_config()
            
            # Create a button to return to main menu
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            
            await query.edit_message_text(
                "✅ *VLAN configuration completed successfully!*\n\n"
                f"*Output:*\n```\n{output}\n```\n\n"
                f"*Save Result:*\n```\n{save_output}\n```",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            await query.edit_message_text(
                f"❌ VLAN configuration failed: {str(e)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return MAIN_MENU
    
    async def configure_dhcp(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start DHCP configuration flow"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        current_device = user_sessions[user_id].get('current_device')
        
        if not current_device or current_device != 'router':
            await query.edit_message_text(
                "❌ DHCP configuration is only available for routers!"
            )
            return await self.show_main_menu(update, context)
        
        # Reset config
        user_sessions[user_id]['config'] = {}
        
        device_info = user_sessions[user_id]['devices'][current_device]['device']
        
        await query.edit_message_text(
            f"📡 *DHCP Configuration on Router*\n"
            f"Device: {device_info['host']}\n\n"
            "Please enter the *DHCP pool name*:",
            parse_mode='Markdown'
        )
        
        return DHCP_POOL_NAME
    
    async def dhcp_pool_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle DHCP pool name input"""
        user_id = update.effective_user.id
        pool_name = update.message.text.strip()
        
        user_sessions[user_id]['config']['pool_name'] = pool_name
        
        await update.message.reply_text(
            f"Pool Name: `{pool_name}`\n\n"
            "Please enter the *network address* for DHCP:\n"
            "Example: 192.168.1.0",
            parse_mode='Markdown'
        )
        
        return DHCP_NETWORK
    
    async def dhcp_network(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle DHCP network input"""
        user_id = update.effective_user.id
        network = update.message.text.strip()
        
        if not self._validate_ip(network):
            await update.message.reply_text(
                "❌ Invalid network address. Please enter a valid IP address:"
            )
            return DHCP_NETWORK
        
        user_sessions[user_id]['config']['network'] = network
        
        await update.message.reply_text(
            f"Network: `{network}`\n\n"
            "Please enter the *subnet mask*:\n"
            "Example: 255.255.255.0",
            parse_mode='Markdown'
        )
        
        return DHCP_MASK
    
    async def dhcp_mask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle DHCP subnet mask input"""
        user_id = update.effective_user.id
        mask = update.message.text.strip()
        
        if not self._validate_ip(mask):
            await update.message.reply_text(
                "❌ Invalid subnet mask. Please enter a valid subnet mask:"
            )
            return DHCP_MASK
        
        user_sessions[user_id]['config']['mask'] = mask
        
        await update.message.reply_text(
            f"Subnet Mask: `{mask}`\n\n"
            "Please enter the *default gateway/router IP*:",
            parse_mode='Markdown'
        )
        
        return DHCP_DEFAULT_ROUTER
    
    async def dhcp_default_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle DHCP default router input"""
        user_id = update.effective_user.id
        default_router = update.message.text.strip()
        
        if not self._validate_ip(default_router):
            await update.message.reply_text(
                "❌ Invalid IP address. Please enter a valid default router IP:"
            )
            return DHCP_DEFAULT_ROUTER
        
        user_sessions[user_id]['config']['default_router'] = default_router
        
        await update.message.reply_text(
            f"Default Router: `{default_router}`\n\n"
            "Please enter *DNS server IPs* (comma-separated) or type 'skip':\n"
            "Example: 8.8.8.8, 8.8.4.4",
            parse_mode='Markdown'
        )
        
        return DHCP_DNS
    
    async def dhcp_dns(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle DHCP DNS servers input"""
        user_id = update.effective_user.id
        dns_servers = update.message.text.strip()
        
        if dns_servers.lower() != 'skip':
            # Validate DNS IPs
            dns_list = [ip.strip() for ip in dns_servers.split(',')]
            for dns_ip in dns_list:
                if not self._validate_ip(dns_ip):
                    await update.message.reply_text(
                        f"❌ Invalid DNS IP: {dns_ip}. Please enter valid IP addresses:"
                    )
                    return DHCP_DNS
            
            user_sessions[user_id]['config']['dns_servers'] = dns_list
        
        # Show configuration summary
        config = user_sessions[user_id]['config']
        
        summary = (
            "📋 *DHCP Configuration Summary*\n\n"
            f"Pool Name: `{config['pool_name']}`\n"
            f"Network: `{config['network']}`\n"
            f"Subnet Mask: `{config['mask']}`\n"
            f"Default Router: `{config['default_router']}`\n"
        )
        
        if 'dns_servers' in config:
            summary += f"DNS Servers: `{', '.join(config['dns_servers'])}`\n"
        
        summary += "\n*Commands to be executed:*\n```\n"
        commands = self._generate_dhcp_commands(config)
        summary += "\n".join(commands)
        summary += "\n```"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Execute", callback_data='execute_dhcp'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
            ]
        ]
        
        await update.message.reply_text(
            summary,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CONFIRM_DHCP
    
    async def execute_dhcp_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Execute DHCP configuration"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        config = user_sessions[user_id]['config']
        current_device = user_sessions[user_id]['current_device']
        connection = user_sessions[user_id]['devices'][current_device]['connection']
        
        await query.edit_message_text("🔄 Executing DHCP configuration...")
        
        try:
            commands = self._generate_dhcp_commands(config)
            output = connection.send_config_set(commands)
            
            # Save configuration
            save_output = connection.save_config()
            
            # Create a button to return to main menu
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            
            await query.edit_message_text(
                "✅ *DHCP configuration completed successfully!*\n\n"
                f"*Output:*\n```\n{output}\n```\n\n"
                f"*Save Result:*\n```\n{save_output}\n```",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("↩️ Back to Main Menu", callback_data='main_menu')]]
            await query.edit_message_text(
                f"❌ DHCP configuration failed: {str(e)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return MAIN_MENU
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = (
            "🌐 *Network Automation Bot Help*\n\n"
            "*Available Commands:*\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/cancel - Cancel current operation\n\n"
            "*Features:*\n"
            "• Connect to multiple devices (Router & Switch)\n"
            "• Switch between connected devices\n"
            "• Configure interface IP addresses\n"
            "• Configure VLANs (Switch only)\n"
            "• Configure DHCP (Router only)\n"
            "• View interface status\n"
            "• Interactive button-based navigation\n\n"
            "*Security Notes:*\n"
            "• Passwords are deleted after receipt\n"
            "• Sessions are temporary\n"
            "• Use in secure environments only\n\n"
            "*Default Switch IP:* 192.168.122.6"
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
    
    def _generate_vlan_commands(self, config: dict) -> list:
        """Generate VLAN configuration commands"""
        commands = [
            'configure terminal',
            f"vlan {config['vlan_id']}"
        ]
        
        if 'vlan_name' in config:
            commands.append(f"name {config['vlan_name']}")
        
        commands.append('exit')
        
        # Configure ports if specified
        if 'vlan_ports' in config:
            # Handle different port formats
            ports = config['vlan_ports']
            if '-' in ports:
                # Range format: Fa0/1-5
                commands.append(f"interface range {ports}")
            elif ',' in ports:
                # Multiple ports: Gi0/1,Gi0/3
                commands.append(f"interface range {ports}")
            else:
                # Single port
                commands.append(f"interface {ports}")
            
            commands.extend([
                "switchport mode access",
                f"switchport access vlan {config['vlan_id']}",
                "exit"
            ])
        
        commands.extend([
            "exit",
            "write memory"
        ])
        
        return commands
    
    def _generate_dhcp_commands(self, config: dict) -> list:
        """Generate DHCP configuration commands"""
        commands = [
            'configure terminal',
            'service dhcp',
            f"ip dhcp pool {config['pool_name']}",
            f"network {config['network']} {config['mask']}",
            f"default-router {config['default_router']}"
        ]
        
        if 'dns_servers' in config:
            dns_cmd = "dns-server " + " ".join(config['dns_servers'])
            commands.append(dns_cmd)
        
        commands.extend([
            "exit",
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
