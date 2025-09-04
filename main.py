from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
import uvicorn
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Network Automation API")

# Initialize OpenAI client
# Set OPENAI_API_KEY environment variable or create .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Warning if API key not found
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found. AI interpretation features will be disabled.")
    print("To enable AI features, set the OPENAI_API_KEY environment variable.")

# Cisco-specific system prompt for network interpretation
CISCO_SYSTEM_PROMPT = """You are an expert Cisco network engineer assistant. Your role is to interpret and explain Cisco IOS command outputs in a clear, concise manner. 

When analyzing network outputs:
1. Identify the key information (interface states, IP addresses, routing information, etc.)
2. Highlight any potential issues or warnings (down interfaces, errors, misconfigurations)
3. Provide a brief summary of the overall status
4. Use proper Cisco terminology and abbreviations
5. Focus on actionable insights

Format your response as:
- **Summary**: Brief overview in 1-2 sentences
- **Key Findings**: Bullet points of important information
- **Issues/Warnings**: Any problems detected (if any)
- **Recommendations**: Suggested actions (if applicable)

Keep responses concise and technical but understandable. Assume the reader has basic networking knowledge."""

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic models
class DeviceCredentials(BaseModel):
    device_type: str = "cisco_ios"
    host: str
    username: str
    password: str
    port: Optional[int] = 22
    secret: Optional[str] = None  # Enable password

class ConfigRequest(BaseModel):
    device: DeviceCredentials
    commands: List[str]
    save_config: bool = True

class CommandResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None
    interpretation: Optional[str] = None

class InterpretRequest(BaseModel):
    output: str
    command: Optional[str] = None

# Predefined command templates
COMMAND_TEMPLATES = {
    "interface_config": {
        "name": "Configure Interface",
        "commands": [
            "enable",
            "conf t",
            "interface {interface}",
            "ip address {ip_address} {subnet_mask}",
            "no shutdown",
            "end",
            "write memory"
        ]
    },
    "vlan_config": {
        "name": "Configure VLAN Sub-interfaces",
        "commands": [
            "enable",
            "conf t",
            "int {interface}",
            "no shutdown",
            "exit",
            "int {interface}.{vlan_id}",
            "encapsulation dot1Q {vlan_id}",
            "ip address {ip_address} {subnet_mask}",
            "exit",
        ]
    }
}

def interpret_output(output: str, command: str = None) -> str:
    """Use OpenAI to interpret Cisco command output"""
    if not openai_client:
        return "LLM interpretation not available - API key not configured"
    
    try:
        # Add command context if provided
        context = f"Command executed: {command}\n\n" if command else ""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": CISCO_SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}Please interpret this Cisco output:\n\n{output}"}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating interpretation: {str(e)}"

@app.get("/")
async def root():
    return FileResponse('templates/index.html')

@app.get("/api/templates")
async def get_command_templates():
    """Get available command templates"""
    return COMMAND_TEMPLATES

@app.post("/api/interpret")
async def interpret_command_output(request: InterpretRequest):
    """Interpret command output using LLM"""
    interpretation = interpret_output(request.output, request.command)
    return {
        "interpretation": interpretation,
        "success": True
    }

