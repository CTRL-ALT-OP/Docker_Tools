/**
 * Terminal View JavaScript
 * Handles real-time terminal output display and updates
 */

// Global state
let terminalOutput = '';
let lastUpdateTime = 0;
let updateInterval = null;
let autoScroll = true;
let isUpdating = false;
let syncCheckInterval = null;
let lastKnownDesktopSelection = null;

// DOM Elements
const terminalOutputElement = document.getElementById('terminal-output');
const statusText = document.getElementById('status-text');
const lastUpdateElement = document.getElementById('last-update');
const autoScrollIndicator = document.getElementById('auto-scroll-indicator');
const statusMessage = document.getElementById('status-message');
const loadingIndicator = document.getElementById('loading-indicator');
const projectSelector = document.getElementById('project-selector');
const refreshBtn = document.getElementById('refresh-btn');

// Initialize the terminal view
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    startTerminalUpdates();
    startSyncMonitoring();
    loadInitialOutput();
});

/**
 * Initialize event listeners
 */
function initializeEventListeners() {
    // Project selector change
    if (projectSelector) {
        projectSelector.addEventListener('change', async function() {
            const selectedGroup = this.value;
            if (selectedGroup) {
                await selectProject(selectedGroup);
            }
        });
    }

    // Refresh button
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshTerminal);
    }

    // Auto-scroll toggle
    if (autoScrollIndicator) {
        autoScrollIndicator.addEventListener('click', toggleAutoScroll);
    }

    // Terminal output scroll event
    if (terminalOutputElement) {
        terminalOutputElement.addEventListener('scroll', handleTerminalScroll);
    }

    // Handle page visibility changes
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // Resume updates when page becomes visible
            startTerminalUpdates();
            startSyncMonitoring();
        } else {
            // Pause updates when page is hidden
            stopTerminalUpdates();
            stopSyncMonitoring();
        }
    });
}

/**
 * Start terminal output updates
 */
function startTerminalUpdates() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    
    // Update every 2 seconds
    updateInterval = setInterval(updateTerminalOutput, 2000);
    
    // Also update immediately
    updateTerminalOutput();
}

/**
 * Stop terminal output updates
 */
function stopTerminalUpdates() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

/**
 * Start monitoring for desktop selection changes
 */
function startSyncMonitoring() {
    if (syncCheckInterval) {
        clearInterval(syncCheckInterval);
    }
    
    // Check for desktop changes every 2 seconds
    syncCheckInterval = setInterval(checkDesktopSync, 2000);
    
    // Also check immediately
    checkDesktopSync();
}

/**
 * Stop monitoring for desktop selection changes
 */
function stopSyncMonitoring() {
    if (syncCheckInterval) {
        clearInterval(syncCheckInterval);
        syncCheckInterval = null;
    }
}

/**
 * Check if desktop selection has changed and update if needed
 */
async function checkDesktopSync() {
    try {
        const result = await apiCall('/api/sync-status');
        
        if (result.success) {
            const currentSelection = result.current_selection;
            const lastDesktopChange = result.last_desktop_change;
            
            // Update dropdown if desktop selection changed
            if (lastDesktopChange && 
                lastDesktopChange !== lastKnownDesktopSelection && 
                lastDesktopChange !== projectSelector.value) {
                
                lastKnownDesktopSelection = lastDesktopChange;
                
                // Update dropdown without triggering change event
                updateDropdownSelection(lastDesktopChange);
                
                // Show notification
                updateStatusText(`Desktop selection changed to: ${lastDesktopChange}`, 'info');
                
                // Reload page to show updated project
                setTimeout(() => {
                    window.location.href = `/terminal?group=${encodeURIComponent(lastDesktopChange)}`;
                }, 1000);
            }
        }
    } catch (error) {
        // Silently handle sync check errors to avoid spam
        console.debug('Sync check failed:', error);
    }
}

/**
 * Update dropdown selection without triggering change event
 */
function updateDropdownSelection(groupName) {
    if (projectSelector && projectSelector.value !== groupName) {
        // Temporarily remove event listener to prevent triggering change
        const originalOnChange = projectSelector.onchange;
        projectSelector.onchange = null;
        
        // Update value
        projectSelector.value = groupName;
        
        // Restore event listener
        setTimeout(() => {
            projectSelector.onchange = originalOnChange;
        }, 100);
    }
}

/**
 * Update terminal output from server
 */
async function updateTerminalOutput() {
    if (isUpdating) {
        return; // Prevent overlapping requests
    }

    isUpdating = true;
    
    try {
        const result = await apiCall('/api/terminal/output');
        
        if (result.success) {
            const newOutput = result.output || '';
            const timestamp = result.timestamp || 0;
            
            // Only update if there's new content
            if (newOutput !== terminalOutput || timestamp > lastUpdateTime) {
                terminalOutput = newOutput;
                lastUpdateTime = timestamp;
                
                updateTerminalDisplay();
                updateStatusInfo(timestamp);
            }
        } else {
            console.warn('Failed to get terminal output:', result.message);
        }
    } catch (error) {
        console.error('Error updating terminal output:', error);
        updateStatusText('Error connecting to server', 'error');
    } finally {
        isUpdating = false;
    }
}

/**
 * Update the terminal display
 */
function updateTerminalDisplay() {
    if (!terminalOutputElement) {
        return;
    }

    const currentScrollTop = terminalOutputElement.scrollTop;
    const currentScrollHeight = terminalOutputElement.scrollHeight;
    const currentClientHeight = terminalOutputElement.clientHeight;
    const isAtBottom = currentScrollTop + currentClientHeight >= currentScrollHeight - 10;

    // Update the content
    terminalOutputElement.value = terminalOutput;

    // Auto-scroll if enabled and user was at bottom
    if (autoScroll && isAtBottom) {
        terminalOutputElement.scrollTop = terminalOutputElement.scrollHeight;
    }

    // Update status
    if (terminalOutput.trim()) {
        updateStatusText('Terminal active - Output available', 'success');
    } else {
        updateStatusText('Ready - Waiting for output...', 'info');
    }
}

