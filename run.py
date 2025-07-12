# run.py

from app import create_app

# Llamamos a la fábrica para obtener nuestra aplicación configurada
app = create_app()

# Esta parte solo se usa cuando ejecutas el archivo localmente
if __name__ == '__main__':
    app.run(debug=True)