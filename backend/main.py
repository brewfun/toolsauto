#!/usr/bin/env python3
"""
Main Flask application for K8s Auto Installer
Entry point for the web API server
"""

import os
import sys
import logging
from pathlib import Path
from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS

from backend.config.settings import settings
from backend.api.routes.installation import installation_bp
from backend.utils.logger import log_manager, get_logger
from backend.utils.helpers import ensure_directory

logger = get_logger(__name__)

def create_app(config_name: str = None) -> Flask:
    """Create and configure Flask application"""
    
    # Create Flask app
    app = Flask(
        __name__,
        template_folder='../frontend/templates',
        static_folder='../frontend/public'
    )
    
    # Configuration
    app.config['SECRET_KEY'] = settings.flask.secret_key
    app.config['DEBUG'] = settings.flask.debug
    app.config['TESTING'] = settings.flask.testing
    app.config['MAX_CONTENT_LENGTH'] = settings.flask.max_content_length
    
    # Additional Flask config
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # Enable CORS for API endpoints
    CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Setup logging
    setup_logging(app)
    
    # Initialize extensions
    initialize_extensions(app)
    
    logger.info(f"Flask app created in {settings.environment.value} mode")
    return app

def register_blueprints(app: Flask):
    """Register Flask blueprints"""
    
    # API blueprints
    app.register_blueprint(installation_bp)
    
    # Add health check blueprint
    from flask import Blueprint
    health_bp = Blueprint('health', __name__, url_prefix='/api')
    
    @health_bp.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': '1.0.0',
            'environment': settings.environment.value,
            'timestamp': log_manager.installation_loggers  # Just to test log_manager is working
        })
    
    app.register_blueprint(health_bp)

