document.addEventListener('DOMContentLoaded', () => {
    // Toast Helper
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        let icon = 'ℹ️';
        if (type === 'error') icon = '❌';
        if (type === 'success') icon = '✅';

        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => toast.remove(), 4000);
    }

    // Configure Marked.js + Highlight.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function (code, lang) {
                const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                return hljs.highlight(code, { language }).value;
            },
            langPrefix: 'hljs language-'
        });
    }

    let historyChartInstance = null;

    // Add Registration Modal Logic
    const regModal = document.getElementById('register-modal');
    const openRegBtn = document.getElementById('btn-open-register');
    const closeRegBtn = document.getElementById('btn-close-modal');
    const cancelRegBtn = document.getElementById('btn-cancel-reg');
    const regForm = document.getElementById('register-form');

    function toggleModal(show) {
        if (show) {
            regModal.classList.add('active');
        } else {
            regModal.classList.remove('active');
            regForm.reset();
        }
    }

    if (openRegBtn) openRegBtn.addEventListener('click', () => toggleModal(true));
    if (closeRegBtn) closeRegBtn.addEventListener('click', () => toggleModal(false));
    if (cancelRegBtn) cancelRegBtn.addEventListener('click', () => toggleModal(false));

    // Close on outside click
    window.addEventListener('click', (e) => {
        if (e.target === regModal) toggleModal(false);
    });

    if (regForm) {
        regForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-submit-reg');
            const spinner = btn.querySelector('.loader-spinner');
            const text = btn.querySelector('.btn-text');

            text.style.display = 'none';
            spinner.style.display = 'inline-block';
            btn.disabled = true;

            const payload = {
                name: document.getElementById('reg-name').value.trim(),
                description: document.getElementById('reg-desc').value.trim(),
                capabilities: document.getElementById('reg-caps').value.trim(),
                cost_per_request: 0.02,
                average_latency_ms: 1500,
                accuracy_score: 0.90,
                provider: 'huggingface',
                framework: 'custom',
                api_endpoint: 'https://router.huggingface.co/v1/chat/completions',
                model_id: document.getElementById('reg-model').value.trim(),
                is_active: true
            };

            try {
                const modal = document.getElementById('register-modal');
                const title = modal.querySelector('h2');
                const submitText = modal.querySelector('.btn-text');

                if (editAgentId) {
                    // PUT request
                    const res = await fetch(`/api/agents/${editAgentId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    if (!res.ok) {
                        const errData = await res.json();
                        throw new Error(errData.detail || errData.error || "Unknown server error");
                    }
                    showToast('Agent successfully updated!', 'success');
                } else {
                    // POST request
                    const res = await fetch('/api/agents/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    if (!res.ok) {
                        const errData = await res.json();
                        throw new Error(errData.detail || errData.error || "Unknown server error");
                    }
                    showToast('Agent successfully registered to the marketplace!', 'success');
                }

                regModal.classList.remove('active');
                document.getElementById('register-form').reset();
                editAgentId = null;
                title.textContent = "Register New Agent";
                submitText.textContent = "Register Agent";
                if (document.getElementById('view-registry').classList.contains('active-view')) {
                    loadAgents();
                }
            } catch (err) {
                showToast(err.message, 'error');
            } finally {
                text.style.display = 'inline-block';
                spinner.style.display = 'none';
                btn.disabled = false;
            }
        });
    }

    let editAgentId = null;

    // Nav Navigation
    const navButtons = {
        'nav-registry': 'view-registry',
        'nav-query': 'view-query',
        'nav-history': 'view-history'
    };

    for (const [btnId, viewId] of Object.entries(navButtons)) {
        document.getElementById(btnId).addEventListener('click', (e) => {
            // Remove active from all
            Object.keys(navButtons).forEach(id => document.getElementById(id).classList.remove('active'));
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));

            // Add active to clicked
            e.target.classList.add('active');
            document.getElementById(viewId).classList.add('active-view');

            // Load specific data
            if (viewId === 'view-registry') loadAgents();
            if (viewId === 'view-history') loadHistory();
        });
    }

    // Feedback Submission
    async function submitFeedback(isPositive) {
        const fbControls = document.getElementById('feedback-controls');
        if (!fbControls) return;
        const logId = fbControls.getAttribute('data-log-id');
        if (!logId) return;

        try {
            const btnUp = document.getElementById('btn-feedback-up');
            const btnDown = document.getElementById('btn-feedback-down');
            btnUp.disabled = true;
            btnDown.disabled = true;
            if (isPositive) btnDown.style.opacity = '0.3';
            else btnUp.style.opacity = '0.3';

            const res = await fetch(`/api/history/${logId}/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_positive: isPositive })
            });
            if (!res.ok) throw new Error('Failed to submit feedback');
            showToast('Feedback saved! Accuracy score updated dynamically.', 'success');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    const btnFbUp = document.getElementById('btn-feedback-up');
    const btnFbDown = document.getElementById('btn-feedback-down');
    if (btnFbUp) btnFbUp.addEventListener('click', () => submitFeedback(true));
    if (btnFbDown) btnFbDown.addEventListener('click', () => submitFeedback(false));

    // Query Submission
    document.getElementById('btn-submit').addEventListener('click', async () => {
        const query = document.getElementById('query-input').value.trim();
        if (!query) return showToast('Please enter a query.', 'error');

        // Read values from the routing sliders
        const cost = parseFloat(document.getElementById('pref-cost').value);
        const latency = parseFloat(document.getElementById('pref-latency').value);
        const accuracy = parseFloat(document.getElementById('pref-accuracy').value);

        const btn = document.getElementById('btn-submit');
        const spinner = btn.querySelector('.loader-spinner');
        const text = btn.querySelector('.btn-text');

        text.style.display = 'none';
        spinner.style.display = 'inline-block';
        btn.disabled = true;

        try {
            const res = await fetch('/api/query/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    pref_cost: cost,
                    pref_latency: latency,
                    pref_accuracy: accuracy
                })
            });

            if (!res.ok) {
                const text = await res.text();
                try {
                    const json = JSON.parse(text);
                    throw new Error(json.detail || json.error || text);
                } catch {
                    throw new Error(text);
                }
            }

            const data = await res.json();

            document.getElementById('response-container').style.display = 'block';
            document.getElementById('res-agent').textContent = data.selected_agent;
            document.getElementById('res-provider').textContent = data.selected_agent_provider || 'huggingface';
            document.getElementById('res-framework').textContent = data.selected_agent_framework || 'custom';
            document.getElementById('res-time').textContent = Math.round(data.execution_time_ms * 10) / 10;

            // Use Marked.js for rich formatting
            if (typeof marked !== 'undefined') {
                document.getElementById('res-content').innerHTML = marked.parse(data.response);
            } else {
                document.getElementById('res-content').textContent = data.response;
            }

            // Show feedback controls and store log_id
            const fbControls = document.getElementById('feedback-controls');
            if (fbControls && data.log_id) {
                fbControls.style.display = 'block';
                fbControls.setAttribute('data-log-id', data.log_id);
            } else if (fbControls) {
                fbControls.style.display = 'none';
            }

            // Reset feedback buttons
            ['btn-feedback-up', 'btn-feedback-down'].forEach(id => {
                const b = document.getElementById(id);
                if (b) { b.disabled = false; b.style.opacity = '1'; }
            });

            showToast('Query routed successfully!', 'success');
        } catch (err) {
            showToast('Error: ' + err.message, 'error');
        } finally {
            text.style.display = 'inline-block';
            spinner.style.display = 'none';
            btn.disabled = false;
        }
    });

    // Filter handling
    const btnFilter = document.getElementById('btn-apply-filters');
    if (btnFilter) {
        btnFilter.addEventListener('click', () => {
            const cap = document.getElementById('filter-capability').value.trim();
            loadAgents(cap);
        });
    }

    // Data Loaders
    async function loadAgents(capability = '') {
        const grid = document.getElementById('agents-grid');
        grid.innerHTML = Array(6).fill().map(() => `
            <div class="agent-card glass-panel" style="pointer-events: none;">
                <div class="skeleton skeleton-title"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text short"></div>
                <div style="margin-top:2rem">
                    <div class="skeleton skeleton-text"></div>
                    <div class="skeleton skeleton-text"></div>
                </div>
            </div>
        `).join('');

        try {
            const url = capability ? `/api/agents/?capability=${encodeURIComponent(capability)}` : '/api/agents/';
            const res = await fetch(url);
            const agents = await res.json();

            if (agents.length === 0) {
                grid.innerHTML = '<div class="empty-state">No agents registered. Please run the seed script.</div>';
                return;
            }

            grid.innerHTML = agents.map(a => `
                <div class="agent-card glass-panel" style="position: relative;">
                    <button class="edit-agent-btn" data-id="${a.id}" title="Edit Agent" style="position: absolute; top: 10px; right: 40px; background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 1.2rem; transition: color 0.2s;">✏️</button>
                    <button class="delete-agent-btn" data-id="${a.id}" title="Delete Agent">&times;</button>
                    <div class="card-header">
                        <h3>${a.name}</h3>
                        <span class="status-dot ${a.is_active ? 'active' : ''}"></span>
                    </div>
                    <p class="desc">${a.description}</p>
                    ${a.model_id ? `<p class="meta-line"><dfn>Model:</dfn> ${a.model_id}</p>` : ''}
                    <div class="capabilities">
                        ${a.capabilities.split(',').map(c => `<span class="tag">${c.trim()}</span>`).join('')}
                    </div>
                </div>
            `).join('');

            // Populate the Optional Force Agent dropdown
            const select = document.getElementById('force-agent-select');
            if (select) {
                select.innerHTML = '<option value="">-- Let the Smart Router Decide --</option>' + agents.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
            }

            // Bind Agent Edit buttons
            document.querySelectorAll('.edit-agent-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const id = parseInt(btn.dataset.id);
                    const agent = agents.find(a => a.id === id);
                    if (agent) {
                        editAgentId = id;
                        document.getElementById('reg-name').value = agent.name;
                        document.getElementById('reg-desc').value = agent.description;
                        document.getElementById('reg-caps').value = agent.capabilities;
                        document.getElementById('reg-model').value = agent.model_id || '';

                        const modal = document.getElementById('register-modal');
                        modal.querySelector('h2').textContent = "Edit Agent";
                        modal.querySelector('.btn-text').textContent = "Save Changes";
                        modal.classList.add('active');
                        modal.style.display = ''; // Clear any inline styles just in case
                    }
                });
            });

            // Bind Agent Delete buttons
            document.querySelectorAll('.delete-agent-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    if (!confirm("Are you sure you want to delete this agent?")) return;
                    if (!confirm("This action cannot be undone. Are you absolutely sure?")) return;
                    const id = e.target.getAttribute('data-id');
                    try {
                        const res = await fetch(`/api/agents/${id}`, { method: 'DELETE' });
                        if (!res.ok) throw new Error('Failed to delete agent');
                        showToast('Agent deleted successfully', 'success');
                        loadAgents();
                    } catch (err) {
                        showToast(err.message, 'error');
                    }
                });
            });

        } catch (err) {
            grid.innerHTML = `<div class="error">Failed to load agents: ${err.message}</div>`;
        }
    }

    async function loadHistory() {
        const tbody = document.getElementById('history-body');
        tbody.innerHTML = Array(5).fill().map(() => `
            <tr><td colspan="4"><div class="skeleton skeleton-row"></div></td></tr>
        `).join('');

        const deleteBtn = document.getElementById('btn-delete-history');
        const selectAllCb = document.getElementById('cb-select-all');
        if (selectAllCb) selectAllCb.checked = false;
        if (deleteBtn) deleteBtn.style.display = 'none';

        try {
            const res = await fetch('/api/history/');
            const logs = await res.json();

            if (logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center">No history yet.</td></tr>';
                return;
            }

            tbody.innerHTML = logs.map(l => {
                return `
                <tr>
                    <td><input type="checkbox" class="cb-history-item" value="${l.id}"></td>
                    <td><div class="truncate-history" title="${l.user_query}">${l.user_query}</div></td>
                    <td><strong>${l.selected_agent_name}</strong></td>
                    <td>${Math.round(l.execution_time_ms)}ms</td>
                </tr>
            `}).join('');

            // Bind history checkboxes
            const itemCbs = document.querySelectorAll('.cb-history-item');

            function updateDeleteButtonVisibility() {
                const anyChecked = Array.from(itemCbs).some(cb => cb.checked);
                if (deleteBtn) deleteBtn.style.display = anyChecked ? 'inline-block' : 'none';
            }

            itemCbs.forEach(cb => {
                cb.addEventListener('change', () => {
                    updateDeleteButtonVisibility();
                    if (selectAllCb) {
                        selectAllCb.checked = Array.from(itemCbs).every(c => c.checked);
                    }
                });
            });

            if (selectAllCb) {
                // Remove existing listener to avoid duplicates if re-rendering
                const newSelectAll = selectAllCb.cloneNode(true);
                selectAllCb.parentNode.replaceChild(newSelectAll, selectAllCb);

                newSelectAll.addEventListener('change', (e) => {
                    const isChecked = e.target.checked;
                    document.querySelectorAll('.cb-history-item').forEach(cb => {
                        cb.checked = isChecked;
                    });
                    const dBtn = document.getElementById('btn-delete-history');
                    if (dBtn) dBtn.style.display = isChecked && itemCbs.length > 0 ? 'inline-block' : 'none';
                });
            }

            // Bind Bulk Delete Button (only once)
            if (deleteBtn && !deleteBtn.hasAttribute('data-bound')) {
                deleteBtn.setAttribute('data-bound', 'true');
                deleteBtn.addEventListener('click', async () => {
                    const checkedIds = Array.from(document.querySelectorAll('.cb-history-item:checked')).map(cb => parseInt(cb.value));
                    if (checkedIds.length === 0) return;

                    if (!confirm(`Are you sure you want to delete ${checkedIds.length} history records?`)) return;

                    try {
                        const res = await fetch('/api/history/bulk', {
                            method: 'DELETE',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ ids: checkedIds })
                        });
                        if (!res.ok) throw new Error('Bulk delete failed');
                        showToast(`Successfully deleted ${checkedIds.length} records`, 'success');
                        loadHistory();
                    } catch (err) {
                        showToast(err.message, 'error');
                    }
                });
            }

            // Render Chart
            if (typeof Chart !== 'undefined') {
                const ctx = document.getElementById('historyChart').getContext('2d');
                const chartData = [...logs].reverse().slice(-20); // Show last 20 queries chronologically

                if (historyChartInstance) {
                    historyChartInstance.destroy();
                }

                historyChartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: chartData.map((_, i) => `#${i + 1}`),
                        datasets: [{
                            label: 'Execution Time (ms)',
                            data: chartData.map(l => Math.round(l.execution_time_ms)),
                            borderColor: '#58a6ff',
                            backgroundColor: 'rgba(88, 166, 255, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#a371f7'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
            }

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center error">Failed to load history: ${err.message}</td></tr>`;
        }
    }

    // Initial load
    loadAgents();
});
