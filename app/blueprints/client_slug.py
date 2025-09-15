from flask import Blueprint, render_template

client_bp = Blueprint("client_bp", __name__)

# Acepta ambas URLs
@client_bp.route("/s/<slug>")
@client_bp.route("/dashboard/<slug>")
def client_slug(slug):
    return render_template("index.html", slug=slug)
