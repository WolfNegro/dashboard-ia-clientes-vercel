# app/__init__.py

from flask import Flask
from dotenv import load_dotenv

def create_app():
    """
    Función de fábrica para crear y configurar la aplicación Flask.
    """
    load_dotenv() # Carga las variables de entorno
    
    app = Flask(__name__)
    
    # Envolvemos las importaciones y el registro en el contexto de la aplicación
    # para evitar importaciones circulares y asegurar que todo esté disponible.
    with app.app_context():
        # Importamos las rutas, que ahora contienen la función de limpieza
        from . import routes
        
        # Registramos el blueprint en la aplicación
        app.register_blueprint(routes.routes)
        
        # ==============================================================================
        #    CIRUGÍA FINAL: LLAMADA DIRECTA A LA FUNCIÓN DE LIMPIEZA
        # ==============================================================================
        # En lugar de usar el obsoleto 'before_first_request', llamamos a la función
        # directamente aquí. Se ejecutará una sola vez cuando el servidor arranque.
        
        # routes.limpiar_cache_antiguo()

        # ==============================================================================
        #    FIN DE LA CIRUGÍA
        # ==============================================================================

    # Devolvemos la aplicación creada
    return app