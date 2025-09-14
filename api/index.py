from app import create_app

# Crea la app Flask de tu proyecto
app = create_app()

# Si Vercel/Proxy está delante, corrige cabeceras para URL/host correctos
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
except Exception:
    pass

# Vercel detecta 'app' como aplicación WSGI automáticamente
