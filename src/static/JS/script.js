const API_BASE = '/api/wiki';

// Verificar status ao carregar a página
window.onload = function() {
    checkStatus();
};

async function extractWiki() {
    const wikiUrl = document.getElementById('wikiUrl').value;
    const statusDiv = document.getElementById('extractStatus');
    
    if (!wikiUrl) {
        showStatus(statusDiv, 'Por favor, insira a URL da Wiki.', 'error');
        return;
    }

    showStatus(statusDiv, 'Extraindo conteúdo da Wiki... Isso pode levar alguns minutos.', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/extract`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ wiki_url: wikiUrl })
        });

        const data = await response.json();

        if (response.ok) {
            showStatus(statusDiv, 
                `✅ Sucesso! Processados ${data.documents_processed} documentos e ${data.total_chunks} chunks de texto.`, 
                'success'
            );
            checkStatus(); // Atualizar status
        } else {
            showStatus(statusDiv, `❌ Erro: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(statusDiv, `❌ Erro de conexão: ${error.message}`, 'error');
    }
}

async function checkStatus() {
    const statusDiv = document.getElementById('statusInfo');
    
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        if (response.ok) {
            const statusText = data.status === 'ready' 
                ? `✅ Base de conhecimento ativa`
                : `⚠️ Base de conhecimento vazia`;
            
            statusDiv.innerHTML = `
                <p><strong>${statusText}</strong></p>
                <p>📄 Documentos: ${data.documents}</p>
                <p>🧩 Chunks de texto: ${data.chunks}</p>
            `;
        } else {
            statusDiv.innerHTML = `<p>❌ Erro ao verificar status: ${data.error}</p>`;
        }
    } catch (error) {
        statusDiv.innerHTML = `<p>❌ Erro de conexão: ${error.message}</p>`;
    }
}

async function askQuestion() {
    const question = document.getElementById('questionInput').value;
    const chatMessages = document.getElementById('chatMessages');
    const loading = document.getElementById('loading');
    
    if (!question.trim()) {
        alert('Por favor, digite uma pergunta.');
        return;
    }

    // Adicionar pergunta do usuário ao chat
    addMessage('user', 'Você', question);
    
    // Limpar input
    document.getElementById('questionInput').value = '';
    
    // Mostrar loading
    loading.style.display = 'block';
    
    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question: question })
        });

        const data = await response.json();
        loading.style.display = 'none';

        if (response.ok) {
            addAssistantMessage(data);
        } else {
            addMessage('assistant', 'Assistente IA', `❌ Erro: ${data.error}`);
        }
    } catch (error) {
        loading.style.display = 'none';
        addMessage('assistant', 'Assistente IA', `❌ Erro de conexão: ${error.message}`);
    }
}

function addMessage(type, sender, content) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    messageDiv.innerHTML = `
        <div class="message-header">${sender}</div>
        <div>${content}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addAssistantMessage(data) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    
    let sourcesHtml = '';
    if (data.sources && data.sources.length > 0) {
        sourcesHtml = `
            <div class="sources">
                <h4>📚 Fontes consultadas:</h4>
                ${data.sources.map(source => 
                    `<div class="source-item">📄 <a href="${source.url}" target="_blank" rel="noopener noreferrer">${source.title}</a></div>`
                ).join('')}
            </div>
        `;
    }
    
    messageDiv.innerHTML = `
        <div class="message-header">Assistente IA</div>
        <div>${data.answer}</div>
        <div class="confidence">
            🎯 Confiança: ${Math.round(data.confidence * 100)}% | 
            📊 Chunks consultados: ${data.context_chunks_used}
        </div>
        ${sourcesHtml}
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showStatus(element, message, type) {
    element.innerHTML = `<div class="status ${type}">${message}</div>`;
}


document.getElementById('questionInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        askQuestion();
    }
});