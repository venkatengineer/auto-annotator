import os
import json
from flask import Flask, render_template, request, Response, jsonify
from script import run_annotation

app = Flask(__name__)

def translate_path(path):
    if not path:
        return path
    # Normalize slashes for uniform comparison
    norm_path = path.replace('\\', '/')
    host_prefix = "D:/CDAC/Venkat"
    if norm_path.lower().startswith(host_prefix.lower()):
        relative_part = norm_path[len(host_prefix):].lstrip('/')
        translated = os.path.join('/data', relative_part)
        return os.path.normpath(translated)
    return path

def to_host_path(container_path):
    if not container_path:
        return container_path
    norm_path = os.path.normpath(container_path).replace('\\', '/')
    if norm_path == '/data' or norm_path.startswith('/data/'):
        relative_part = norm_path[len('/data'):].lstrip('/')
        host_path = os.path.join('D:\\CDAC\\Venkat', relative_part.replace('/', '\\'))
        return host_path
    return container_path

@app.route('/api/resolve_folder')
def api_resolve_folder():
    folder_name = request.args.get('folder_name', '').strip()
    first_file = request.args.get('first_file', '').strip()
    
    if not folder_name:
        return jsonify({'error': 'Folder name is required'}), 400
        
    matched_path = None
    # Search under /data for a directory matching the selected name containing the target file
    for root, dirs, files in os.walk('/data'):
        if os.path.basename(root).lower() == folder_name.lower():
            if first_file:
                if first_file in files:
                    matched_path = root
                    break
            else:
                matched_path = root
                break
                
    if not matched_path:
        # Fallback: check matching folder names without file validation
        for root, dirs, files in os.walk('/data'):
            if os.path.basename(root).lower() == folder_name.lower():
                matched_path = root
                break
                
    if matched_path:
        host_path = to_host_path(matched_path)
        return jsonify({
            'container_path': matched_path,
            'host_path': host_path
        })
        
    return jsonify({'error': 'Could not resolve path. Make sure the folder is under D:\\CDAC\\Venkat.'}), 404

@app.route('/')
def index():
    # Render main dashboard page
    return render_template('index.html')

@app.route('/run')
def run():
    image_folder = request.args.get('image_folder', '').strip()
    label_folder = request.args.get('label_folder', '').strip()
    
    if not image_folder:
        def err_stream():
            yield f"data: {json.dumps({'error': 'Image directory path is required.'})}\n\n"
        return Response(err_stream(), mimetype='text/event-stream')

    # Translate paths from host path to container path
    translated_image_folder = translate_path(image_folder)

    if not label_folder:
        # Default label folder to sibling 'anno' directory
        clean_img = translated_image_folder.rstrip('/\\')
        parent = os.path.dirname(clean_img)
        translated_label_folder = os.path.join(parent, 'anno')
    else:
        translated_label_folder = translate_path(label_folder)

    def event_stream():
        try:
            # Output helpful system logs showing translation mapping
            yield f"data: {json.dumps({'message': f'[SYSTEM] Host image path: {image_folder}'})}\n\n"
            yield f"data: {json.dumps({'message': f'[SYSTEM] Resolved container path: {translated_image_folder}'})}\n\n"
            if label_folder:
                yield f"data: {json.dumps({'message': f'[SYSTEM] Host label path: {label_folder}'})}\n\n"
                yield f"data: {json.dumps({'message': f'[SYSTEM] Resolved container path: {translated_label_folder}'})}\n\n"
            else:
                yield f"data: {json.dumps({'message': f'[SYSTEM] Dynamic label container path: {translated_label_folder}'})}\n\n"
            
            for log in run_annotation(translated_image_folder, translated_label_folder):
                yield f"data: {json.dumps({'message': log})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    # Listen on all interfaces on port 5000 inside the container
    app.run(host='0.0.0.0', port=5000, debug=True)
