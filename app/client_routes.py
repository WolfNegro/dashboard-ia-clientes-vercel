# app/client_routes.py
from flask import render_template
from app import app

@app.route("/s/<slug>")
def client_slug(slug):
    # Renderiza tu plantilla principal y pasa el slug (la plantilla puede ignorarlo si no lo usa)
    return render_template("index.html", slug=slug)
