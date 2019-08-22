#!/usr/bin/env python

from flask import Blueprint, jsonify

healthecheck_bp = Blueprint('healthcheck', __name__)


@healthecheck_bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({"pong": True})


if __name__ == '__main__':
    pass
