/**
 * Voice IT - API Wrapper
 * Wraps PyWebView API calls with error handling and async support.
 */

const API = {
    /**
     * Check if PyWebView API is ready
     */
    isReady() {
        return window.pywebview && window.pywebview.api;
    },

    /**
     * Wait for PyWebView API to be ready
     */
    async waitForReady(timeout = 5000) {
        const start = Date.now();
        while (!this.isReady()) {
            if (Date.now() - start > timeout) {
                throw new Error('PyWebView API timeout');
            }
            await new Promise(resolve => setTimeout(resolve, 50));
        }
        return true;
    },

    /**
     * Call a Python API method
     */
    async call(method, ...args) {
        if (!this.isReady()) {
            await this.waitForReady();
        }
        try {
            return await window.pywebview.api[method](...args);
        } catch (error) {
            console.error(`API call failed: ${method}`, error);
            throw error;
        }
    },

    // =========================================================================
    // APP INFO
    // =========================================================================

    async getAppInfo() {
        return this.call('get_app_info');
    },

    // =========================================================================
    // CONFIGURATION
    // =========================================================================

    async getConfig(key) {
        return this.call('get_config', key);
    },

    async setConfig(key, value) {
        return this.call('set_config', key, value);
    },

    async getAllConfig() {
        return this.call('get_all_config');
    },

    // =========================================================================
    // PROVIDERS
    // =========================================================================

    async getProvidersStatus() {
        return this.call('get_providers_status');
    },

    async connectProvider(providerId) {
        return this.call('connect_provider', providerId);
    },

    async disconnectProvider(providerId) {
        return this.call('disconnect_provider', providerId);
    },

    async setActiveProvider(providerId) {
        return this.call('set_active_provider', providerId);
    },

    async connectProviderWithKey(providerId, apiKey) {
        return this.call('connect_provider_with_key', providerId, apiKey);
    },

    // =========================================================================
    // HISTORY
    // =========================================================================

    async getHistory(limit = 50, offset = 0, search = '') {
        return this.call('get_history', limit, offset, search);
    },

    async deleteHistoryEntry(entryId) {
        return this.call('delete_history_entry', entryId);
    },

    async clearAllHistory() {
        return this.call('clear_all_history');
    },

    // =========================================================================
    // CLIPBOARD
    // =========================================================================

    async copyToClipboard(text) {
        return this.call('copy_to_clipboard', text);
    },

    async pasteText(text) {
        return this.call('paste_text', text);
    },

    async getClipboard() {
        return this.call('get_clipboard');
    },

    // =========================================================================
    // APP CONTROL
    // =========================================================================

    async minimizeToTray() {
        return this.call('minimize_to_tray');
    },

    async quitApp() {
        return this.call('quit_app');
    },

    // =========================================================================
    // HOTKEYS
    // =========================================================================

    async getHotkeyConfig() {
        return this.call('get_hotkey_config');
    },

    async setHotkey(mode, keys) {
        return this.call('set_hotkey', mode, keys);
    },

    // =========================================================================
    // LANGUAGE
    // =========================================================================

    async getLanguage() {
        return this.call('get_language');
    },

    async setLanguage(language) {
        return this.call('set_language', language);
    },

    async getSupportedLanguages() {
        return this.call('get_supported_languages');
    },
};

// Make API globally available
window.API = API;
