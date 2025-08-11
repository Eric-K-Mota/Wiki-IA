# src/routes/user.py

from flask import Blueprint, jsonify, request

# Criação do blueprint para rotas de usuário
user_bp = Blueprint('user', __name__)

# Rota de teste para simular login de usuário
@user_bp.route('/login', methods=['POST'])
def login():
    """
    Simula um login com dados enviados via POST.
    """
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # Simulação de autenticação (substituir por lógica real depois)
    if username == "Eric" and password == "Erickaw3-":
        return jsonify({
            "status": "success",
            "message": "Login realizado com sucesso.",
            "user": {
                "id": 1,
                "username": "admin",
                "role": "admin"
            }
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Usuário ou senha inválidos."
        }), 401

# Rota para obter informações básicas do usuário logado
@user_bp.route('/me', methods=['GET'])
def get_user_info():
    """
    Retorna dados simulados do usuário logado.
    """
    return jsonify({
        "id": 1,
        "username": "admin",
        "role": "admin"
    })
