"""
AgenikPredict Backend - Flask Application Factory
"""

import os
import warnings

# Suppress multiprocessing resource_tracker warnings (from third-party libs like transformers)
# Must be set before all other imports
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask application factory function"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Set JSON encoding: ensure Unicode displays directly (instead of \uXXXX format)
    # Flask >= 2.3 uses app.json.ensure_ascii, older versions use JSON_AS_ASCII config
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Set up logging
    logger = setup_logger('agenikpredict')
    
    # Only print startup info in reloader subprocess (avoid printing twice in debug mode)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("AgenikPredict Backend starting...")
        logger.info("=" * 50)
    
    # Enable CORS with restricted origins
    allowed_origins = [
        os.environ.get('APP_URL', 'http://localhost:3000'),
        'https://agenikpredict.com',
        'https://www.agenikpredict.com',
        'https://app.agenikpredict.com',
        'https://agenikpredict-landing.vercel.app',
        'http://localhost:3000',
        'http://localhost:5173',
    ]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})
    
    # Register simulation process cleanup function (ensure all simulation processes terminate on server shutdown)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Simulation process cleanup function registered")
    
    # Request logging middleware
    @app.before_request
    def log_request():
        logger = get_logger('agenikpredict.request')
        logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Request body: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('agenikpredict.request')
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Initialize user database and seed accounts
    from .models.user import init_db, seed_admin, seed_demo
    init_db()
    seed_admin()
    seed_demo()
    if should_log_startup:
        logger.info("User database initialized, admin and demo accounts seeded")

    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp, auth_bp, market_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(market_bp, url_prefix='/api/market')
    
    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'AgenikPredict Backend'}
    
    if should_log_startup:
        logger.info("AgenikPredict Backend startup complete")

    # ------------------------------------------------------------------
    # Serve Vue frontend static files in production
    # In dev the Vite dev-server handles this; in production the built
    # assets live at <project>/frontend/dist and Flask serves them via
    # this catch-all.  It is registered AFTER all /api/* blueprints and
    # /health so those routes take priority.
    # ------------------------------------------------------------------
    from flask import send_from_directory

    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'dist')
    )

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # Never intercept API or health routes
        if path.startswith('api/') or path == 'health':
            from flask import abort
            abort(404)
        if path and os.path.exists(os.path.join(frontend_dist, path)):
            return send_from_directory(frontend_dist, path)
        index = os.path.join(frontend_dist, 'index.html')
        if os.path.exists(index):
            return send_from_directory(frontend_dist, 'index.html')
        return {'error': 'Frontend not built. Run npm run build in frontend/'}, 404

    return app

