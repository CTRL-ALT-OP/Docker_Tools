/**
 * Docker Tools Web Interface JavaScript
 * Handles button interactions and AJAX calls to mirror desktop app functionality
 */

// Global state
let currentProject = null;
let loadingRequests = new Set();
let syncCheckInterval = null;
let lastKnownDesktopSelection = null;

// DOM Elements
const statusMessage = document.getElementById('status-message');
const loadingIndicator = document.getElementById('loading-indicator');
const projectSelector = document.getElementById('project-selector');
const resultModal = document.getElementById('result-modal');
const addProjectModal = document.getElementById('add-project-modal');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadCurrentProject();
    startSyncMonitoring();
});

/**
 * Initialize event listeners for navigation and UI elements
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

    // Navigation buttons
    const refreshBtn = document.getElementById('refresh-btn');
    const addProjectBtn = document.getElementById('add-project-btn');
    const settingsBtn = document.getElementById('settings-btn');

    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshProjects);
    }

    if (addProjectBtn) {
        addProjectBtn.addEventListener('click', showAddProjectModal);
    }

    if (settingsBtn) {
        settingsBtn.addEventListener('click', showSettings);
    }

    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === resultModal) {
            closeModal();
        }
        if (event.target === addProjectModal) {
            closeAddProjectModal();
        }
    });

    // Auto-fill project name when URL changes
    const repoUrlInput = document.getElementById('repo-url');
    if (repoUrlInput) {
        repoUrlInput.addEventListener('input', autoFillProjectName);
    }

    // Handle page visibility changes to resume sync monitoring
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // Resume sync monitoring when page becomes visible
            startSyncMonitoring();
        } else {
            // Pause sync monitoring when page is hidden
            stopSyncMonitoring();
        }
    });
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
                lastDesktopChange !== currentProject) {
                
                lastKnownDesktopSelection = lastDesktopChange;
                
                // Update dropdown without triggering change event
                updateDropdownSelection(lastDesktopChange);
                
                // Update current project state
                currentProject = lastDesktopChange;
                
                // Show notification
                updateStatus(`Desktop selection changed to: ${lastDesktopChange}`, 'info');
                
                // Reload page to show updated project
                setTimeout(() => {
                    window.location.href = `/?group=${encodeURIComponent(lastDesktopChange)}`;
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
 * Load current project information
 */
function loadCurrentProject() {
    const selectedProject = projectSelector ? projectSelector.value : null;
    if (selectedProject) {
        currentProject = selectedProject;
        lastKnownDesktopSelection = selectedProject;
        updateStatus(`Current project: ${selectedProject}`);
    }
}

/**
 * Update status message
 */
function updateStatus(message, type = 'info') {
    if (statusMessage) {
        statusMessage.textContent = message;
        statusMessage.className = `status-${type}`;
    }
}

/**
 * Show/hide loading indicator
 */
function setLoading(isLoading, requestId = null) {
    if (isLoading && requestId) {
        loadingRequests.add(requestId);
    } else if (!isLoading && requestId) {
        loadingRequests.delete(requestId);
    }

    const hasLoading = loadingRequests.size > 0;
    if (loadingIndicator) {
        loadingIndicator.style.display = hasLoading ? 'flex' : 'none';
    }
}

/**
 * Make API call with error handling
 */
async function apiCall(endpoint, options = {}) {
    const requestId = Date.now();
    setLoading(true, requestId);

    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    } finally {
        setLoading(false, requestId);
    }
}

/**
 * Show result modal with action results
 */