/**
 * Update status information
 */
function updateStatusInfo(timestamp) {
    if (lastUpdateElement) {
        const date = new Date(timestamp * 1000);
        const timeString = date.toLocaleTimeString();
        lastUpdateElement.textContent = ` | Last update: ${timeString}`;
    }
}

/**
 * Update status text
 */
function updateStatusText(text, type = 'info') {
    if (statusText) {
        statusText.textContent = text;
        statusText.className = `status-${type}`;
    }
    
    if (statusMessage) {
        statusMessage.textContent = text;
        statusMessage.className = `status-${type}`;
    }
}

/**
 * Handle terminal scroll events
 */
function handleTerminalScroll() {
    if (!terminalOutputElement) {
        return;
    }

    const currentScrollTop = terminalOutputElement.scrollTop;
    const currentScrollHeight = terminalOutputElement.scrollHeight;
    const currentClientHeight = terminalOutputElement.clientHeight;
    const isAtBottom = currentScrollTop + currentClientHeight >= currentScrollHeight - 10;

    // Update auto-scroll indicator
    if (autoScrollIndicator) {
        if (isAtBottom) {
            autoScrollIndicator.classList.add('active');
        } else {
            autoScrollIndicator.classList.remove('active');
        }
    }
}

/**
 * Toggle auto-scroll functionality
 */
function toggleAutoScroll() {
    autoScroll = !autoScroll;
    
    if (autoScrollIndicator) {
        if (autoScroll) {
            autoScrollIndicator.classList.add('active');
            autoScrollIndicator.innerHTML = '<i class="fas fa-arrow-down"></i> Auto-scroll';
            updateStatusText('Auto-scroll enabled', 'success');
        } else {
            autoScrollIndicator.classList.remove('active');
            autoScrollIndicator.innerHTML = '<i class="fas fa-pause"></i> Manual';
            updateStatusText('Auto-scroll disabled - Manual mode', 'warning');
        }
    }
}

/**
 * Copy terminal output to clipboard
 */
async function copyTerminalOutput() {
    try {
        if (!terminalOutput.trim()) {
            updateStatusText('No output to copy', 'warning');
            return;
        }

        await navigator.clipboard.writeText(terminalOutput);
        updateStatusText('Terminal output copied to clipboard', 'success');
        
        // Visual feedback
        const copyBtn = document.querySelector('.btn-copy');
        if (copyBtn) {
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
            copyBtn.style.backgroundColor = 'var(--success, #27ae60)';
            
            setTimeout(() => {
                copyBtn.innerHTML = originalText;
                copyBtn.style.backgroundColor = '';
            }, 2000);
        }
    } catch (error) {
        console.error('Failed to copy terminal output:', error);
        updateStatusText('Failed to copy output', 'error');
    }
}

/**
 * Clear terminal output
 */
async function clearTerminal() {
    try {
        const result = await apiCall('/api/terminal/clear', {
            method: 'POST'
        });
        
        if (result.success) {
            terminalOutput = '';
            updateTerminalDisplay();
            updateStatusText('Terminal cleared', 'success');
        } else {
            updateStatusText('Failed to clear terminal', 'error');
        }
    } catch (error) {
        console.error('Error clearing terminal:', error);
        updateStatusText('Error clearing terminal', 'error');
    }
}

/**
 * Refresh terminal view
 */
async function refreshTerminal() {
    updateStatusText('Refreshing terminal...', 'info');
    setLoading(true);
    
    try {
        await updateTerminalOutput();
        updateStatusText('Terminal refreshed', 'success');
    } catch (error) {
        console.error('Error refreshing terminal:', error);
        updateStatusText('Error refreshing terminal', 'error');
    } finally {
        setLoading(false);
    }
}

/**
 * Load initial terminal output
 */
async function loadInitialOutput() {
    updateStatusText('Loading terminal output...', 'info');
    await updateTerminalOutput();
}

/**
 * Select project and update URL
 */
async function selectProject(groupName) {
    try {
        const result = await apiCall('/api/select-project', {
            method: 'POST',
            body: JSON.stringify({ group_name: groupName })
        });
        
        if (result.success) {
            // Update URL to reflect new project
            const url = new URL(window.location);
            url.searchParams.set('group', groupName);
            window.history.pushState({}, '', url);
            
            updateStatusText(`Switched to project: ${groupName}`, 'success');
            
            // Refresh terminal output for new project
            await updateTerminalOutput();
        } else {
            updateStatusText(`Failed to switch project: ${result.message}`, 'error');
        }
    } catch (error) {
        console.error('Error selecting project:', error);
        updateStatusText('Error switching project', 'error');
    }
}

/**
 * Go back to main dashboard
 */
function goBack() {
    window.location.href = '/';
}

/**
 * Show/hide loading indicator
 */
function setLoading(isLoading) {
    if (loadingIndicator) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }
}

/**
 * API call helper function
 */
async function apiCall(endpoint, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const requestOptions = { ...defaultOptions, ...options };

    try {
        const response = await fetch(endpoint, requestOptions);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Export functions for global access
window.copyTerminalOutput = copyTerminalOutput;
window.clearTerminal = clearTerminal;
window.goBack = goBack;

// Clean up intervals when page is unloaded
window.addEventListener('beforeunload', function() {
    stopSyncMonitoring();
    stopTerminalUpdates();
}); 