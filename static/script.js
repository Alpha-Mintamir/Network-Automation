// API Base URL
const API_URL = window.location.origin;

// State management
let currentSection = 'home';
let connectionStatus = false;
let deviceInfo = null;
let lastCommandOutput = null;
let aiEnabled = true;

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    initializeFormWatchers();
    showNotification('info', '👋 Welcome! Please connect to a device to begin.');
});

// Initialize event listeners
function initializeEventListeners() {
    // Navigation clicks
    document.querySelectorAll('[data-section]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const section = link.getAttribute('data-section');
            navigateToSection(section);
        });
    });

    // Dropdown menus
    document.querySelectorAll('.dropdown').forEach(dropdown => {
        dropdown.addEventListener('mouseenter', () => {
            dropdown.querySelector('.dropdown-menu').style.display = 'block';
        });
        dropdown.addEventListener('mouseleave', () => {
            dropdown.querySelector('.dropdown-menu').style.display = 'none';
        });
    });

    // Form input listeners for real-time preview
    initializeFormWatchers();
}

// Initialize form watchers for real-time command preview
function initializeFormWatchers() {
    // Interface configuration
    ['int-name', 'int-ip', 'int-mask', 'int-description', 'int-no-shutdown'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', updateInterfacePreview);
            element.addEventListener('change', updateInterfacePreview);
        }
    });

    // Sub-interface configuration
    ['sub-parent', 'sub-vlan', 'sub-ip', 'sub-mask', 'sub-description'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', updateSubinterfacePreview);
            element.addEventListener('change', updateSubinterfacePreview);
        }
    });

    // Static route configuration
    ['static-network', 'static-mask', 'static-nexthop', 'static-distance'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', updateStaticRoutePreview);
        }
    });
}

// Navigation function
function navigateToSection(sectionId) {
    // Update active nav
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-section="${sectionId}"]`)?.classList.add('active');

    // Show/hide sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId)?.classList.add('active');

    currentSection = sectionId;
}

// Routing tab switcher
function showRoutingTab(tabName) {
    // Update active tab
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Show/hide content
    document.querySelectorAll('.routing-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-routing`)?.classList.add('active');
}

// Command generation - simplified
function generateExitCommands() {
    // Return empty - we'll let Netmiko handle mode management
    return [];
}

// Test device connection
async function testConnection() {
    const button = event.target;
    const originalText = button.textContent;
    
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Connecting...';
    
    const device = {
        device_type: "cisco_ios",
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value),
        username: document.getElementById('username').value,
        password: document.getElementById('password').value
    };
    
    // Add enable password if provided
    const secret = document.getElementById('secret').value;
    if (secret) {
        device.secret = secret;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/test-connection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(device)
        });
        
        const result = await response.json();
        
        if (result.success) {
            connectionStatus = true;
            deviceInfo = device;
            updateConnectionStatus(true);
            button.innerHTML = '✅ Connected';
            showNotification('success', result.message);
            
            // Enable all configuration buttons
            document.querySelectorAll('.btn-primary:disabled').forEach(btn => {
                btn.disabled = false;
            });
        } else {
            connectionStatus = false;
            button.innerHTML = '❌ Connection Failed';
            showNotification('error', result.message);
        }
    } catch (error) {
        connectionStatus = false;
        button.innerHTML = '❌ Connection Error';
        showNotification('error', `Connection failed: ${error.message}`);
    } finally {
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalText;
        }, 3000);
    }
}

// Update connection status in navbar
function updateConnectionStatus(connected) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    
    if (connected) {
        statusDot.classList.add('connected');
        statusText.textContent = `Connected to ${deviceInfo.host}`;
    } else {
        statusDot.classList.remove('connected');
        statusText.textContent = 'Disconnected';
    }
}

// Interface configuration preview
function updateInterfacePreview() {
    const preview = document.getElementById('int-preview');
    const intName = document.getElementById('int-name').value || '<interface>';
    const intIp = document.getElementById('int-ip').value || '<ip-address>';
    const intMask = document.getElementById('int-mask').value || '<subnet-mask>';
    const intDesc = document.getElementById('int-description').value;
    const noShutdown = document.getElementById('int-no-shutdown').checked;
    
    let commands = [
        'configure terminal',
        `interface ${intName}`
    ];
    
    if (intDesc) {
        commands.push(`description ${intDesc}`);
    }
    
    commands.push(
        `ip address ${intIp} ${intMask}`,
        noShutdown ? 'no shutdown' : 'shutdown',
        'exit',
        'write memory'
    );
    
    preview.textContent = commands.join('\n');
}

