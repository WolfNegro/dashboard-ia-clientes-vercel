# app/__init__.py

from flask import Flask
from dotenv import load_dotenv

def create_app():
    """
    Función de fábrica para crear y configurar la aplicación Flask.
    """
    load_dotenv() # Carga las variables de entorno
    
    app = Flask(__name__)
    
    # Importamos y registramos las rutas (el blueprint)
    from .routes import routes as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # Devolvemos la aplicación creada
    return app