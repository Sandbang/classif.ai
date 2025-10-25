import shutil
import uuid
from flask import Flask, request, redirect, url_for, render_template, send_from_directory, flash
from PIL import Image
from werkzeug.utils import secure_filename
import io
import base64
import json

# Attempt to import project grading modules
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import find_text_lines
import grade_proof
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ANNOTATED_FOLDER = os.path.join(BASE_DIR, 'static', 'annotated')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ANNOTATED_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ANNOTATED_FOLDER'] = ANNOTATED_FOLDER
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_prefix = uuid.uuid4().hex[:8]
        saved_name = f"{unique_prefix}_{filename}"
        saved_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
        file.save(saved_path)

        # 1) Run text line detection to get boxed image array and layout
        boxed_image_array, layout_data_list = find_text_lines.find_text_lines(saved_path)
        if boxed_image_array is None or layout_data_list is None:
            flash('Text line detection failed. See server logs for details.')
            return redirect(url_for('index'))

        # 2) Call the grading model (this may require ANTHROPIC_API_KEY in env)
        grading_result = grade_proof.grade_proof_image(image_array=boxed_image_array)

        # 3) Build layout_map expected by annotate_image
        try:
            layout_map = {item['number']: item['box'] for item in layout_data_list}
        except Exception:
            flash('Layout data format unexpected. See server logs.')
            return redirect(url_for('index'))

        # 4) Prepare errors and render the original uploaded (unannotated) image with web overlay
        errors = grading_result.get('errors', []) if grading_result else []

        # Use the uploaded image file directly for display (no pre-drawn boxes)
        display_rel_path = os.path.join('static', 'uploads', os.path.basename(saved_path)).replace('\\', '/')

        # Get image dimensions for overlay scaling in the template (use uploaded image)
        img_width = img_height = None
        try:
            with Image.open(saved_path) as im:
                img_width, img_height = im.size
        except Exception:
            img_width, img_height = None, None

        return render_template(
            'result.html',
            display_image=display_rel_path,
            grading=grading_result,
            layout_data_list=layout_data_list,
            errors=errors,
            img_width=img_width,
            img_height=img_height,
        )

    flash('File type not allowed')
    return redirect(url_for('index'))


@app.route('/static/annotated/<path:filename>')
def serve_annotated(filename):
    return send_from_directory(app.config['ANNOTATED_FOLDER'], filename)


@app.route('/explain', methods=['POST'])
def explain():
    """Endpoint to ask Claude for an explanation about a specific comment/line.
    Expects JSON: { image_path: 'static/uploads/xxx.jpg', box: [x,y,w,h], comment: 'text', question: '...' }
    Returns JSON { answer: 'text' }
    """
    payload = request.get_json()
    image_rel = payload.get('image_path')
    box = payload.get('box')
    comment_text = payload.get('comment', '')
    question = payload.get('question', '')

    if not image_rel or not box or not question:
        return ({'error': 'Missing required fields (image_path, box, question)'}), 400

    # Resolve file path
    image_path = os.path.join(BASE_DIR, image_rel)
    if not os.path.exists(image_path):
        return ({'error': 'Image file not found'}), 404

    # Load and crop the image region
    try:
        with Image.open(image_path) as im:
            im = im.convert('RGB')
            x, y, w, h = box
            # add slight padding
            pad = int(max(2, min(20, min(w, h) * 0.08)))
            left = max(0, int(x - pad))
            top = max(0, int(y - pad))
            right = min(im.width, int(x + w + pad))
            bottom = min(im.height, int(y + h + pad))
            crop = im.crop((left, top, right, bottom))

            bio = io.BytesIO()
            crop.save(bio, format='JPEG')
            b64 = base64.b64encode(bio.getvalue()).decode('utf-8')
    except Exception as e:
        return ({'error': f'Could not crop image: {e}'}), 500

    # Build the message content for Claude
    system_prompt = (
        "You are an assistant that explains student's math proof steps concisely. "
        "Provide a clear explanation targeted at an undergraduate-level student."
    )

    user_message_content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
        {"type": "text", "text": f"Student line context: {comment_text}\n\nQuestion: {question}\n\nBe concise and explain the issue or provide guidance."}
    ]

    try:
        resp = grade_proof.client.messages.create(
            model=grade_proof.MODEL_NAME,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message_content}],
        )
        raw_text = resp.content[0].text
        # strip code fences if present
        if raw_text.startswith('```'):
            # remove triple backticks block
            try:
                raw_text = raw_text.split('```', 2)[2].strip()
            except Exception:
                raw_text = raw_text.strip('`')

        return ({'answer': raw_text}), 200
    except Exception as e:
        return ({'error': f'API error: {e}'}), 500



if __name__ == '__main__':
    # Run on localhost:5000
    app.run(host='127.0.0.1', port=5000, debug=True)
