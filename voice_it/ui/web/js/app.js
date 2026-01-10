/**
 * Voice IT - Main Application Controller
 * Handles navigation, state management, and UI updates.
 */

const App = {
    // Current view
    currentView: 'home',

    // State
    state: {
        isRecording: false,
        isProcessing: false,
        isConnected: false,
        activeProvider: null,
    },

    // DOM elements cache
    elements: {},

    /**
     * Initialize the application
     */
    async init() {
        console.log('Voice IT initializing...');

        // Cache DOM elements
        this.cacheElements();

        // Set up event listeners
        this.setupEventListeners();

        // Wait for API
        try {
            await API.waitForReady();
            console.log('API ready');

            // Load initial data
            await this.loadInitialData();
        } catch (error) {
            console.error('Failed to initialize API:', error);
            this.updateStatus('API Error', false);
        }

        console.log('Voice IT initialized');
    },

    /**
     * Cache frequently accessed DOM elements
     */
    cacheElements() {
        this.elements = {
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),
            micContainer: document.getElementById('micContainer'),
            micBtn: document.getElementById('micBtn'),
            statusMain: document.getElementById('statusMain'),
            recentList: document.getElementById('recentList'),
            historyList: document.getElementById('historyList'),
            historySearch: document.getElementById('historySearch'),
            historyCount: document.getElementById('historyCount'),
            settingsList: document.getElementById('settingsList'),
            views: document.querySelectorAll('.view'),
            navBtns: document.querySelectorAll('.nav-btn'),
        };
    },

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Navigation buttons
        this.elements.navBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const view = btn.dataset.nav;
                this.navigateTo(view);
            });
        });

        // History search
        if (this.elements.historySearch) {
            let debounceTimer;
            this.elements.historySearch.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.searchHistory(e.target.value);
                }, 300);
            });
        }
    },

    /**
     * Load initial data from API
     */
    async loadInitialData() {
        try {
            // Get provider status
            const status = await API.getProvidersStatus();
            this.state.activeProvider = status.active;

            // Check if any provider is connected
            const connectedProvider = Object.values(status.providers).find(p => p.connected);
            this.state.isConnected = !!connectedProvider;

            // Show the connected provider's name (short version for header)
            const displayName = connectedProvider
                ? this.getShortProviderName(connectedProvider.id)
                : 'OFFLINE';
            this.updateStatus(displayName, !!connectedProvider);

            // Load recent history for home view
            await this.loadRecentHistory();

        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    },

    /**
     * Navigate to a view
     */
    navigateTo(view) {
        if (this.currentView === view) return;

        // Update active nav button
        this.elements.navBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.nav === view);
        });

        // Update active view
        this.elements.views.forEach(v => {
            v.classList.toggle('active', v.dataset.view === view);
        });

        this.currentView = view;

        // Load view-specific data
        this.onViewChange(view);
    },

    /**
     * Handle view change - load data for the new view
     */
    async onViewChange(view) {
        switch (view) {
            case 'home':
                await this.loadRecentHistory();
                break;
            case 'history':
                await this.loadHistory();
                break;
            case 'settings':
                await this.loadSettings();
                break;
        }
    },

    /**
     * Update status indicator
     */
    updateStatus(text, connected) {
        if (this.elements.statusText) {
            this.elements.statusText.textContent = text;
        }
        if (this.elements.statusDot) {
            this.elements.statusDot.classList.toggle('connected', connected);
        }
    },

    /**
     * Get short display name for provider (for header badge)
     */
    getShortProviderName(providerId) {
        const names = {
            'groq': 'GROQ',
            'chatgpt': 'OPENAI',
            'gemini': 'GEMINI',
            'grok': 'GROK',
        };
        return names[providerId] || providerId?.toUpperCase() || 'CONNECTED';
    },

    // =========================================================================
    // STATE CHANGE HANDLERS (called from Python)
    // =========================================================================

    /**
     * Handle state changes from Python
     */
    onStateChange(state, data) {
        console.log('State change:', state, data);

        switch (state) {
            case 'recording':
                this.setRecordingState(data?.active || false);
                break;
            case 'processing':
                this.setProcessingState(data?.active || false);
                break;
            case 'transcription':
                this.onTranscription(data?.text, data?.success);
                break;
            case 'error':
                this.onError(data?.message);
                break;
        }
    },

    /**
     * Handle provider connection result
     */
    onProviderConnected(providerId, success) {
        console.log('Provider connected:', providerId, success);
        if (success) {
            this.state.activeProvider = providerId;
            this.state.isConnected = true;
            this.updateStatus(this.getShortProviderName(providerId), true);
        }
        // Reload settings view if visible
        if (this.currentView === 'settings') {
            this.loadSettings();
        }
    },

    /**
     * Handle provider error
     */
    onProviderError(providerId, error) {
        console.error('Provider error:', providerId, error);
        // Could show a toast notification here
    },

    /**
     * Set recording state
     */
    setRecordingState(isRecording) {
        this.state.isRecording = isRecording;

        if (this.elements.micContainer) {
            this.elements.micContainer.classList.toggle('recording', isRecording);
            this.elements.micContainer.classList.remove('processing');
        }

        if (this.elements.statusDot) {
            this.elements.statusDot.classList.toggle('recording', isRecording);
            this.elements.statusDot.classList.remove('processing');
        }

        if (this.elements.statusMain) {
            this.elements.statusMain.textContent = isRecording
                ? 'Recording...'
                : 'Ready to transcribe';
        }
    },

    /**
     * Set processing state
     */
    setProcessingState(isProcessing) {
        this.state.isProcessing = isProcessing;

        if (this.elements.micContainer) {
            this.elements.micContainer.classList.toggle('processing', isProcessing);
            this.elements.micContainer.classList.remove('recording');
        }

        if (this.elements.statusDot) {
            this.elements.statusDot.classList.toggle('processing', isProcessing);
            this.elements.statusDot.classList.remove('recording');
        }

        if (this.elements.statusMain) {
            this.elements.statusMain.textContent = isProcessing
                ? 'Processing...'
                : 'Ready to transcribe';
        }
    },

    /**
     * Handle transcription result
     */
    onTranscription(text, success) {
        this.setRecordingState(false);
        this.setProcessingState(false);

        if (success && text) {
            // Refresh recent history
            this.loadRecentHistory();
        }
    },

    /**
     * Handle error
     */
    onError(message) {
        console.error('Error:', message);
        this.setRecordingState(false);
        this.setProcessingState(false);

        if (this.elements.statusMain) {
            this.elements.statusMain.textContent = message || 'Error occurred';
            setTimeout(() => {
                this.elements.statusMain.textContent = 'Ready to transcribe';
            }, 3000);
        }
    },

    // =========================================================================
    // DATA LOADING
    // =========================================================================

    /**
     * Load recent history for home view
     */
    async loadRecentHistory() {
        try {
            const history = await API.getHistory(3, 0, '');

            if (!this.elements.recentList) return;

            if (!history || history.length === 0) {
                this.elements.recentList.innerHTML = `
                    <div class="recent-empty">No transcriptions yet</div>
                `;
                return;
            }

            this.elements.recentList.innerHTML = history.map(item => `
                <div class="recent-item" data-id="${item.id}">
                    <div class="recent-text">${this.escapeHtml(item.text)}</div>
                    <div class="recent-time">${this.formatTime(item.created_at)}</div>
                </div>
            `).join('');

        } catch (error) {
            console.error('Failed to load recent history:', error);
        }
    },

    /**
     * Load full history
     */
    async loadHistory() {
        try {
            const history = await API.getHistory(50, 0, '');

            if (this.elements.historyCount) {
                this.elements.historyCount.textContent = history?.length || 0;
            }

            if (!this.elements.historyList) return;

            if (!history || history.length === 0) {
                this.elements.historyList.innerHTML = `
                    <div class="empty-state">
                        <i data-lucide="clock"></i>
                        <p class="empty-state-text">No history yet</p>
                    </div>
                `;
                lucide.createIcons();
                return;
            }

            this.elements.historyList.innerHTML = history.map(item => `
                <div class="card history-card" data-id="${item.id}">
                    <div class="card-content">
                        <p class="card-text">${this.escapeHtml(item.text)}</p>
                        <span class="card-time">${this.formatTime(item.created_at)}</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn-icon" onclick="App.copyHistoryItem(${item.id}, '${this.escapeHtml(item.text).replace(/'/g, "\\'")}')">
                            <i data-lucide="copy"></i>
                        </button>
                        <button class="btn-icon btn-danger" onclick="App.deleteHistoryItem(${item.id})">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                </div>
            `).join('');

            lucide.createIcons();

        } catch (error) {
            console.error('Failed to load history:', error);
        }
    },

    /**
     * Search history
     */
    async searchHistory(query) {
        try {
            const history = await API.getHistory(50, 0, query);

            if (this.elements.historyCount) {
                this.elements.historyCount.textContent = history?.length || 0;
            }

            if (!this.elements.historyList) return;

            if (!history || history.length === 0) {
                this.elements.historyList.innerHTML = `
                    <div class="empty-state">
                        <i data-lucide="search"></i>
                        <p class="empty-state-text">${query ? 'No results found' : 'No history yet'}</p>
                    </div>
                `;
                lucide.createIcons();
                return;
            }

            this.elements.historyList.innerHTML = history.map(item => `
                <div class="card history-card" data-id="${item.id}">
                    <div class="card-content">
                        <p class="card-text">${this.escapeHtml(item.text)}</p>
                        <span class="card-time">${this.formatTime(item.created_at)}</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn-icon" onclick="App.copyHistoryItem(${item.id}, '${this.escapeHtml(item.text).replace(/'/g, "\\'")}')">
                            <i data-lucide="copy"></i>
                        </button>
                        <button class="btn-icon btn-danger" onclick="App.deleteHistoryItem(${item.id})">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                </div>
            `).join('');

            lucide.createIcons();

        } catch (error) {
            console.error('Failed to search history:', error);
        }
    },

    /**
     * Copy history item
     */
    async copyHistoryItem(id, text) {
        try {
            await API.copyToClipboard(text);
            // Could show a toast notification
        } catch (error) {
            console.error('Failed to copy:', error);
        }
    },

    /**
     * Delete history item
     */
    async deleteHistoryItem(id) {
        try {
            await API.deleteHistoryEntry(id);
            await this.loadHistory();
            await this.loadRecentHistory();
        } catch (error) {
            console.error('Failed to delete:', error);
        }
    },

    /**
     * Load settings
     */
    async loadSettings() {
        console.log('loadSettings called');
        try {
            console.log('Loading settings data...');

            const providersStatus = await API.getProvidersStatus();
            console.log('providersStatus:', providersStatus);

            const hotkeyConfig = await API.getHotkeyConfig();
            console.log('hotkeyConfig:', hotkeyConfig);

            const language = await API.getLanguage();
            console.log('language:', language);

            const languages = await API.getSupportedLanguages();
            console.log('languages:', languages);

            console.log('settingsList element:', this.elements.settingsList);
            if (!this.elements.settingsList) {
                console.error('settingsList element not found!');
                return;
            }

            const providers = providersStatus.providers;
            const activeProvider = providersStatus.active;

            this.elements.settingsList.innerHTML = `
                <!-- Provider Section -->
                <div class="settings-section">
                    <div class="settings-section-title">
                        <i data-lucide="cpu"></i>
                        <span>AI Provider</span>
                    </div>
                    <div class="provider-cards">
                        ${Object.values(providers).map(p => `
                            <div class="provider-card ${p.connected ? 'connected' : ''} ${p.id === activeProvider ? 'active' : ''}"
                                 data-provider="${p.id}">
                                <div class="provider-info">
                                    <span class="provider-name">${p.name}</span>
                                    <span class="provider-status">${p.connected ? 'Connected' : 'Not connected'}</span>
                                </div>
                                <button class="btn btn-sm ${p.connected ? 'btn-ghost' : 'btn-primary'}"
                                        onclick="App.toggleProvider('${p.id}', ${p.connected})">
                                    ${p.connected ? 'Disconnect' : 'Connect'}
                                </button>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <!-- Hotkey Section -->
                <div class="settings-section">
                    <div class="settings-section-title">
                        <i data-lucide="keyboard"></i>
                        <span>Hotkey</span>
                    </div>
                    <div class="setting-row">
                        <span class="setting-label">Dictation</span>
                        <kbd class="hotkey-display">${hotkeyConfig.dictation?.join(' + ') || 'Ctrl + Win'}</kbd>
                    </div>
                </div>

                <!-- About Section -->
                <div class="settings-section">
                    <div class="settings-section-title">
                        <i data-lucide="info"></i>
                        <span>About</span>
                    </div>
                    <div class="setting-row">
                        <span class="setting-label">Version</span>
                        <span class="setting-value">1.0.0</span>
                    </div>
                </div>
            `;

            console.log('Settings HTML set, creating icons...');
            lucide.createIcons();
            console.log('Settings loaded successfully');

        } catch (error) {
            console.error('Failed to load settings:', error);
            // Show error in the settings list
            if (this.elements.settingsList) {
                this.elements.settingsList.innerHTML = `
                    <div class="empty-state">
                        <p class="empty-state-text">Error loading settings: ${error.message}</p>
                    </div>
                `;
            }
        }
    },

    /**
     * Toggle provider connection
     */
    async toggleProvider(providerId, isConnected) {
        try {
            if (isConnected) {
                await API.disconnectProvider(providerId);
                // Update status
                this.state.isConnected = false;
                this.state.activeProvider = null;
                this.updateStatus('OFFLINE', false);
                // Reload settings to update UI
                await this.loadSettings();
            } else {
                // Check if another provider is already connected
                const status = await API.getProvidersStatus();
                const connectedProvider = Object.values(status.providers).find(p => p.connected);

                if (connectedProvider) {
                    this.showErrorMessage(`Please disconnect ${connectedProvider.name} first before connecting another provider.`);
                    return;
                }

                const provider = status.providers[providerId];

                if (provider && provider.requires_api_key) {
                    this.showApiKeyModal(providerId, provider.name);
                } else {
                    await API.connectProvider(providerId);
                }
            }
            // Settings will be reloaded when onProviderConnected is called
        } catch (error) {
            console.error('Failed to toggle provider:', error);
        }
    },

    /**
     * Show error message to user
     */
    showErrorMessage(message) {
        const modal = document.getElementById('errorModal');
        const messageEl = document.getElementById('errorMessage');

        if (messageEl) {
            messageEl.textContent = message;
        }
        if (modal) {
            modal.classList.remove('hidden');
        }
    },

    /**
     * Close error modal
     */
    closeErrorModal() {
        const modal = document.getElementById('errorModal');
        if (modal) {
            modal.classList.add('hidden');
        }
    },

    /**
     * Show API key modal
     */
    showApiKeyModal(providerId, providerName) {
        this.currentApiKeyProvider = providerId;
        const modal = document.getElementById('apiKeyModal');
        const description = document.getElementById('apiKeyProviderName');
        const input = document.getElementById('apiKeyInput');

        if (description) {
            description.textContent = `Enter your ${providerName} API key:`;
        }
        if (input) {
            input.value = '';
        }
        if (modal) {
            modal.classList.remove('hidden');
            // Focus input after modal appears
            setTimeout(() => input?.focus(), 100);
        }

        // Reinitialize icons in modal
        lucide.createIcons();
    },

    /**
     * Close API key modal
     */
    closeApiKeyModal() {
        const modal = document.getElementById('apiKeyModal');
        const input = document.getElementById('apiKeyInput');

        if (modal) {
            modal.classList.add('hidden');
        }
        if (input) {
            input.value = '';
        }
        this.currentApiKeyProvider = null;
    },

    /**
     * Submit API key
     */
    async submitApiKey() {
        const input = document.getElementById('apiKeyInput');
        const apiKey = input?.value?.trim();

        if (!apiKey) {
            return;
        }

        if (!this.currentApiKeyProvider) {
            console.error('No provider selected');
            return;
        }

        try {
            await API.connectProviderWithKey(this.currentApiKeyProvider, apiKey);
            this.closeApiKeyModal();
        } catch (error) {
            console.error('Failed to connect with API key:', error);
        }
    },

    /**
     * Set language
     */
    async setLanguage(language) {
        try {
            await API.setLanguage(language);
        } catch (error) {
            console.error('Failed to set language:', error);
        }
    },

    // =========================================================================
    // UTILITIES
    // =========================================================================

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Format timestamp
     */
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        // Less than a minute
        if (diff < 60000) {
            return 'Just now';
        }

        // Less than an hour
        if (diff < 3600000) {
            const mins = Math.floor(diff / 60000);
            return `${mins}m ago`;
        }

        // Less than a day
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours}h ago`;
        }

        // Format as date
        return date.toLocaleDateString();
    },
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Wait for pywebview
    window.addEventListener('pywebviewready', () => {
        App.init();
    });

    // Fallback initialization after timeout
    setTimeout(() => {
        if (!window.pywebview) {
            console.log('Running without PyWebView (development mode)');
            // Mock API for development
            window.pywebview = {
                api: {
                    get_providers_status: () => ({
                        providers: {
                            groq: { id: 'groq', name: 'Groq (Whisper)', connected: false, requires_api_key: true },
                            claude: { id: 'claude', name: 'Claude', connected: false, requires_api_key: false },
                            chatgpt: { id: 'chatgpt', name: 'ChatGPT', connected: false, requires_api_key: false },
                            gemini: { id: 'gemini', name: 'Gemini', connected: false, requires_api_key: false },
                        },
                        active: 'groq',
                    }),
                    get_history: () => [],
                    get_hotkey_config: () => ({ dictation: ['ctrl', 'win'], command_mode: ['ctrl', 'shift', 'win'] }),
                    get_language: () => 'en',
                    get_supported_languages: () => [
                        { code: 'en', name: 'English' },
                        { code: 'es', name: 'Spanish' },
                    ],
                    connect_provider_with_key: (providerId, apiKey) => ({ status: 'connecting', provider: providerId }),
                },
            };
            App.init();
        }
    }, 1000);
});

// Make App globally available
window.App = App;
