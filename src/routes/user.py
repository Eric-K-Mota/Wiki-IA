import os
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from src.services.wiki_extractor import MediaWikiExtractor

user_bp = Blueprint('user', __name__)

@user_bp.route('/login', methods=['POST'])
def login():
    """
    Autentica um utilizador usando as credenciais do MediaWiki.
    """
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # NOVO: Pega o URL da Wiki a partir das variáveis de ambiente
    wiki_url = os.getenv("MEDIAWIKI_URL")

    if not all([username, password, wiki_url]):
        return jsonify({"status": "error", "message": "Faltam dados (usuário, senha ou URL da Wiki não configurado no backend)"}), 400

    # NOVO: Usa o nosso MediaWikiExtractor para tentar fazer o login
    try:
        extractor = MediaWikiExtractor(wiki_url)
        login_successful = extractor.login(username, password)
    except Exception as e:
        # Captura erros de conexão com a Wiki, por exemplo
        print(f"Erro ao tentar conectar com a MediaWiki: {e}")
        return jsonify({"status": "error", "message": "Não foi possível conectar ao serviço de autenticação."}), 500

    # Substituímos a verificação de senha fixa por esta chamada
    if login_successful:
        # Se o login na Wiki foi bem-sucedido, cria o nosso token de acesso (crachá digital)
        access_token = create_access_token(identity=username)
        return jsonify({
            "status": "success",
            "message": "Login realizado com sucesso.",
            "access_token": access_token
        }), 200
    else:
        # Se o login na Wiki falhou, as credenciais são inválidas
        return jsonify({
            "status": "error",
            "message": "Usuário ou senha inválidos."
        }), 401
