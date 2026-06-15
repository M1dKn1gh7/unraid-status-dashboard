import os
import requests as req
from flask import Flask, jsonify, send_from_directory, request, Response, abort
from cache import cache
from config import Config
from collectors import system, media, ups, network, unraid

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
    data["unraid"] = cache.get("unraid", Config.CACHE_TTL_UNRAID, unraid.collect)
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


@app.route("/api/img")
def api_img():
    img_path = request.args.get("path", "")
    if not img_path or not Config.TAUTULLI_API_KEY:
        abort(404)
    try:
        r = req.get(
            f"{Config.TAUTULLI_URL}/api/v2",
            params={
                "apikey": Config.TAUTULLI_API_KEY,
                "cmd": "pms_image_proxy",
                "img": img_path,
                "width": 120,
                "height": 180,
                "fallback": "poster",
            },
            timeout=5,
        )
        return Response(r.content, content_type=r.headers.get("content-type", "image/jpeg"))
    except Exception:
        abort(502)


@app.route("/api/all")
def api_all():
    sys_data = cache.get("system", Config.CACHE_TTL_SYSTEM, system.collect)
    sys_data["unraid"] = cache.get("unraid", Config.CACHE_TTL_UNRAID, unraid.collect)
    return jsonify({
        "system": sys_data,
        "media": cache.get("media", Config.CACHE_TTL_MEDIA, media.collect),
        "ups": cache.get("ups", Config.CACHE_TTL_UPS, ups.collect),
        "network": cache.get("network", Config.CACHE_TTL_NETWORK, network.collect),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