// Sub-interface configuration preview
function updateSubinterfacePreview() {
    const preview = document.getElementById('sub-preview');
    const parent = document.getElementById('sub-parent').value || '<parent-interface>';
    const vlan = document.getElementById('sub-vlan').value || '<vlan-id>';
    const ip = document.getElementById('sub-ip').value || '<ip-address>';
    const mask = document.getElementById('sub-mask').value || '<subnet-mask>';
    const desc = document.getElementById('sub-description').value;
    
    let commands = [
        'configure terminal',
        `interface ${parent}`,
        'no shutdown',
        'exit',
        `interface ${parent}.${vlan}`,
        `encapsulation dot1Q ${vlan}`
    ];
    
    if (desc) {
        commands.push(`description ${desc}`);
    }
    
    commands.push(
        `ip address ${ip} ${mask}`,
        'exit',
        'write memory'
    );
    
    preview.textContent = commands.join('\n');
}

// Static route preview
function updateStaticRoutePreview() {
    const network = document.getElementById('static-network').value || '<network>';
    const mask = document.getElementById('static-mask').value || '<mask>';
    const nexthop = document.getElementById('static-nexthop').value || '<next-hop>';
    const distance = document.getElementById('static-distance').value;
    
    let commands = [
        'configure terminal'
    ];
    
    let routeCmd = `ip route ${network} ${mask} ${nexthop}`;
    if (distance) {
        routeCmd += ` ${distance}`;
    }
    
    commands.push(
        routeCmd,
        'exit',
        'write memory'
    );
    
    // Update preview if it exists
    const preview = document.querySelector('#static-routing .command-preview pre');
    if (preview) {
        preview.textContent = commands.join('\n');
    }
}

// Execute interface configuration
async function executeInterfaceConfig() {
    const intName = document.getElementById('int-name').value;
    const intIp = document.getElementById('int-ip').value;
    const intMask = document.getElementById('int-mask').value;
    const intDesc = document.getElementById('int-description').value;
    const noShutdown = document.getElementById('int-no-shutdown').checked;
    
    if (!intName || !intIp || !intMask) {
        showNotification('error', 'Please fill all required fields');
        return;
    }
    
    let commands = [
        'configure terminal',
        `interface ${intName}`
    ];
    
    if (intDesc) {
        commands.push(`description ${intDesc}`);
    }
    
    commands.push(
        `ip address ${intIp} ${intMask}`,
        noShutdown ? 'no shutdown' : 'shutdown',
        'exit',
        'write memory'
    );
    
    await executeCommands(commands);
}

// Execute sub-interface configuration
async function executeSubinterfaceConfig() {
    const parent = document.getElementById('sub-parent').value;
    const vlan = document.getElementById('sub-vlan').value;
    const ip = document.getElementById('sub-ip').value;
    const mask = document.getElementById('sub-mask').value;
    const desc = document.getElementById('sub-description').value;
    
    if (!parent || !vlan || !ip || !mask) {
        showNotification('error', 'Please fill all required fields');
        return;
    }
    
    let commands = [
        'configure terminal',
        `interface ${parent}`,
        'no shutdown',
        'exit',
        `interface ${parent}.${vlan}`,
        `encapsulation dot1Q ${vlan}`
    ];
    
    if (desc) {
        commands.push(`description ${desc}`);
    }
    
    commands.push(
        `ip address ${ip} ${mask}`,
        'exit',
        'write memory'
    );
    
    await executeCommands(commands);
}

// Execute static route
async function executeStaticRoute() {
    const network = document.getElementById('static-network').value;
    const mask = document.getElementById('static-mask').value;
    const nexthop = document.getElementById('static-nexthop').value;
    const distance = document.getElementById('static-distance').value;
    
    if (!network || !mask || !nexthop) {
        showNotification('error', 'Please fill all required fields');
        return;
    }
    
    let commands = [
        'configure terminal'
    ];
    
    let routeCmd = `ip route ${network} ${mask} ${nexthop}`;
    if (distance) {
        routeCmd += ` ${distance}`;
    }
    
    commands.push(
        routeCmd,
        'exit',
        'write memory'
    );
    
    await executeCommands(commands);
}

// Execute show command
async function executeShowCommand(command) {
    const commands = [command];
    
    await executeCommands(commands, false); // false = don't save config
}

// Save running configuration
async function saveRunningConfig() {
    const commands = ['write memory'];
    
    await executeCommands(commands);
}

// Show tech support
async function showTechSupport() {
    const commands = ['show tech-support'];
    
    await executeCommands(commands, false);
}

