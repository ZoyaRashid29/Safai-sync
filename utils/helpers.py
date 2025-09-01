import json
import os
import requests
DATA_FILE = "data/complaints.json"

def load_complaints():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as file:
        return json.load(file)

def save_complaints(complaints):
    with open(DATA_FILE, "w") as file:
        json.dump(complaints, file, indent=4)

def save_uploaded_file(uploaded_file):
    file_path = os.path.join("uploads", uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path



