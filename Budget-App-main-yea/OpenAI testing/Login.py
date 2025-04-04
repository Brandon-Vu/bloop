from flask import Flask, request, redirect, render_template_string
from supabase import create_client, Client
import bcrypt
import re
import csv
import os
from dotenv import load_dotenv
app = Flask(__name__)

load_dotenv()

# Get values from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Password Strength Checker ---
def is_valid_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r'\d', password):
        return False, "Password must include at least one digit."
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
        return False, "Password must include at least one special character."
    return True, "Password is valid."

# --- Serve Login/Register Page ---
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Saive - Login</title>
      <style>
        body {
          font-family: Arial, sans-serif;
          background: linear-gradient(to bottom right, #5f6dff, #47a0ff);
          color: white;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
        }
        form {
          background: rgba(255, 255, 255, 0.1);
          padding: 30px;
          border-radius: 10px;
          text-align: center;
        }
        input {
          padding: 10px;
          margin: 10px 0;
          width: 200px;
        }
        button {
          padding: 10px 20px;
          margin: 10px;
        }
      </style>
    </head>
    <body>
      <h1>Welcome to Saive</h1>
      <form method="POST" action="/auth">
        <input type="text" name="username" placeholder="Username" required /><br />
        <input type="password" name="password" placeholder="Password" required /><br />
        <button name="action" value="login">Login</button>
        <button name="action" value="register">Register</button>
      </form>
    </body>
    </html>
    '''

# --- Handle Authentication ---
@app.route('/auth', methods=['POST'])
def auth():
    username = request.form['username']
    password = request.form['password']
    action = request.form['action']

    if action == "register":
        valid, msg = is_valid_password(password)
        if not valid:
            return f"<h3>{msg}</h3><a href='/'>Back</a>"

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            supabase.table("users").insert({"username": username, "password_hash": hashed}).execute()
            return "<h3>✅ Registration successful. <a href='/'>Go login</a></h3>"
        except Exception as e:
            return f"<h3>❌ Error: Username may already exist.<br>{e}</h3><a href='/'>Back</a>"

    elif action == "login":
        try:
            result = supabase.table("users").select("*").eq("username", username).execute()
            user = result.data[0] if result.data else None
            if user and bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                return redirect("/home")
            else:
                return "<h3>❌ Invalid username or password.</h3><a href='/'>Try again</a>"
        except Exception as e:
            return f"<h3>❌ Login error:<br>{e}</h3><a href='/'>Try again</a>"

# --- Home Page Redirect ---
@app.route('/home')
def home():
    try:
        with open('home.html') as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>home.html not found. Please check your file.</h3>"

# --- Run Server ---
if __name__ == '__main__':
    app.run(debug=True)
