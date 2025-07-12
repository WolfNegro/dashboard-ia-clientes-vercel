from app import create_app

# Crear instancia de la app Flask desde factory
app = create_app()

if __name__ == "__main__":
    # Ejecutar servidor local en modo debug
    app.run(host="0.0.0.0", port=5000, debug=True)
