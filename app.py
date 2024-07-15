from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import json
from pdfminer.high_level import extract_text as extract_text_from_pdf
from docx2txt import process as extract_text_from_docx
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.secret_key = 'supersecretkey'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resume_data.db'  # SQLite database file
db = SQLAlchemy(app)
class ResumeData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    it_skills = db.Column(db.Text)
    programming = db.Column(db.Text)
    front_end = db.Column(db.Text)
    back_end = db.Column(db.Text)
    database = db.Column(db.Text)
    ai_ml = db.Column(db.Text)
    other_skills = db.Column(db.Text)
    experience = db.Column(db.Text)


# Ensure the 'uploads' directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load API key from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    api_key = config.get("api_key")

# Configure Generative AI
genai.configure(api_key=api_key)
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 1000,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

# Function to extract the required info from the resume using the GenAI API
def output_text(input_text):
    chat_session = model.start_chat(history=[]) 
    response = chat_session.send_message("""This text is a resume. Please identify and extract the following information:
    Note: Follow this instruction strictly: Please do not enclose the response in '```json' in the beginning and '```' at the end.
    * Name (full name, sentence case)
    * Email address
    * Phone number (without country code)
    * IT Skills (technical skills in computer science and related fields, use sentence case,without [], in case no IT skills are mentioned or found return NONE)
      * Skills like: Strong problem-solving, analytical skills, communication, collaboration, leadership, critical thinking, attention to detail etc are not IT skills and should be in the other skills section.
    * Now add the following columns:
      * Programming: (Programming Skills from the IT skills, sentence case, If none found return NONE)
      * Front End: (Front end technology Skills from the IT skills, sentence case, If none found return NONE)
      * Back End: (Back end technology Skills from the IT skills, sentence case, If none found return NONE)
      * Database: (Database Skills from the IT skills, sentence case, If none found return NONE)
      * AI/ML: (AI/ML Skills from the IT skills, sentence case, If none found return NONE)
    * Other Skills (non-technical skills, use sentence case to rewrite each skill, if required, without [] and improve the terms if required and do not include hobbies or sports)
    * Experience (for each and every experience containing:(do not consider Education as experience and return NONE if no experience found)
        * Title (job title, sentence case)
        * Organization (company name, sentence case)
        * Duration (employment period, e.g., "Jan 2020 - Dec 2023") all three info in one line for each experience.
        eg: "Software Developer at Google, Jan 2020 - Dec 2023" , NOTE: each experience should be separated by a new line and the value should be a string.
    The output should be in proper JSON format. Note: Follow this instruction strictly: Please do not enclose 
    the response in '```json' in the beginning and '```' at the end.""" +input_text)
    return response.text

def extract_text(file_path, file_type):
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_type == 'docx':
        return extract_text_from_docx(file_path)
    elif file_type == 'txt':
        with open(file_path, 'r') as file:
            return file.read()
    else:
        return None
    
@app.context_processor
def utility_processor():
    return dict(enumerate=enumerate)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'resume' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['resume']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file:
            file_ext = file.filename.split('.')[-1].lower()
            if file_ext not in ['pdf', 'docx', 'txt']:
                flash('Unsupported file format')
                return redirect(request.url)
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            
            text = extract_text(file_path, file_ext)
            extracted_info = output_text(text)
            
            # Save extracted info in session
            extracted_data = json.loads(extracted_info)
            if 'extracted_data' not in session:
                session['extracted_data'] = []
            session['extracted_data'].append(extracted_data)
            
            resume_data = ResumeData(
            name=extracted_data.get('Name', 'Unknown'),
            email=extracted_data.get('Email address', 'Unknown'),
            phone=extracted_data.get('Phone number', 'Unknown'),
            it_skills=extracted_data.get('IT Skills', 'NONE'),
            programming=extracted_data.get('Programming', 'NONE'),
            front_end=extracted_data.get('Front End', 'NONE'),
            back_end=extracted_data.get('Back End', 'NONE'),
            database=extracted_data.get('Database', 'NONE'),
            ai_ml=extracted_data.get('AI/ML', 'NONE'),
            other_skills=extracted_data.get('Other Skills', 'NONE'),
            experience=extracted_data.get('Experience', 'NONE')
        )
        db.session.add(resume_data)
        db.session.commit()
        
        # Delete uploaded file after extraction
        os.remove(file_path)
        
        return redirect(url_for('result'))
    
    return render_template('upload.html')

@app.route('/result', methods=['GET', 'POST'])
def result():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            return redirect(url_for('upload'))
        elif action == 'clear':
            # Delete the last added entry from the database
            last_entry = ResumeData.query.order_by(ResumeData.id.desc()).first()
            if last_entry:
                db.session.delete(last_entry)
                db.session.commit()
                flash('Last entry deleted successfully')
            else:
                flash('No entries to delete')
            
            return redirect(url_for('result'))
    
    # Retrieve all stored data from the database
    extracted_data = ResumeData.query.all()
    
    return render_template('result.html', data=extracted_data)

@app.route('/view-data')
def view_data():
    all_data = ResumeData.query.all()
    return render_template('view.html', all_data=all_data)


# @app.route('/details/<int:id>')
# def details(id):
#     extracted_data = session.get('extracted_data', [])
#     if id < len(extracted_data):
#         person_details = extracted_data[id]
#         return render_template('details.html', details=person_details)
#     else:
#         flash('Invalid person ID')
#         return redirect(url_for('result'))

@app.route('/details/<int:id>')
def details(id):
    resume_data = ResumeData.query.get(id)
    if resume_data:
        return render_template('details.html', details=resume_data)
    else:
        flash('Resume data with ID {} not found.'.format(id))
        return redirect(url_for('result'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if not exist
    
    app.run(debug=True)