def register_error_handlers(app: Flask):
    """Register error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': 'The request was invalid or cannot be served',
            'status_code': 400
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication is required',
            'status_code': 401
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource',
            'status_code': 403
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status_code': 404
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'error': 'Method Not Allowed',
            'message': 'The method is not allowed for this endpoint',
            'status_code': 405
        }), 405
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            'error': 'Rate Limit Exceeded',
            'message': 'Too many requests, please try again later',
            'status_code': 429
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.error(f"Unhandled exception: {error}")
        
        if settings.flask.debug:
            # In debug mode, return the actual error
            return jsonify({
                'error': 'Internal Server Error',
                'message': str(error),
                'type': type(error).__name__,
                'status_code': 500
            }), 500
        else:
            # In production, return generic error
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }), 500

def register_cli_commands(app: Flask):
    """Register CLI commands"""
    
    @app.cli.command()
    def init_db():
        """Initialize database"""
        print("Database initialization not implemented yet")
    
    @app.cli.command()
    def create_user():
        """Create admin user"""
        print("User creation not implemented yet")
    
    @app.cli.command()
    def cleanup_logs():
        """Cleanup old log files"""
        try:
            logs_dir = Path(settings.storage.logs_directory)
            if not logs_dir.exists():
                print("Logs directory does not exist")
                return
            
            # Find old log files (older than retention period)
            import time
            cutoff_time = time.time() - (settings.monitoring.log_retention_days * 24 * 3600)
            
            cleaned_count = 0
            for log_file in logs_dir.glob('*.log*'):
                if log_file.stat().st_mtime < cutoff_time:
                    try:
                        log_file.unlink()
                        cleaned_count += 1
                        print(f"Removed old log file: {log_file.name}")
                    except Exception as e:
                        print(f"Failed to remove {log_file.name}: {e}")
            
            print(f"Cleanup completed. Removed {cleaned_count} old log files.")
            
        except Exception as e:
            print(f"Cleanup failed: {e}")

def setup_logging(app: Flask):
    """Setup application logging"""
    
    # Flask's default logger
    if not app.debug:
        # In production, reduce Flask's default logging
        app.logger.setLevel(logging.WARNING)
    
    # Log application startup
    logger.info(f"Starting K8s Auto Installer API server")
    logger.info(f"Environment: {settings.environment.value}")
    logger.info(f"Debug mode: {settings.flask.debug}")
    logger.info(f"Log level: {settings.log_level.value}")
    logger.info(f"Logs directory: {settings.storage.logs_directory}")

def initialize_extensions(app: Flask):
    """Initialize Flask extensions and services"""
    
    # Ensure required directories exist
    ensure_directory(settings.storage.logs_directory)
    ensure_directory(settings.storage.temp_directory)
    ensure_directory(settings.storage.backup_directory)
    
    # Initialize log manager (already done on import, but ensure it's working)
    if hasattr(log_manager, 'websocket_handler') and log_manager.websocket_handler:
        logger.info("WebSocket log streaming enabled")
    
    logger.info("Extensions initialized")

# Frontend routes (for serving the web interface)
def register_frontend_routes(app: Flask):
    """Register frontend routes"""
    
    @app.route('/')
    def index():
        """Main dashboard"""
        return render_template('index.html')
    
    @app.route('/dashboard')
    def dashboard():
        """Installation dashboard"""
        return render_template('dashboard.html')
    
    @app.route('/install')
    def install_form():
        """Installation form"""
        return render_template('install.html')
    
    @app.route('/docs')
    def documentation():
        """Documentation page"""
        return render_template('docs.html')
    
    # Serve static files
    @app.route('/static/<path:filename>')
    def static_files(filename):
        """Serve static files"""
        return send_from_directory(app.static_folder, filename)

# Create the Flask application
app = create_app()

# Register frontend routes if templates exist
template_dir = Path(app.template_folder)
if template_dir.exists():
    register_frontend_routes(app)
    logger.info("Frontend routes registered")

# Development server configuration
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='K8s Auto Installer API Server')
    parser.add_argument(
        '--host', 
        default=settings.flask.host,
        help=f'Host to bind to (default: {settings.flask.host})'
    )
    parser.add_argument(
        '--port', 
        type=int,
        default=settings.flask.port,
        help=f'Port to bind to (default: {settings.flask.port})'
    )
    parser.add_argument(
        '--debug', 
        action='store_true',
        default=settings.flask.debug,
        help='Enable debug mode'
    )
    parser.add_argument(
        '--reload',
        action='store_true', 
        default=False,
        help='Enable auto-reload on code changes'
    )
    
    args = parser.parse_args()
    
    # Override settings with command line arguments
    if args.debug:
        app.config['DEBUG'] = True
        settings.flask.debug = True
    
    logger.info(f"Starting development server on {args.host}:{args.port}")
    logger.info(f"Debug mode: {app.config['DEBUG']}")
    
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=app.config['DEBUG'],
            use_reloader=args.reload,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        logger.info("Shutting down...")
        log_manager.shutdown()
        logger.info("Shutdown complete")

# WSGI entry point for production deployment
def application(environ, start_response):
    """WSGI application entry point"""
    return app(environ, start_response)

# Gunicorn hooks (if using Gunicorn)
def on_starting(server):
    """Called just before the master process is initialized."""
    logger.info("Gunicorn server starting...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    logger.info("Gunicorn server reloading...")

def worker_int(worker):
    """Called just after a worker has been killed by SIGINT or SIGQUIT."""
    logger.info(f"Worker {worker.pid} interrupted")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    logger.error(f"Worker {worker.pid} aborted")

def on_exit(server):
    """Called just before exiting."""
    logger.info("Gunicorn server exiting...")
    log_manager.shutdown()

# Configuration validation on startup
validation_errors = []

# Check if running as root for localhost installations
if settings.environment.value != 'testing':
    # Only warn about root access in non-testing environments
    if os.geteuid() != 0:
        logger.warning(
            "Not running as root - localhost installations will fail. "
            "Run with sudo for All-in-One installations."
        )

# Check required directories
for directory in [settings.storage.logs_directory, settings.storage.temp_directory]:
    if not os.path.exists(directory):
        try:
            ensure_directory(directory)
        except Exception as e:
            validation_errors.append(f"Cannot create directory {directory}: {e}")

# Log validation results
if validation_errors:
    for error in validation_errors:
        logger.error(f"Validation error: {error}")
    
    if settings.environment.value == 'production':
        logger.error("Validation errors in production environment - exiting")
        sys.exit(1)
else:
    logger.info("Application validation passed")

# Export for external use
__all__ = ['app', 'create_app']