const API_BASE = '/api/wiki';

// --- NOVO: Bloco de Proteção da Página ---
// Esta é a primeira coisa que o script faz quando a página carrega.
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('access_token');

    // Se não há token E não estamos na página de login, redireciona para o login.
    // Isto impede que alguém aceda ao chat diretamente pelo URL.
    if (!token && window.location.pathname.indexOf('login.html') === -1) {
        window.location.href = '/login.html';
        return; // Pára a execução do resto do script
    }

    // Se o token existe, podemos continuar e verificar o status da base de conhecimento.
    // Removemos a verificação do window.onload antigo para a colocar aqui.
    checkStatus();
});


// --- NOVO: Função Centralizada para Pedidos Autenticados ---
async function fetchAuthenticated(url, options = {}) {
    const token = localStorage.getItem('access_token');

    // Prepara os cabeçalhos (headers)
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers, // Permite passar outros headers se necessário
    };

    // Se o token existir, adiciona-o ao cabeçalho de Autorização
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
        ...options,
        headers: headers,
    });

    // Se a resposta for 401 (Não Autorizado), o token pode ter expirado.
    // Limpamos o token e redirecionamos para o login.
    if (response.status === 401) {
        localStorage.removeItem('access_token');
        window.location.href = '/login.html';
        // Lança um erro para parar a execução da função que chamou
        throw new Error('Sessão expirada. Por favor, faça login novamente.');
    }

    return response;
}


// --- Funções da Aplicação (Agora usam a nova função segura) ---

async function extractWiki() {
    // Nota: O URL da Wiki e as credenciais de extração agora estão no backend,
    // o que é mais seguro. O frontend só precisa de enviar o pedido.
    const statusDiv = document.getElementById('extractStatus');
    showStatus(statusDiv, 'Extraindo conteúdo da Wiki... Isso pode levar alguns minutos.', 'info');
    
    try {
        // Usa a nova função de fetch autenticado
        const response = await fetchAuthenticated(`${API_BASE}/extract`, {
            method: 'POST',
            // O corpo do pedido agora só precisa da URL, que o backend irá usar.
            // As credenciais para a wiki são lidas pelo backend a partir do .env
            body: JSON.stringify({ wiki_url: 'http://10.1.1.127/' })
        });

        const data = await response.json();

        if (response.ok) {
            showStatus(statusDiv, 
                `✅ Sucesso! Processados ${data.documents_processed} documentos e ${data.total_chunks_created} chunks de texto.`, 
                'success'
            );
            checkStatus();
        } else {
            showStatus(statusDiv, `❌ Erro: ${data.message || data.error || 'Erro desconhecido'}`, 'error');
        }
    } catch (error) {
        showStatus(statusDiv, `❌ Erro: ${error.message}`, 'error');
    }
}

async function checkStatus() {
    const statusDiv = document.getElementById('statusInfo');
    
    try {
        // Usa a nova função de fetch autenticado
        const response = await fetchAuthenticated(`${API_BASE}/status`);
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
        statusDiv.innerHTML = `<p>❌ Erro: ${error.message}</p>`;
    }
}

async function askQuestion() {
    const question = document.getElementById('questionInput').value;
    const loading = document.getElementById('loading');
    
    if (!question.trim()) { return; }

    addMessage('user', 'Você', question);
    document.getElementById('questionInput').value = '';
    loading.style.display = 'block';
    
    try {
        // Usa a nova função de fetch autenticado
        const response = await fetchAuthenticated(`${API_BASE}/ask`, {
            method: 'POST',
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
        addMessage('assistant', 'Assistente IA', `❌ Erro: ${error.message}`);
    }
}

// As funções addMessage, addAssistantMessage, etc., continuam iguais ao que já tínhamos.
// ... (copia e cola o resto das tuas funções auxiliares aqui, sem alterações) ...

function addMessage(type, sender, content) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    messageDiv.innerHTML = `
        <div class="message-header">${sender}</div>
        <div></div> 
    `;
    messageDiv.querySelector('div:last-child').innerText = content;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addAssistantMessage(data) {
    // Esta função deve ser a tua versão final que já renderiza Markdown e imagens
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    let htmlResposta = marked.parse(data.answer);
    
    const wikiBaseUrl = "http://10.1.1.123"; // O URL da tua wiki
    const regex = /<WIKI_IMAGE>(.*?)<\/WIKI_IMAGE>/g;

    htmlResposta = htmlResposta.replace(regex, (match, imageName) => {
        const imageUrl = `${wikiBaseUrl}/index.php?title=Special:Filepath/${imageName.trim()}`;
        return `<a href="${imageUrl}" target="_blank" rel="noopener noreferrer"><img src="${imageUrl}" alt="${imageName.trim()}" style="max-width: 100%; height: auto; border-radius: 8px;"></a>`;
    });

    let sourcesHtml = '';
    if (data.sources && data.sources.length > 0) {
        sourcesHtml = `<div class="sources"><h4>📚 Fontes consultadas:</h4>${data.sources.map(source => `<div class="source-item">📄 <a href="${source.url}" target="_blank">${source.title}</a></div>`).join('')}</div>`;
    }

    messageDiv.innerHTML = `
        <div class="message-header">Assistente IA</div>
        <div class="message-content">${htmlResposta}</div> 
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