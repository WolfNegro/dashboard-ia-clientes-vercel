# app/__init__.py
from flask import Flask

def create_app():    
    app = Flask(__name__)    
    app.config['SECRET_KEY'] = 'la-version-definitiva-funciona'

    from .routes import routes    
    app.register_blueprint(routes)

    return app