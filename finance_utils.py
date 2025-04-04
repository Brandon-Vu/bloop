import csv
import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get values from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def read_finance_csv(user_id):
    response = supabase \
        .from_("users") \
        .select("user_finance") \
        .eq("id", user_id) \
        .single() \
        .execute()

    if response.data and 'user_finance' in response.data:
        csv_text = response.data['user_finance']
        lines = csv_text.strip().split('\n')
        return list(csv.DictReader(lines))
    return []

def write_finance_csv(user_id, rows):
    if not rows:
        return
    headers = rows[0].keys()
    csv_lines = [','.join(headers)] + [','.join([row[h] for h in headers]) for row in rows]
    user_finance = '\n'.join(csv_lines)
    supabase \
        .from_("users") \
        .upsert({"id": user_id, "user_finance": user_finance}, on_conflict=["id"]) \
        .execute()

def format_finance_data(data):
    output = []
    for row in data:
        output.append(
            f"{row['Date']} - {row['Description']} ({row['Category']}): {row['Transaction Type']} £{row['Amount']} | Balance: £{row['Balance']}"
        )
    return "\n".join(output)
