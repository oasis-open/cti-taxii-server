from flask import Blueprint, abort, current_app, jsonify, request
from werkzeug.security import check_password_hash

from ... import auth, jwt_encode

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    auth_info = request.json
    if not auth_info:
        abort(400)
    username, password = auth_info['username'], auth_info['password']
    password_hash = current_app.auth_backend.get_password_hash(username)

    if not password_hash or not check_password_hash(password_hash, password):
        abort(401)

    return jsonify({'access_token': jwt_encode(username).decode('utf-8')})


@auth_bp.route('/routes', methods=['GET'])
@auth.login_required
def routes():
    return jsonify([
        {
            'path': str(rule.rule),
            'arguments': list(rule.arguments),
            'defaults': rule.defaults,
            'methods': list(rule.methods)
        }
        for rule in current_app.url_map.iter_rules()
    ])
