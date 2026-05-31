from flask import Flask, request, jsonify, send_file
import subprocess
import os
import uuid
import threading

app = Flask(__name__)
CLIPS_DIR = "/tmp/clips"
os.makedirs(CLIPS_DIR, exist_ok=True)

def delete_after_delay(path, delay=300):
    """Delete clip file after 5 minutes to save space"""
    import time
    time.sleep(delay)
    if os.path.exists(path):
        os.remove(path)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/clip', methods=['POST'])
def clip():
    data = request.json
    video_url   = data.get('videoUrl')
    start_time  = int(data.get('startTime', 30))
    duration    = int(data.get('duration', 60))
    output_name = data.get('outputName', str(uuid.uuid4()))

    if not video_url:
        return jsonify({"status": "error", "error": "videoUrl is required"}), 400

    out_path = os.path.join(CLIPS_DIR, f"{output_name}.mp4")
    end_time = start_time + duration

    cmd = [
        "yt-dlp",
        "--download-sections", f"*{start_time}-{end_time}",
        "--merge-output-format", "mp4",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--no-playlist",
        "-o", out_path,
        video_url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            return jsonify({"status": "error", "error": result.stderr[-500:]}), 500

        if not os.path.exists(out_path):
            return jsonify({"status": "error", "error": "File not created"}), 500

        # Auto-delete after 5 minutes
        threading.Thread(target=delete_after_delay, args=(out_path,), daemon=True).start()

        file_size = os.path.getsize(out_path)
        return jsonify({
            "status": "success",
            "clipPath": out_path,
            "clipUrl": f"/download/{output_name}",
            "fileSizeBytes": file_size
        })

    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "error": "Timeout - video too long"}), 504
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/download/<name>', methods=['GET'])
def download(name):
    path = os.path.join(CLIPS_DIR, f"{name}.mp4")
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, mimetype='video/mp4', as_attachment=True, download_name=f"{name}.mp4")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
