"""
------------------------------------------------------------------------
File : app.py
Description: Main project
Date creation: 20-02-2024
Project : soup-server
Author: Alessio Giacché
Copyright: Copyright (c) 2024 Alessio Giacché <ale.giacc.dev@gmail.com>
License : MIT
------------------------------------------------------------------------
"""

# Import
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from Controllers.AggregateGraph.aggregate_graph_controller import aggregate_graph_controller_bp
from Controllers.generic_graph_controller import generic_graph_controller_bp
from Controllers.Graph.graph_op_controller import graph_op_controller_bp
from Controllers.AggregateGraph.aggregate_graph_op_controller import aggregate_graph_op_controller_bp
from Controllers.graph_json_controller import graph_json_controller_bp
from Controllers.dataset_controller import dataset_controller_bp
from Controllers.filters_controller import filters_controller_bp
from Controllers.onboarding_controller import onboarding_controller_bp
from Shared.support_config import get_db_connector
from Models.api_response_model import ApiResponse
from Models.logger_model import Logger

# App
app = Flask(__name__)

# Register the App Blueprint
app.register_blueprint(graph_op_controller_bp)
app.register_blueprint(aggregate_graph_controller_bp)
app.register_blueprint(aggregate_graph_op_controller_bp)
app.register_blueprint(generic_graph_controller_bp)
app.register_blueprint(graph_json_controller_bp)
app.register_blueprint(dataset_controller_bp)
app.register_blueprint(filters_controller_bp)
app.register_blueprint(onboarding_controller_bp)

# Init the Socket
socketio = SocketIO(app, cors_allowed_origins="*")

# Store the Socket in the app configuration
app.config['socketio'] = socketio

# Add application CORS
CORS(app)

# Configure SOUP Docker folder and volume
docker_soup_path = '/soup'

# View only default error log
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Engine custom logger setup
logger = Logger()


# Welcome, API
@app.route('/api/v2/welcome', methods=['GET'])
def welcome_api():
    """
    Test the connection with the Engine
    :return: ApiResponse model
    """

    response = ApiResponse()
    response.http_status_code = 200
    response.message = "Hello user, the Engine work :)"
    response.response_data = None
    return jsonify(response.to_dict()), 200


@app.route('/api/v2/memgraph-connect', methods=['GET'])
def connect_database():
    """
    Test the connection with Memgraph
    :return: ApiResponse model
    """

    response = ApiResponse()

    try:
        # Engine database setup
        database_connector = get_db_connector()
        database_connector.connect()

        # Execute query test
        query = "RETURN 1"
        result = database_connector.run_query_memgraph(query)

        # Check the result and response
        if not result:
            response.http_status_code = 500
            response.message = "Error while connecting to Memgraph"
            response.response_data = None

            logger.error('Error while connecting to Memgraph')
            return jsonify(response.to_dict()), 500

        response.http_status_code = 200
        response.message = "Success connect with Memgraph"
        response.response_data = result
        return jsonify(response.to_dict()), 200
    except Exception as e:
        response.http_status_code = 500
        response.message = f"Internal Server Error: {e}"
        response.response_data = None

        logger.error(f'Internal Server Error: {e}')
        return jsonify(response.to_dict()), 500


# Main (run the Server on 8080)
#
# NOTE (Pilastro 1 - Import refactor): the server no longer runs the
# `app` Flask instance built above - it is left in place, unmodified,
# because this module's old routes/blueprint-registrations are not
# deleted (only the import route they used to serve, POST /api/v2/graph,
# is no longer active here: soup/api/core_routes.py now serves it,
# backed by the new plugin-based import pipeline). The process instead
# builds and runs soup.api.flask_app's app, which registers every other
# legacy blueprint unmodified alongside the new import/welcome/
# memgraph-connect routes. See soup/core/engine.py (build_engine) and
# soup/api/flask_app.py (build_flask_app).
if __name__ == '__main__':
    from soup.core.engine import build_engine
    from soup.core.settings import Settings
    from soup.api.flask_app import build_flask_app

    engine = build_engine(Settings.from_env())
    new_app = build_flask_app(engine)
    new_app.run(host='0.0.0.0', port=8080, debug=True)