@app.post("/api/execute", response_model=CommandResponse)
async def execute_commands(request: ConfigRequest):
    """Execute commands on a network device"""
    try:
        # Convert Pydantic model to dict for netmiko
        device_dict = request.device.model_dump()
        
        # Add extended timeout and session log for debugging
        device_dict['timeout'] = 30
        device_dict['session_timeout'] = 60
        device_dict['fast_cli'] = False
        device_dict['session_log'] = 'netmiko_session.log'
        
        print(f"Connecting to {device_dict['host']}...")
        net_connect = ConnectHandler(**device_dict)
        
        # Check if we need to enter enable mode
        if not net_connect.check_enable_mode():
            try:
                net_connect.enable()
            except Exception as e:
                print(f"Warning: Could not enter enable mode: {e}")
        
        # Process commands - separate config commands from show commands
        config_commands = []
        show_commands = []
        
        for cmd in request.commands:
            cmd = cmd.strip()
            if cmd.startswith('show ') or cmd == 'enable' or cmd == 'end' or cmd == 'exit':
                show_commands.append(cmd)
            else:
                config_commands.append(cmd)
        
        output = ""
        interpretation = None
        all_show_outputs = []
        
        # Execute show commands individually
        if show_commands:
            for cmd in show_commands:
                if cmd not in ['enable', 'end', 'exit']:  # Skip mode change commands
                    try:
                        cmd_output = net_connect.send_command(
                            cmd, 
                            expect_string=r'[#>]',
                            read_timeout=20
                        )
                        output += f"\n{net_connect.find_prompt()}{cmd}\n{cmd_output}\n"
                        # Collect show command outputs for interpretation
                        if cmd.startswith('show '):
                            all_show_outputs.append((cmd, cmd_output))
                    except Exception as e:
                        output += f"\nError executing '{cmd}': {str(e)}\n"
        
        # Execute configuration commands
        if config_commands:
            try:
                config_output = net_connect.send_config_set(
                    config_commands,
                    exit_config_mode=True,
                    read_timeout=20
                )
                output += f"\n{config_output}\n"
            except Exception as e:
                output += f"\nError executing config commands: {str(e)}\n"
        
        # Save configuration if requested
        if request.save_config:
            try:
                save_output = net_connect.save_config()
                output += f"\n{save_output}"
            except Exception as e:
                output += f"\nWarning: Could not save config: {str(e)}"
        
        net_connect.disconnect()
        
        # Generate LLM interpretation for show commands if available
        if all_show_outputs and openai_client:
            try:
                combined_output = "\n\n".join([f"Command: {cmd}\nOutput:\n{out}" for cmd, out in all_show_outputs])
                interpretation = interpret_output(combined_output, "Multiple show commands")
            except Exception as e:
                print(f"Error generating interpretation: {e}")
        
        return CommandResponse(
            success=True,
            output=output,
            interpretation=interpretation
        )
        
    except NetMikoTimeoutException:
        raise HTTPException(
            status_code=408,
            detail="Connection timeout. Please check the device IP and connectivity."
        )
    except NetMikoAuthenticationException:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please check username and password."
        )
    except Exception as e:
        error_msg = str(e)
        if "Pattern not detected" in error_msg:
            error_msg += "\n\nThis usually means:\n1. The device needs an enable password\n2. The device has a non-standard prompt\n3. Commands are taking too long to execute\n\nCheck the netmiko_session.log file for details."
        raise HTTPException(
            status_code=500,
            detail=f"Error executing commands: {error_msg}"
        )

@app.post("/api/test-connection")
async def test_connection(device: DeviceCredentials):
    """Test connection to a network device"""
    try:
        device_dict = device.model_dump()
        
        # Add extended timeout for connection test
        device_dict['timeout'] = 20
        device_dict['fast_cli'] = False
        
        net_connect = ConnectHandler(**device_dict)
        
        # Get device prompt to verify connection
        prompt = net_connect.find_prompt()
        
        # Check if we can enter enable mode
        enable_status = "Enable mode not tested"
        if not net_connect.check_enable_mode():
            try:
                net_connect.enable()
                enable_status = "Enable mode accessible"
            except Exception as e:
                enable_status = f"Enable mode requires password or failed: {str(e)}"
        else:
            enable_status = "Already in enable mode"
        
        net_connect.disconnect()
        
        return {
            "success": True,
            "message": f"Successfully connected to device. Prompt: {prompt}. {enable_status}"
        }
        
    except NetMikoTimeoutException:
        return {
            "success": False,
            "message": "Connection timeout. Please check the device IP and connectivity."
        }
    except NetMikoAuthenticationException:
        return {
            "success": False,
            "message": "Authentication failed. Please check username and password."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