function showResultModal(title, message, details = null, type = 'info') {
    const modal = document.getElementById('result-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalDetails = document.getElementById('modal-details');

    if (modalTitle) modalTitle.textContent = title;
    if (modalMessage) {
        modalMessage.innerHTML = `<div class="message ${type}">${message}</div>`;
    }
    if (modalDetails) {
        modalDetails.innerHTML = details ? `<div class="terminal-output">${details}</div>` : '';
    }

    modal.classList.add('show');
}

/**
 * Close result modal
 */
function closeModal() {
    const modal = document.getElementById('result-modal');
    modal.classList.remove('show');
}

/**
 * Show add project modal
 */
function showAddProjectModal() {
    const modal = document.getElementById('add-project-modal');
    modal.classList.add('show');
}

/**
 * Close add project modal
 */
function closeAddProjectModal() {
    const modal = document.getElementById('add-project-modal');
    modal.classList.remove('show');
    
    // Reset form
    const form = document.getElementById('add-project-form');
    if (form) form.reset();
}

/**
 * Auto-fill project name from GitHub URL
 */
function autoFillProjectName() {
    const repoUrlInput = document.getElementById('repo-url');
    const projectNameInput = document.getElementById('project-name');
    
    if (!repoUrlInput || !projectNameInput) return;

    const url = repoUrlInput.value.trim();
    if (!url) return;

    try {
        // Extract project name from GitHub URL
        const match = url.match(/github\.com\/[^/]+\/([^/]+?)(?:\.git)?(?:\/|$)/);
        if (match) {
            projectNameInput.value = match[1];
        }
    } catch (error) {
        console.error('Error parsing GitHub URL:', error);
    }
}

/**
 * Refresh projects
 */
async function refreshProjects() {
    updateStatus('Refreshing projects...');
    
    try {
        const result = await apiCall('/api/refresh');
        if (result.success) {
            updateStatus('Projects refreshed successfully', 'success');
            // Reload the page to show updated projects
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            updateStatus('Failed to refresh projects', 'error');
        }
    } catch (error) {
        updateStatus('Error refreshing projects', 'error');
        console.error('Refresh failed:', error);
    }
}

/**
 * Select project - calls the same method as GUI dropdown
 */
async function selectProject(groupName) {
    updateStatus(`Selecting project: ${groupName}...`);
    
    try {
        const result = await apiCall('/api/select-project', {
            method: 'POST',
            body: JSON.stringify({ group_name: groupName })
        });
        
        if (result.success) {
            updateStatus(`Selected project: ${groupName}`, 'success');
            currentProject = groupName;
            lastKnownDesktopSelection = groupName;
            
            // Reload the page to show the selected project
            setTimeout(() => {
                window.location.href = `/?group=${encodeURIComponent(groupName)}`;
            }, 500);
        } else {
            updateStatus(`Failed to select project: ${result.message}`, 'error');
            showResultModal('Project Selection Error', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error selecting project', 'error');
        console.error('Project selection failed:', error);
        showResultModal('Project Selection Error', 'Failed to select project. Please try again.', null, 'error');
    }
}

/**
 * Show settings
 */
async function showSettings() {
    try {
        const result = await apiCall('/api/action/settings', {
            method: 'POST',
            body: JSON.stringify({})
        });

        if (result.success) {
            showResultModal('Settings', result.message, null, 'info');
        } else {
            showResultModal('Settings Error', result.message, null, 'error');
        }
    } catch (error) {
        showResultModal('Settings Error', 'An error occurred while accessing settings.', error.message, 'error');
    }
}

/**
 * Add new project
 */
async function addProject() {
    const repoUrlInput = document.getElementById('repo-url');
    const projectNameInput = document.getElementById('project-name');
    
    if (!repoUrlInput || !projectNameInput) return;

    const repoUrl = repoUrlInput.value.trim();
    const projectName = projectNameInput.value.trim();

    if (!repoUrl || !projectName) {
        alert('Please fill in both repository URL and project name.');
        return;
    }

    updateStatus('Adding project...');
    
    try {
        const result = await apiCall('/api/action/add-project', {
            method: 'POST',
            body: JSON.stringify({
                repo_url: repoUrl,
                project_name: projectName
            })
        });

        if (result.success) {
            updateStatus('Project added successfully', 'success');
            showResultModal('Add Project', result.message, null, 'success');
            closeAddProjectModal();
            
            // Refresh the page to show the new project
            setTimeout(() => {
                refreshProjects();
            }, 1500);
        } else {
            updateStatus('Failed to add project', 'error');
            showResultModal('Add Project Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error adding project', 'error');
        showResultModal('Add Project Error', 'An error occurred while adding the project.', error.message, 'error');
    }
}

// =============================================================================
// PROJECT ACTIONS - These mirror the desktop app functionality
// =============================================================================

/**
 * Cleanup project
 */
async function cleanupProject(projectName, parentFolder) {
    updateStatus(`Cleaning up project: ${projectName}...`);
    
    try {
        const result = await apiCall('/api/action/cleanup', {
            method: 'POST',
            body: JSON.stringify({
                project_name: projectName,
                parent_folder: parentFolder
            })
        });

        if (result.success) {
            updateStatus('Project cleanup completed', 'success');
            showResultModal(
                'Cleanup Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Project cleanup failed', 'error');
            showResultModal('Cleanup Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during cleanup', 'error');
        showResultModal('Cleanup Error', 'An error occurred during cleanup.', error.message, 'error');
    }
}

/**
 * Archive project
 */
async function archiveProject(projectName, parentFolder) {
    updateStatus(`Archiving project: ${projectName}...`);
    
    try {
        const result = await apiCall('/api/action/archive', {
            method: 'POST',
            body: JSON.stringify({
                project_name: projectName,
                parent_folder: parentFolder
            })
        });

        if (result.success) {
            updateStatus('Project archiving completed', 'success');
            showResultModal(
                'Archive Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Project archiving failed', 'error');
            showResultModal('Archive Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during archiving', 'error');
        showResultModal('Archive Error', 'An error occurred during archiving.', error.message, 'error');
    }
}

/**
 * Docker build and test
 */
async function dockerBuildTest(projectName, parentFolder) {
    updateStatus(`Docker build and test for: ${projectName}...`);
    
    try {
        const result = await apiCall('/api/action/docker', {
            method: 'POST',
            body: JSON.stringify({
                project_name: projectName,
                parent_folder: parentFolder
            })
        });

        if (result.success) {
            updateStatus('Docker build and test completed', 'success');
            showResultModal(
                'Docker Build Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Docker build and test failed', 'error');
            showResultModal('Docker Build Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during Docker build', 'error');
        showResultModal('Docker Error', 'An error occurred during Docker build.', error.message, 'error');
    }
}

/**
 * Git view
 */
async function gitView(projectName, parentFolder) {
    updateStatus(`Git view for: ${projectName}...`);
    
    try {
        const result = await apiCall('/api/action/git-view', {
            method: 'POST',
            body: JSON.stringify({
                project_name: projectName,
                parent_folder: parentFolder
            })
        });

        if (result.success) {
            updateStatus('Git view completed', 'success');
            showResultModal(
                'Git View',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Git view failed', 'error');
            showResultModal('Git View Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during Git view', 'error');
        showResultModal('Git Error', 'An error occurred during Git view.', error.message, 'error');
    }
}

/**
 * Open file manager (placeholder - would need platform-specific implementation)
 */
function openFileManager(projectPath) {
    showResultModal(
        'File Manager',
        `File manager functionality is not available in the web version. Project path: ${projectPath}`,
        null,
        'info'
    );
}

// =============================================================================
// PROJECT GROUP ACTIONS - These apply to all versions
// =============================================================================

/**
 * Sync run tests
 */
async function syncRunTests(groupName) {
    updateStatus(`Syncing run_tests.sh for: ${groupName}...`);
    
    try {
        const result = await apiCall('/api/action/sync-run-tests', {
            method: 'POST',
            body: JSON.stringify({
                group_name: groupName
            })
        });

        if (result.success) {
            updateStatus('Run tests sync completed', 'success');
            showResultModal(
                'Sync Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Run tests sync failed', 'error');
            showResultModal('Sync Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during sync', 'error');
        showResultModal('Sync Error', 'An error occurred during sync.', error.message, 'error');
    }
}

/**
 * Edit run tests
 */
async function editRunTests(groupName) {
    updateStatus(`Editing run tests for: ${groupName}...`);
    
    try {
        const result = await apiCall('/api/action/edit-run-tests', {
            method: 'POST',
            body: JSON.stringify({
                group_name: groupName
            })
        });

        if (result.success) {
            updateStatus('Edit run tests accessed', 'success');
            showResultModal('Edit Run Tests', result.message, null, 'info');
        } else {
            updateStatus('Edit run tests failed', 'error');
            showResultModal('Edit Run Tests Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during edit run tests', 'error');
        showResultModal('Edit Run Tests Error', 'An error occurred while accessing edit run tests.', error.message, 'error');
    }
}

/**
 * Validate project group
 */
async function validateProjectGroup(groupName) {
    updateStatus(`Validating project group: ${groupName}...`);
    
    try {
        const result = await apiCall('/api/action/validate-project-group', {
            method: 'POST',
            body: JSON.stringify({
                group_name: groupName
            })
        });

        if (result.success) {
            updateStatus('Project group validation completed', 'success');
            showResultModal(
                'Validation Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Project group validation failed', 'error');
            showResultModal('Validation Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during validation', 'error');
        showResultModal('Validation Error', 'An error occurred during validation.', error.message, 'error');
    }
}

/**
 * Build Docker files
 */
async function buildDockerFiles(groupName) {
    updateStatus(`Building Docker files for: ${groupName}...`);
    
    try {
        const result = await apiCall('/api/action/build-docker-files', {
            method: 'POST',
            body: JSON.stringify({
                group_name: groupName
            })
        });

        if (result.success) {
            updateStatus('Docker files build completed', 'success');
            showResultModal(
                'Build Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Docker files build failed', 'error');
            showResultModal('Build Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during Docker files build', 'error');
        showResultModal('Build Error', 'An error occurred during Docker files build.', error.message, 'error');
    }
}

/**
 * Git checkout all
 */
async function gitCheckoutAll(groupName) {
    updateStatus(`Git checkout all for: ${groupName}...`);
    
    try {
        const result = await apiCall('/api/action/git-checkout-all', {
            method: 'POST',
            body: JSON.stringify({
                group_name: groupName
            })
        });

        if (result.success) {
            updateStatus('Git checkout all completed', 'success');
            showResultModal(
                'Checkout Complete',
                result.message,
                result.result ? JSON.stringify(result.result, null, 2) : null,
                'success'
            );
        } else {
            updateStatus('Git checkout all failed', 'error');
            showResultModal('Checkout Failed', result.message, null, 'error');
        }
    } catch (error) {
        updateStatus('Error during Git checkout all', 'error');
        showResultModal('Checkout Error', 'An error occurred during Git checkout all.', error.message, 'error');
    }
}

/**
 * Open terminal view
 */
function openTerminal() {
    const currentGroup = projectSelector ? projectSelector.value : null;
    const url = currentGroup ? `/terminal?group=${encodeURIComponent(currentGroup)}` : '/terminal';
    window.location.href = url;
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Format error message for display
 */
function formatErrorMessage(error) {
    if (typeof error === 'string') {
        return error;
    }
    if (error.message) {
        return error.message;
    }
    return 'An unknown error occurred';
}

/**
 * Debounce function to limit API calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Clean up intervals when page is unloaded
window.addEventListener('beforeunload', function() {
    stopSyncMonitoring();
});

// Make functions available globally for onclick handlers
window.cleanupProject = cleanupProject;
window.archiveProject = archiveProject;
window.dockerBuildTest = dockerBuildTest;
window.gitView = gitView;
window.openFileManager = openFileManager;
window.syncRunTests = syncRunTests;
window.editRunTests = editRunTests;
window.validateProjectGroup = validateProjectGroup;
window.buildDockerFiles = buildDockerFiles;
window.gitCheckoutAll = gitCheckoutAll;
window.closeModal = closeModal;
window.closeAddProjectModal = closeAddProjectModal;
window.addProject = addProject;
window.openTerminal = openTerminal; 