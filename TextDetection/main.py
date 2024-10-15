from flask import Flask, render_template, request, redirect, url_for, flash
from PIL import Image, ImageEnhance, ImageOps, ImageDraw
import easyocr
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_config import auth

cred = credentials.Certificate('C:/Users/Kraljevic-pc/Downloads/text-detection-app.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'text-detection-app-c6172.appspot.com'
})

db = firestore.client()

app = Flask(__name__)
app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = 'static/uploads/'
PROCESSED_FOLDER = 'static/processed/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

reader = easyocr.Reader(['en'])


def preprocess_image(image_path):
    img = Image.open(image_path)

    img = ImageOps.grayscale(img)

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)

    img = img.point(lambda p: p > 128 and 255)

    img.save(image_path)
    return img

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    return render_template('index.html')

# Route to handle image upload and OCR
from PIL import Image, ImageDraw

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        flash("No file part")
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        flash("No selected file")
        return redirect(url_for('index'))

    if 'user' not in session:
        flash("You need to be logged in to upload images.", "warning")
        return redirect(url_for('login'))

    if file:
        # Save the uploaded image locally
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(image_path)

        # Preprocess the image (optional step)
        preprocess_image(image_path)

        # Perform OCR on the image using EasyOCR
        result = reader.readtext(image_path)

        # Load the image using PIL to draw bounding boxes
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        # Loop through the results and draw bounding boxes
        for (bbox, text, prob) in result:
            # Extract the coordinates of the bounding box
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)

            # Draw a rectangle around the text
            draw.rectangle([min_x, min_y, max_x, max_y], outline="green", width=3)

        # Save the image with bounding boxes
        processed_image_path = os.path.join(app.config['PROCESSED_FOLDER'], file.filename)
        img.save(processed_image_path)

        # Extract text from OCR result
        ocr_text = '\n'.join([item[1] for item in result])

        # Get the current user's email (from session)
        user_email = auth.get_account_info(session['user'])['users'][0]['email']

        # Upload the image to Firebase Storage and get the public URL
        image_url = upload_to_firebase(processed_image_path, file.filename)

        # Save OCR results and image URL to Firestore
        save_to_firestore(file.filename, ocr_text, image_url, user_email)

        return render_template('index.html', detected_text=ocr_text, image_path=image_url)



@app.route('/delete_file', methods=['POST'])
def delete_file():
    if 'user' not in session:
        return redirect(url_for('login'))

    file_name = request.form['file_name']
    image_url = request.form['image_url']

    # Delete the file from Firebase Storage
    bucket = storage.bucket()
    blob = bucket.blob(file_name)  # The file name is used as the blob name
    try:
        blob.delete()  # Delete the image from Firebase Storage
    except Exception as e:
        return redirect(url_for('show_all_files'))  # If there's an error, redirect silently

    # Delete the corresponding Firestore document
    try:
        db.collection('ocr_results').document(file_name).delete()  # Delete Firestore entry
    except Exception as e:
        return redirect(url_for('show_all_files'))  # If there's an error, redirect silently

    # Redirect back to the files page after deletion
    return redirect(url_for('show_all_files'))

@app.route('/files', methods=['GET'])
def show_all_files():
    # Ensure the user is logged in
    if 'user' not in session:
        flash("You need to log in to view your files.", "warning")
        return redirect(url_for('login'))

    # Get the current user's email from the session
    user_email = auth.get_account_info(session['user'])['users'][0]['email']

    # Query Firestore for documents where the user_email matches the logged-in user's email
    docs = db.collection('ocr_results').where('user_email', '==', user_email).stream()

    # Create a list to store file data (image URLs and OCR results)
    files = []
    for doc in docs:
        file_data = doc.to_dict()  # Convert Firestore document to dictionary
        files.append(file_data)

    # Pass the files data to the HTML template
    return render_template('files.html', files=files)
def upload_to_firebase(image_path, file_name):
    bucket = storage.bucket()  # Get Firebase Storage bucket
    blob = bucket.blob(file_name)  # Create a blob for the image file
    blob.upload_from_filename(image_path)  # Upload image to Firebase Storage
    blob.make_public()  # Make the file publicly accessible
    return blob.public_url  # Return the public URL of the image

def save_to_firestore(file_name, ocr_text, image_url, user_email):
    # Reference to Firestore collection
    doc_ref = db.collection('ocr_results').document(file_name)

    # Data to store, including the user's email
    data = {
        'file_name': file_name,
        'ocr_text': ocr_text,
        'image_url': image_url,
        'user_email': user_email,  # Store the email of the user who uploaded the image
    }

    # Add document to Firestore
    doc_ref.set(data)



from flask import Flask, render_template, request, redirect, url_for, flash, session
from firebase_config import auth  # Import the Firebase Auth object


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Register the user with email and password
            user = auth.create_user_with_email_and_password(email, password)
            session['user'] = user['idToken']  # Store the user's token in session
            return redirect(url_for('index'))  # Redirect to dashboard or homepage
        except Exception as e:
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Sign in the user with email and password
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = user['idToken']  # Store the user's token in session
            return redirect(url_for('index'))  # Redirect to dashboard or homepage
        except Exception as e:
            return redirect(url_for('login'))

    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove the user from the session
    return redirect(url_for('login'))





if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(PROCESSED_FOLDER):
        os.makedirs(PROCESSED_FOLDER)
    app.run(debug=True)
