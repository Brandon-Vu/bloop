import os
import re
import csv
import io
from datetime import datetime, timedelta
from openai import OpenAI
from finance_utils import format_finance_data  # For formatting CSV data for display
from category_keywords import CATEGORY_KEYWORDS
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Get values from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")    

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def get_user_id():
    user_id = os.environ.get("SAIVE_USER_ID")
    if not user_id:
        print("No user ID provided. Please log in first and set SAIVE_USER_ID.")
    return user_id

def initialize_finance_csv():
    """
    Checks if the current user (by SAIVE_USER_ID) has finance data.
    If not, it initializes the user_finance field with the CSV header.
    """
    user_id = get_user_id()
    if not user_id:
        return
    response = supabase.from_("users").select("user_finance").eq("id", user_id).single().execute()
    if not response.data or not response.data.get("user_finance"):
        header = "Date,Time,Description,Transaction Type,Amount,Balance,Category\n"
        supabase.from_("users").update({"user_finance": header}).eq("id", user_id).execute()

def read_finance_csv():
    """
    Reads the CSV text stored in the user_finance column of the users table.
    If the field is empty, it initializes it with a header row.
    """
    user_id = get_user_id()
    if not user_id:
        return []
    response = supabase.from_("users").select("user_finance").eq("id", user_id).single().execute()
    if response.data and response.data.get("user_finance"):
        csv_text = response.data["user_finance"]
    else:
        csv_text = "Date,Time,Description,Transaction Type,Amount,Balance,Category\n"
        supabase.from_("users").update({"user_finance": csv_text}).eq("id", user_id).execute()
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    return list(reader)

def write_finance_csv(rows):
    """
    Writes the CSV content (generated from rows) back to the user_finance column.
    """
    header = ["Date", "Time", "Description", "Transaction Type", "Amount", "Balance", "Category"]
    f = io.StringIO()
    writer = csv.DictWriter(f, fieldnames=header)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    new_csv_text = f.getvalue()
    user_id = get_user_id()
    if not user_id:
        return False
    response = supabase.from_("users").update({"user_finance": new_csv_text}).eq("id", user_id).execute()
    if not response.data:
        print("Error updating user_finance in DB:", response)
        return False
    return True

def get_latest_balance():
    rows = read_finance_csv()
    if not rows:
        return 0.0
    try:
        last_row = rows[-1]
        return float(last_row["Balance"])
    except Exception as e:
        print("Error reading balance from CSV data:", e)
        return 0.0

def add_finance_entry(date, description, txn_type, amount, category):
    rows = read_finance_csv()
    balance = get_latest_balance()
    new_balance = balance + amount if txn_type == "credit" else balance - amount
    time_now = datetime.now().strftime("%H:%M:%S")
    
    new_row = {
        "Date": date,
        "Time": time_now,
        "Description": description,
        "Transaction Type": txn_type,
        "Amount": amount,
        "Balance": new_balance,
        "Category": category
    }
    rows.append(new_row)
    if write_finance_csv(rows):
        return new_row
    else:
        return None

def is_exit_command(text):
    return any(keyword in text.lower() for keyword in ["exit", "quit", "bye", "goodbye"])

def auto_categorize(description):
    desc = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in desc for word in keywords):
            return category.capitalize()
    return "Uncategorized"

def clean_description(desc):
    filler_words = [
        "today", "yesterday", "last week", "2 weeks ago",
        "with cash", "cash", "using", "via", "at", "for", "in", "on",
        "a", "an", "the", "just", "only", "my", "me"
    ]
    pattern = re.compile(r'\b(' + '|'.join(re.escape(word) for word in filler_words) + r')\b', flags=re.IGNORECASE)
    desc = pattern.sub('', desc)
    desc = desc.strip(" ,.-")
    desc = re.sub(r'\s+', ' ', desc)
    return " ".join(word.capitalize() if word.lower() not in ["and", "or", "the", "of"] else word for word in desc.split())

def parse_relative_date(text):
    today = datetime.today()
    if "2 weeks ago" in text:
        return (today - timedelta(weeks=2)).strftime("%Y-%m-%d")
    elif "a week ago" in text or "last week" in text or "1 week ago" in text:
        return (today - timedelta(weeks=1)).strftime("%Y-%m-%d")
    elif "yesterday" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in text:
        return today.strftime("%Y-%m-%d")
    else:
        return today.strftime("%Y-%m-%d")

