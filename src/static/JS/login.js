// src/static/js/login.js

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const statusDiv = document.getElementById('login-status');

    loginForm.addEventListener('submit', async (event) => {
        // Impede o recarregamento da página
        event.preventDefault();

        // Limpa mensagens de status anteriores
        statusDiv.textContent = '';
        statusDiv.className = 'status';

        // Pega os valores do formulário
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        try {
            // Mostra uma mensagem de carregamento
            statusDiv.textContent = 'A autenticar...';
            statusDiv.classList.add('info');

            // Faz a chamada à nossa API de login
            const response = await fetch('/api/user/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            const data = await response.json();

            if (response.ok) {
                // SUCESSO!
                // Guarda o token de acesso no armazenamento local do navegador
                localStorage.setItem('access_token', data.access_token);
                
                // Redireciona para a página principal do chat
                window.location.href = '/'; // Redireciona para a raiz (que serve o index.html)
            } else {
                // ERRO!
                statusDiv.textContent = data.message || 'Ocorreu um erro.';
                statusDiv.classList.add('error');
            }
        } catch (error) {
            console.error('Erro de conexão:', error);
            statusDiv.textContent = 'Erro de conexão com o servidor. Tente novamente.';
            statusDiv.classList.add('error');
        }
    });
});