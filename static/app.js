document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');
    const quickBtns = document.querySelectorAll('.quick-btn');
    const toggleBtns = document.querySelectorAll('.toggle-btn');
    const chatContainer = document.getElementById('chat-container');
    const graphContainer = document.getElementById('graph-container');
    const resetZoomBtn = document.getElementById('reset-zoom');
    const tooltip = document.getElementById('node-tooltip');

    let graphData = null;
    let simulation = null;
    let svg = null;
    let zoom = null;

    loadStats();

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            if (view === 'chat') {
                chatContainer.style.display = 'flex';
                graphContainer.style.display = 'none';
            } else {
                chatContainer.style.display = 'none';
                graphContainer.style.display = 'block';
                loadGraph();
            }
        });
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;
        await sendMessage(message);
    });

    quickBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const query = btn.dataset.query;
            toggleBtns.forEach(b => b.classList.remove('active'));
            document.querySelector('[data-view="chat"]').classList.add('active');
            chatContainer.style.display = 'flex';
            graphContainer.style.display = 'none';
            await sendMessage(query);
        });
    });

    if (resetZoomBtn) {
        resetZoomBtn.addEventListener('click', () => {
            if (svg && zoom) {
                svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
            }
        });
    }

    async function sendMessage(message) {
        chatInput.value = '';
        sendBtn.disabled = true;
        addMessage(message, 'user');
        const loadingId = addLoadingMessage();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });

            removeLoadingMessage(loadingId);

            if (!response.ok) {
                const error = await response.json();
                addMessage(`Error: ${error.detail || 'Something went wrong'}`, 'assistant');
                return;
            }

            const data = await response.json();
            addMessage(data.response, 'assistant');
        } catch (error) {
            removeLoadingMessage(loadingId);
            addMessage(`Error: ${error.message}`, 'assistant');
        } finally {
            sendBtn.disabled = false;
            chatInput.focus();
        }
    }

    function addMessage(content, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = role === 'user' 
            ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
               </svg>`
            : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 2v4m0 12v4M2 12h4m12 0h4"/>
               </svg>`;

        const formattedContent = formatMarkdown(content);

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">${formattedContent}</div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function addLoadingMessage() {
        const id = 'loading-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.id = id;
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="3"/>
                    <path d="M12 2v4m0 12v4M2 12h4m12 0h4"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return id;
    }

    function removeLoadingMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function formatMarkdown(text) {
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        const lines = text.split('\n');
        let html = '';
        let inList = false;
        let listItems = [];

        lines.forEach(line => {
            const trimmed = line.trim();
            
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                if (!inList) {
                    inList = true;
                    listItems = [];
                }
                listItems.push(trimmed.substring(2));
            } else {
                if (inList) {
                    html += '<ul>' + listItems.map(item => `<li>${item}</li>`).join('') + '</ul>';
                    inList = false;
                    listItems = [];
                }
                if (trimmed) {
                    html += `<p>${trimmed}</p>`;
                }
            }
        });

        if (inList) {
            html += '<ul>' + listItems.map(item => `<li>${item}</li>`).join('') + '</ul>';
        }

        return html || `<p>${text}</p>`;
    }

    async function loadStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) return;
            
            const stats = await response.json();
            
            document.getElementById('stat-nodes').textContent = stats.total_nodes;
            document.getElementById('stat-edges').textContent = stats.total_edges;
            
            const nodeTypesEl = document.getElementById('node-types');
            nodeTypesEl.innerHTML = '';
            
            if (stats.nodes_by_type) {
                Object.entries(stats.nodes_by_type).forEach(([type, count]) => {
                    const badge = document.createElement('span');
                    badge.className = 'node-type-badge';
                    badge.textContent = `${type}: ${count}`;
                    nodeTypesEl.appendChild(badge);
                });
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    async function loadGraph() {
        if (graphData) {
            renderGraph(graphData);
            return;
        }

        try {
            const response = await fetch('/api/graph');
            if (!response.ok) return;
            
            graphData = await response.json();
            renderGraph(graphData);
        } catch (error) {
            console.error('Failed to load graph:', error);
        }
    }

    function renderGraph(data) {
        const svgEl = document.getElementById('graph-svg');
        svgEl.innerHTML = '';

        const width = svgEl.clientWidth;
        const height = svgEl.clientHeight;

        svg = d3.select(svgEl);

        const nodeColorMap = {
            'service': '#6366f1',
            'database': '#22c55e',
            'cache': '#f59e0b',
            'team': '#ec4899',
        };

        const nodes = data.nodes.map(n => ({
            ...n,
            id: n.id,
            label: n.name || n.id.split(':')[1],
            color: nodeColorMap[n.type] || '#64748b',
        }));

        const nodeIds = new Set(nodes.map(n => n.id));
        const links = data.edges
            .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
            .map(e => ({
                source: e.source,
                target: e.target,
                type: e.type,
            }));

        zoom = d3.zoom()
            .scaleExtent([0.2, 4])
            .on('zoom', (event) => {
                container.attr('transform', event.transform);
            });

        svg.call(zoom);

        const container = svg.append('g');

        svg.append('defs').append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '-0 -5 10 10')
            .attr('refX', 25)
            .attr('refY', 0)
            .attr('orient', 'auto')
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .append('path')
            .attr('d', 'M 0,-5 L 10,0 L 0,5')
            .attr('fill', '#64748b');

        simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id).distance(120))
            .force('charge', d3.forceManyBody().strength(-400))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(40));

        const link = container.append('g')
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('stroke', '#64748b')
            .attr('stroke-opacity', 0.5)
            .attr('stroke-width', 1.5)
            .attr('marker-end', 'url(#arrowhead)');

        const node = container.append('g')
            .selectAll('g')
            .data(nodes)
            .join('g')
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended));

        node.append('circle')
            .attr('r', d => d.type === 'team' ? 18 : 14)
            .attr('fill', d => d.color)
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .style('cursor', 'pointer')
            .style('filter', 'drop-shadow(0 0 8px rgba(99, 102, 241, 0.4))');

        node.append('text')
            .text(d => d.label)
            .attr('x', 0)
            .attr('y', 30)
            .attr('text-anchor', 'middle')
            .attr('fill', '#f8fafc')
            .attr('font-size', '11px')
            .attr('font-weight', '500')
            .style('pointer-events', 'none');

        node.on('mouseover', (event, d) => {
            showTooltip(event, d);
        }).on('mouseout', () => {
            hideTooltip();
        });

        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
    }

    function showTooltip(event, d) {
        let propsHtml = '';
        if (d.team) propsHtml += `<div><strong>Team:</strong> ${d.team}</div>`;
        if (d.oncall) propsHtml += `<div><strong>Oncall:</strong> ${d.oncall}</div>`;
        if (d.port) propsHtml += `<div><strong>Port:</strong> ${d.port}</div>`;
        if (d.lead) propsHtml += `<div><strong>Lead:</strong> ${d.lead}</div>`;
        if (d.slack_channel) propsHtml += `<div><strong>Slack:</strong> ${d.slack_channel}</div>`;

        tooltip.innerHTML = `
            <div class="tooltip-type">${d.type}</div>
            <div class="tooltip-title">${d.name || d.id}</div>
            ${propsHtml ? `<div class="tooltip-props">${propsHtml}</div>` : ''}
        `;
        
        tooltip.style.left = (event.pageX + 15) + 'px';
        tooltip.style.top = (event.pageY - 10) + 'px';
        tooltip.classList.add('visible');
    }

    function hideTooltip() {
        tooltip.classList.remove('visible');
    }
});
