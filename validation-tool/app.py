import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from validator import SimpleValidator

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)

validation_sessions = {}

class ValidationProgress:
    def __init__(self):
        self.status = "waiting"
        self.progress = 0
        self.message = ""
        self.result = None
        self.error = None
        self.timing = {
            'extraction_time': None,
            'build_time': None,
            'test_time': None,
            'total_start_time': time.time()
        }

def run_validation(session_id, zip_path, codebase_type):
    """Run validation in background thread"""
    progress = validation_sessions[session_id]
    
    try:
        progress.status = "extracting"
        progress.message = "Extracting codebase..."
        progress.progress = 10
        
        with SimpleValidator() as validator:
            result = validator.validate_codebase_with_progress(zip_path, progress, codebase_type)
            
            progress.status = "complete"
            progress.progress = 100
            progress.message = "Validation complete"
            progress.result = result
            
    except Exception as e:
        progress.status = "error"
        progress.error = str(e)
        progress.message = f"Error: {str(e)}"
    
    finally:
        if zip_path.exists():
            zip_path.unlink()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Only ZIP files are allowed'}), 400
    
    # Get codebase type
    codebase_type = request.form.get('codebase_type', 'rewrite')
    if codebase_type not in ['preedit', 'postedit', 'rewrite']:
        return jsonify({'error': 'Invalid codebase type'}), 400
    
    # Generate session ID
    import uuid
    session_id = str(uuid.uuid4())[:8]
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    zip_path = app.config['UPLOAD_FOLDER'] / f"{session_id}_{filename}"
    file.save(zip_path)
    
    # Initialize progress tracking
    validation_sessions[session_id] = ValidationProgress()
    
    # Start validation in background
    thread = threading.Thread(target=run_validation, args=(session_id, zip_path, codebase_type))
    thread.daemon = True
    thread.start()
    
    return jsonify({'session_id': session_id})

@app.route('/status/<session_id>')
def get_status(session_id):
    if session_id not in validation_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    progress = validation_sessions[session_id]
    
    response = {
        'status': progress.status,
        'progress': progress.progress,
        'message': progress.message,
        'timing': progress.timing
    }
    
    if progress.result:
        response['result'] = progress.result
    
    if progress.error:
        response['error'] = progress.error
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080) 