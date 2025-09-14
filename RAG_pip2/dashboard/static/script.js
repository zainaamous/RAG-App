/**
 * Enhanced RAG Dashboard JavaScript
 * Handles real-time updates, WebSocket connections, and interactive features
 */

class RAGDashboard {
    constructor() {
        this.ws = null;
        this.stats = {};
        this.documents = [];
        this.isConnected = false;
        this.retryCount = 0;
        this.maxRetries = 5;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadInitialData();
        this.startPeriodicUpdates();
    }
    
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTab(item.dataset.tab);
            });
        });
        
        // Query form
        const queryForm = document.getElementById('queryForm');
        if (queryForm) {
            queryForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleQuery();
            });
        }
        
        // Ingest form
        const ingestForm = document.getElementById('ingestForm');
        if (ingestForm) {
            ingestForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleIngest();
            });
        }
        
        // File upload
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                this.handleFileUpload(e.target.files[0]);
            });
        }
        
        // Refresh buttons
        document.querySelectorAll('.btn-refresh').forEach(btn => {
            btn.addEventListener('click', () => {
                this.loadInitialData();
            });
        });
        
        // Delete document buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-delete')) {
                this.deleteDocument(e.target.dataset.docId);
            }
        });
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this.retryCount = 0;
                this.updateConnectionStatus(true);
                console.log('WebSocket connected');
            };
            
            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            };
            
            this.ws.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus(false);
                this.reconnectWebSocket();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.updateConnectionStatus(false);
        }
    }
    
    reconnectWebSocket() {
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            const delay = Math.min(1000 * Math.pow(2, this.retryCount), 10000);
            
            setTimeout(() => {
                console.log(`Reconnecting WebSocket (attempt ${this.retryCount})`);
                this.connectWebSocket();
            }, delay);
        }
    }
    
    updateConnectionStatus(connected) {
        const indicator = document.querySelector('.status-indicator');
        if (indicator) {
            indicator.classList.toggle('error', !connected);
            indicator.textContent = connected ? '● Connected' : '● Disconnected';
        }
    }
    
    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'document_ingested':
                this.showAlert('Document ingested successfully', 'success');
                this.loadDocuments();
                this.loadStats();
                break;
                
            case 'document_deleted':
                this.showAlert('Document deleted successfully', 'success');
                this.loadDocuments();
                this.loadStats();
                break;
                
            case 'batch_ingest_complete':
                this.showAlert(`Batch ingestion complete: ${message.data.successful} successful, ${message.data.failed} failed`, 'info');
                this.loadDocuments();
                this.loadStats();
                break;
                
            default:
                console.log('Unknown WebSocket message:', message);
        }
    }
    
    switchTab(tabName) {
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}Tab`).classList.add('active');
        
        // Load tab-specific data
        switch (tabName) {
            case 'dashboard':
                this.loadStats();
                break;
            case 'documents':
                this.loadDocuments();
                break;
            case 'query':
                // Query tab doesn't need additional loading
                break;
            case 'ingest':
                // Ingest tab doesn't need additional loading
                break;
        }
    }
    
    async loadInitialData() {
        await Promise.all([
            this.loadStats(),
            this.loadDocuments()
        ]);
    }
    
    async loadStats() {
        try {
            const response = await fetch('/stats');
            const data = await response.json();
            
            this.stats = data;
            this.updateStatsDisplay(data);
            
        } catch (error) {
            console.error('Failed to load stats:', error);
            this.showAlert('Failed to load statistics', 'error');
        }
    }
    
    updateStatsDisplay(stats) {
        // Update stat cards
        const statCards = document.querySelectorAll('.stat-card');
        statCards.forEach(card => {
            const key = card.dataset.stat;
            const value = this.getNestedValue(stats, key);
            
            if (value !== undefined) {
                const valueElement = card.querySelector('.stat-value');
                const labelElement = card.querySelector('.stat-label');
                
                if (valueElement) {
                    valueElement.textContent = this.formatStatValue(value, key);
                }
                
                if (labelElement) {
                    labelElement.textContent = this.formatStatLabel(key);
                }
            }
        });
        
        // Update system health
        this.updateSystemHealth(stats.system_health);
    }
    
    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    }
    
    formatStatValue(value, key) {
        if (typeof value === 'number') {
            if (key.includes('time') || key.includes('duration')) {
                return `${value.toFixed(2)}s`;
            } else if (key.includes('count') || key.includes('vectors')) {
                return value.toLocaleString();
            }
        }
        return value;
    }
    
    formatStatLabel(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    updateSystemHealth(health) {
        const healthElement = document.querySelector('.system-health');
        if (healthElement && health) {
            const status = health.api_status === 'healthy' ? 'success' : 'error';
            healthElement.innerHTML = `
                <div class="alert alert-${status}">
                    <span>API Status: ${health.api_status}</span>
                </div>
            `;
        }
    }
    
    async loadDocuments() {
        try {
            const response = await fetch('/documents');
            const data = await response.json();
            
            this.documents = data;
            this.updateDocumentsDisplay(data);
            
        } catch (error) {
            console.error('Failed to load documents:', error);
            this.showAlert('Failed to load documents', 'error');
        }
    }
    
    updateDocumentsDisplay(documents) {
        const tableBody = document.querySelector('#documentsTable tbody');
        if (!tableBody) return;
        
        tableBody.innerHTML = '';
        
        documents.forEach(doc => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <div class="font-medium">${doc.doc_uid.substring(0, 12)}...</div>
                    <div class="text-sm text-gray-500">${doc.doc_uid}</div>
                </td>
                <td>${doc.source}</td>
                <td><span class="badge badge-info">${doc.chunk_count}</span></td>
                <td>${doc.version || '1.0'}</td>
                <td>
                    <div class="flex gap-2">
                        <button class="btn btn-secondary btn-sm" onclick="dashboard.viewDocument('${doc.doc_uid}')">
                            View
                        </button>
                        <button class="btn btn-error btn-sm btn-delete" data-doc-id="${doc.doc_uid}">
                            Delete
                        </button>
                    </div>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    async handleQuery() {
        const queryInput = document.getElementById('queryInput');
        const queryResult = document.getElementById('queryResult');
        const queryLoading = document.getElementById('queryLoading');
        
        if (!queryInput.value.trim()) {
            this.showAlert('Please enter a question', 'warning');
            return;
        }
        
        queryLoading.style.display = 'block';
        queryResult.innerHTML = '';
        
        try {
            const response = await fetch('/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: queryInput.value,
                    namespace: 'library-global'
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayQueryResult(data);
                queryInput.value = '';
            } else {
                throw new Error(data.detail || 'Query failed');
            }
            
        } catch (error) {
            console.error('Query error:', error);
            this.showAlert(`Query failed: ${error.message}`, 'error');
        } finally {
            queryLoading.style.display = 'none';
        }
    }
    
    displayQueryResult(result) {
        const queryResult = document.getElementById('queryResult');
        
        queryResult.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Answer</h3>
                    <span class="badge badge-${this.getConfidenceBadgeClass(result.confidence)}">
                        Confidence: ${(result.confidence * 100).toFixed(1)}%
                    </span>
                </div>
                <div class="card-content">
                    <div class="prose max-w-none">
                        ${this.formatAnswer(result.answer)}
                    </div>
                    
                    ${result.sources.length > 0 ? `
                        <div class="mt-6">
                            <h4 class="font-semibold mb-3">Sources (${result.sources.length})</h4>
                            <div class="space-y-2">
                                ${result.sources.map((source, index) => `
                                    <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                                        <span class="badge badge-info">${index + 1}</span>
                                        <div class="flex-1">
                                            <div class="font-medium">${source.source}</div>
                                            <div class="text-sm text-gray-600">${source.content_preview}</div>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="mt-6 flex justify-between text-sm text-gray-500">
                        <span>Query Type: ${result.query_type}</span>
                        <span>Processing Time: ${result.processing_time.toFixed(2)}s</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    getConfidenceBadgeClass(confidence) {
        if (confidence >= 0.8) return 'success';
        if (confidence >= 0.6) return 'warning';
        return 'error';
    }
    
    formatAnswer(answer) {
        // Simple formatting - in a real app, you might use a markdown parser
        return answer
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }
    
    async handleIngest() {
        const contentInput = document.getElementById('contentInput');
        const sourceInput = document.getElementById('sourceInput');
        const ingestLoading = document.getElementById('ingestLoading');
        
        if (!contentInput.value.trim()) {
            this.showAlert('Please enter document content', 'warning');
            return;
        }
        
        ingestLoading.style.display = 'block';
        
        try {
            const response = await fetch('/ingest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: contentInput.value,
                    source: sourceInput.value || 'manual_input',
                    namespace: 'library-global'
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert('Document ingested successfully', 'success');
                contentInput.value = '';
                sourceInput.value = '';
                this.loadDocuments();
                this.loadStats();
            } else {
                throw new Error(data.detail || 'Ingestion failed');
            }
            
        } catch (error) {
            console.error('Ingestion error:', error);
            this.showAlert(`Ingestion failed: ${error.message}`, 'error');
        } finally {
            ingestLoading.style.display = 'none';
        }
    }
    
    async handleFileUpload(file) {
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('namespace', 'library-global');
        
        const uploadLoading = document.getElementById('uploadLoading');
        uploadLoading.style.display = 'block';
        
        try {
            const response = await fetch('/ingest/file', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(`File "${file.name}" ingested successfully`, 'success');
                this.loadDocuments();
                this.loadStats();
            } else {
                throw new Error(data.detail || 'File upload failed');
            }
            
        } catch (error) {
            console.error('File upload error:', error);
            this.showAlert(`File upload failed: ${error.message}`, 'error');
        } finally {
            uploadLoading.style.display = 'none';
            // Reset file input
            document.getElementById('fileInput').value = '';
        }
    }
    
    async deleteDocument(docId) {
        if (!confirm(`Are you sure you want to delete document ${docId}?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/documents/${docId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showAlert('Document deleted successfully', 'success');
                this.loadDocuments();
                this.loadStats();
            } else {
                const data = await response.json();
                throw new Error(data.detail || 'Deletion failed');
            }
            
        } catch (error) {
            console.error('Deletion error:', error);
            this.showAlert(`Deletion failed: ${error.message}`, 'error');
        }
    }
    
    viewDocument(docId) {
        // In a real implementation, you might open a modal or navigate to a detail page
        this.showAlert(`Viewing document ${docId} - Feature not implemented yet`, 'info');
    }
    
    showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alertContainer') || this.createAlertContainer();
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <span>${message}</span>
            <button class="ml-auto text-lg font-bold" onclick="this.parentElement.remove()">&times;</button>
        `;
        
        alertContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }
    
    createAlertContainer() {
        const container = document.createElement('div');
        container.id = 'alertContainer';
        container.className = 'fixed top-20 right-4 z-50 space-y-2';
        document.body.appendChild(container);
        return container;
    }
    
    startPeriodicUpdates() {
        // Update stats every 30 seconds
        setInterval(() => {
            if (this.isConnected) {
                this.loadStats();
            }
        }, 30000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new RAGDashboard();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Page is hidden, reduce update frequency
        console.log('Page hidden, reducing update frequency');
    } else {
        // Page is visible, resume normal updates
        console.log('Page visible, resuming updates');
        if (window.dashboard) {
            window.dashboard.loadInitialData();
        }
    }
});
