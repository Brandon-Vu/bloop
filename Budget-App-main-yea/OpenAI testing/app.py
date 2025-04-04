from flask import Flask, request, jsonify, send_file
import os
from chatbot import get_response  # Ensure chatbot.py is in the same directory

app = Flask(__name__)

# Serve index.html as the default login page
@app.route('/')
def index():
    return send_file("index.html")

# Route for home.html
@app.route('/home.html')
def home():
    return send_file("home.html")

# Route for monthly-charts.html
@app.route('/monthly-charts.html')
def monthly_charts():
    return send_file("monthly-charts.html")

# Route for saym.html
@app.route('/saym.html')
def saym():
    return send_file("saym.html")

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data.get("user_id")
    message = data.get("message")
    if not user_id or not message:
        return jsonify({"error": "Missing user_id or message"}), 400

    # Set the environment variable for the current session.
    os.environ["SAIVE_USER_ID"] = user_id

    # Get the chatbot response.
    response = get_response(message)
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)
