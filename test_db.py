#!/usr/bin/env python3
"""
Test Supabase connection
"""

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_ANON_KEY

def test_supabase():
    print(f"URL: {SUPABASE_URL}")
    print(f"Key starts with: {SUPABASE_ANON_KEY[:20]}...")

    try:
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("Client created successfully")

        # Try a simple query
        result = client.table('products').select('id').limit(1).execute()
        print(f"Query successful: {len(result.data)} rows")

    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    test_supabase()