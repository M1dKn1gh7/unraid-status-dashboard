import os
from flask import Flask, jsonify, send_from_directory
from cache import cache
from config import Config
from collectors import system, media, ups, network

app = Flask(__name__, static_folder="static")


@app.route("/")
def index():
    return send_from_directory("static", "dashboard.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/system")
def api_system():
    data = cache.get("system", Config.CACHE_TTL_SYSTEM, system.collect)
    return jsonify(data)


@app.route("/api/media")
def api_media():
    data = cache.get("media", Config.CACHE_TTL_MEDIA, media.collect)
    return jsonify(data)


@app.route("/api/ups")
def api_ups():
    data = cache.get("ups", Config.CACHE_TTL_UPS, ups.collect)
    return jsonify(data)


@app.route("/api/network")
def api_network():
    data = cache.get("network", Config.CACHE_TTL_NETWORK, network.collect)
    return jsonify(data)


@app.route("/api/all")
def api_all():
    return jsonify({
        "system": cache.get("system", Config.CACHE_TTL_SYSTEM, system.collect),
        "media": cache.get("media", Config.CACHE_TTL_MEDIA, media.collect),
        "ups": cache.get("ups", Config.CACHE_TTL_UPS, ups.collect),
        "network": cache.get("network", Config.CACHE_TTL_NETWORK, network.collect),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