def extract_natural_entry(user_input):
    text = user_input.lower()
    date = parse_relative_date(text)
    
    if "cash" in text:
        transaction_type = "cash"
    elif any(word in text for word in ["spent", "paid", "bought", "used", "purchased"]):
        transaction_type = "debit"
    elif any(word in text for word in ["received", "got", "earned", "gift", "given", "found"]):
        transaction_type = "credit"
    else:
        transaction_type = "credit"
    
    description = "Uncategorized"
    amount = None

    patterns = [
        (r"(\b\w+\b)\s+(?:sent|gave|offered|provided|gifted)\s+me\s+(\d+(?:\.\d+)?)",
         lambda m: (f"Gift from {m.group(1).capitalize()}", float(m.group(2)))),
        (r"(?:my|from)?\s*(grandma|mum|mom|dad|friend|sister|brother|uncle|aunt).*?(?:gave|sent)\s+me\s+(\d+(?:\.\d+)?)",
         lambda m: (f"Gift from {m.group(1).capitalize()}", float(m.group(2)))),
        (r"(?:bought|spent|paid) (.+?) (?:for|at|with) (\d+(?:\.\d+)?)",
         lambda m: (clean_description(m.group(1)), float(m.group(2)))),
        (r"received (\d+(?:\.\d+)?) from (.+)",
         lambda m: (clean_description(m.group(2)), float(m.group(1)))),
        (r"got paid (\d+(?:\.\d+)?)",
         lambda m: ("Salary", float(m.group(1)))),
        (r"my boss .*?(?:gave|offered|granted) me .*?(\d+(?:\.\d+)?)",
         lambda m: ("Raise from Boss", float(m.group(1)))),
        (r"used (\d+(?:\.\d+)?) .*? for (.+)",
         lambda m: (clean_description(m.group(2)), float(m.group(1)))),
    ]

    for pattern, extractor in patterns:
        match = re.search(pattern, text)
        if match:
            description, amount = extractor(match)
            break

    if amount is None:
        finance_keywords = ["spent", "paid", "bought", "received", "salary", "gift", "used"]
        if any(word in text for word in finance_keywords):
            numbers = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", text) if float(n) > 1]
            if numbers:
                amount = max(numbers)
        else:
            return None

    if amount:
        description = clean_description(description)
        category = auto_categorize(description)
        return date, description, transaction_type, amount, category

    return None

def handle_summary_query(user_input):
    import pandas as pd

    rows = read_finance_csv()
    if not rows:
        return "No finance data found."

    df = pd.DataFrame(rows)
    match = re.search(r"between (\d{1,2}:\d{2}) ?(am|pm)? to (\d{1,2}:\d{2}) ?(am|pm)?", user_input, re.IGNORECASE)
    if match:
        t1 = match.group(1)
        ampm1 = match.group(2) or ""
        t2 = match.group(3)
        ampm2 = match.group(4) or ""
        
        fmt = "%I:%M %p" if ampm1 or ampm2 else "%H:%M"
        try:
            t1_24 = datetime.strptime(f"{t1} {ampm1}".strip(), fmt).time()
            t2_24 = datetime.strptime(f"{t2} {ampm2}".strip(), fmt).time()
        except Exception as e:
            return "Sorry, I couldn't understand the time format."
        
        today = datetime.today().strftime("%Y-%m-%d")
        df_today = df[df["Date"] == today]
        df_today["Time"] = pd.to_datetime(df_today["Time"]).dt.time
        df_filtered = df_today[(df_today["Time"] >= t1_24) & (df_today["Time"] <= t2_24)]
        received = df_filtered[df_filtered["Transaction Type"] == "credit"]
        total_received = received["Amount"].astype(float).sum()
        return f"📥 You received £{total_received:.2f} between {t1} {ampm1} and {t2} {ampm2} today."

    return None

def get_response(user_message):
    print("Received message in chatbot.py:", user_message)
    
    if is_exit_command(user_message):
        return "Goodbye!"
    
    # Check if the user is asking for their balance.
    if "balance" in user_message.lower():
        balance = get_latest_balance()
        reply = f"Your current balance is: £{balance:.2f}"
        print("Returning reply (balance query):", reply)
        return reply

    # Check if the message creates a new finance entry.
    new_entry = extract_natural_entry(user_message)
    if new_entry and all(new_entry):
        date, desc, txn_type, amt, category = new_entry
        result = add_finance_entry(date, desc, txn_type, amt, category)
        if result:
            reply = f"✅ Entry added: {desc} ({txn_type}) of £{amt} on {date} in {category}"
            print("Entry added reply:", reply)
            return reply
        else:
            return "❌ Failed to add the entry."

    # Otherwise, delegate to OpenAI for a general response.
    conversation_history = [
        {"role": "system", "content": "You are Saive, your personal AI financial advisor."},
        {"role": "user", "content": user_message}
    ]
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            store=True,
            messages=conversation_history
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Error communicating with API: {e}"
    
    print("Returning reply:", reply)
    return reply

def chat_with_saive():
    conversation_history = []
    # Initialize the user's finance data in the DB if necessary.
    initialize_finance_csv()
    finance_data = read_finance_csv()
    finance_output = format_finance_data(finance_data)

    conversation_history.append({
        "role": "system",
        "content": f"You are Saive, your personal AI financial advisor. Use the following finance data as reference:\n{finance_output}"
    })

    print("Welcome to Saive 🧠💰 — your personal finance assistant!")
    print("Type something like 'I spent 10 on lunch today' or 'Got paid 500 yesterday'.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if is_exit_command(user_input):
            print("Saive: Goodbye! Stay financially sharp. 🤑")
            break
        
        new_entry = extract_natural_entry(user_input)
        if new_entry and all(new_entry):
            date, desc, txn_type, amt, category = new_entry
            result = add_finance_entry(date, desc, txn_type, amt, category)
            if result:
                print(f"✅ Entry added: {desc} ({txn_type}) of £{amt} on {date} in {category}")
                finance_data = read_finance_csv()
                finance_output = format_finance_data(finance_data)
                conversation_history[0]["content"] = (
                    f"You are Saive, your personal AI financial advisor. "
                    f"Use the following finance data as reference:\n{finance_output}"
                )
            else:
                print("❌ Failed to add the entry.")
            continue

        conversation_history.append({"role": "user", "content": user_input})
        try:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                store=True,
                messages=conversation_history
            )
            reply = completion.choices[0].message.content
        except Exception as e:
            reply = f"Error communicating with API: {e}"
        print("Saive:", reply)
        conversation_history.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    chat_with_saive()