// Execute commands on device
async function executeCommands(commands, saveConfig = true) {
    if (!connectionStatus) {
        showNotification('error', 'Please connect to a device first');
        return;
    }
    
    const loader = document.getElementById('loader');
    const outputContainer = document.getElementById('outputContainer');
    const output = document.getElementById('output');
    
    loader.style.display = 'flex';
    
    const request = {
        device: deviceInfo,
        commands: commands,
        save_config: false // We handle saving manually in commands
    };
    
    try {
        const response = await fetch(`${API_URL}/api/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request)
        });
        
        if (response.ok) {
            const result = await response.json();
            
            outputContainer.style.display = 'block';
            output.textContent = result.output;
            lastCommandOutput = result.output;
            
            // Highlight output
            highlightOutput(output);
            
            // Handle AI interpretation if available and enabled
            if (result.interpretation && aiEnabled) {
                displayInterpretation(result.interpretation);
                // Show interpretation tab if we have show commands
                const hasShowCommands = commands.some(cmd => cmd.startsWith('show '));
                if (hasShowCommands) {
                    showNotification('info', '🤖 AI analysis available - check the AI Interpretation tab');
                }
            } else {
                clearInterpretation();
            }
            
            // Scroll to output
            outputContainer.scrollIntoView({ behavior: 'smooth' });
            
            showNotification('success', '✅ Commands executed successfully!');
        } else {
            const error = await response.json();
            showNotification('error', error.detail || 'Failed to execute commands');
        }
    } catch (error) {
        showNotification('error', `Execution failed: ${error.message}`);
    } finally {
        loader.style.display = 'none';
    }
}

// Highlight output syntax
function highlightOutput(element) {
    let content = element.textContent;
    
    // Highlight IP addresses
    content = content.replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, '<span style="color: #3b82f6; font-weight: 600;">$&</span>');
    
    // Highlight interface states
    content = content.replace(/\b(up|active|connected)\b/gi, '<span style="color: #10b981; font-weight: 600;">$&</span>');
    content = content.replace(/\b(down|inactive|disconnected|err-disabled)\b/gi, '<span style="color: #ef4444; font-weight: 600;">$&</span>');
    
    // Highlight interface names
    content = content.replace(/\b(GigabitEthernet|FastEthernet|Ethernet|Vlan)\d+\/\d+(\.\d+)?/g, '<span style="color: #8b5cf6; font-weight: 600;">$&</span>');
    
    element.innerHTML = content;
}

// Clear output
function clearOutput() {
    document.getElementById('output').textContent = '';
    document.getElementById('outputContainer').style.display = 'none';
}

// Show notification
function showNotification(type, message, duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => notification.classList.add('show'), 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

// Show output tab
function showOutputTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.output-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Show/hide sections
    document.querySelectorAll('.output-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${tabName}-output`)?.classList.add('active');
}

// Display AI interpretation
function displayInterpretation(interpretation) {
    const interpretationDiv = document.getElementById('interpretation');
    
    // Convert markdown-style formatting to HTML
    let formattedInterpretation = interpretation
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
    
    interpretationDiv.innerHTML = `<div class="ai-analysis">${formattedInterpretation}</div>`;
}

// Clear interpretation
function clearInterpretation() {
    const interpretationDiv = document.getElementById('interpretation');
    interpretationDiv.innerHTML = `
        <div class="interpretation-placeholder">
            <p>🤖 AI interpretation will appear here for show commands...</p>
        </div>
    `;
}

// Request new interpretation
async function requestInterpretation() {
    if (!lastCommandOutput) {
        showNotification('error', 'No output available for interpretation');
        return;
    }
    
    const loader = document.getElementById('loader');
    loader.style.display = 'flex';
    
    try {
        const response = await fetch(`${API_URL}/api/interpret`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                output: lastCommandOutput
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            displayInterpretation(result.interpretation);
            showNotification('success', '🤖 AI interpretation regenerated');
        } else {
            showNotification('error', 'Failed to generate interpretation');
        }
    } catch (error) {
        showNotification('error', `Interpretation failed: ${error.message}`);
    } finally {
        loader.style.display = 'none';
    }
}

// Toggle AI interpretation
function toggleAIInterpretation() {
    aiEnabled = document.getElementById('enableAI').checked;
    showNotification('info', aiEnabled ? 'AI interpretation enabled' : 'AI interpretation disabled');
}

// Initialize command preview on page load
window.addEventListener('load', () => {
    updateInterfacePreview();
    updateSubinterfacePreview();
    updateStaticRoutePreview();
});