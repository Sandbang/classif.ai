import shutil
import uuid
from flask import Flask, request, redirect, url_for, render_template, send_from_directory, flash
from PIL import Image
from werkzeug.utils import secure_filename

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

        # 4) Annotate image based on grading_result
        errors = grading_result.get('errors', []) if grading_result else []

        # Call the annotate function which writes a file named annotated_{name}.jpg in cwd
        grade_proof.annotate_image(
            image_array=boxed_image_array,
            layout_map=layout_map,
            errors_list=errors,
            original_image_path=saved_path,
        )

        # Expected annotated filename
        base = os.path.basename(saved_path)
        name, _ext = os.path.splitext(base)
        generated_name = f"annotated_{name}.jpg"

        # It may have been saved in the process cwd; move it into annotated folder
        generated_src = os.path.join(os.getcwd(), generated_name)
        generated_dst = os.path.join(app.config['ANNOTATED_FOLDER'], generated_name)

        if os.path.exists(generated_src):
            shutil.move(generated_src, generated_dst)
        elif os.path.exists(os.path.join(BASE_DIR, generated_name)):
            shutil.move(os.path.join(BASE_DIR, generated_name), generated_dst)
        else:
            # If the file wasn't found, still proceed but warn
            flash('Annotated image was not created as expected. Check server logs.')

        # Get image dimensions for overlay scaling in the template
        img_width = img_height = None
        try:
            with Image.open(generated_dst) as im:
                img_width, img_height = im.size
        except Exception:
            # Fall back to defaults if image isn't available yet
            img_width, img_height = None, None

        # Render result page showing the annotated image and JSON grading result
        return render_template(
            'result.html',
            annotated_image=f'static/annotated/{generated_name}',
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


if __name__ == '__main__':
    # Run on localhost:5000
    app.run(host='127.0.0.1', port=5000, debug=True)
