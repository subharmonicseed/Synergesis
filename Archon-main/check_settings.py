import asyncio
import os
from supabase import create_client

def check_settings():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not key:
        print('SUPABASE_URL or SUPABASE_SERVICE_KEY not set')
        return
    
    supabase = create_client(url, key)
    result = supabase.table('archon_settings').select('*').eq('category', 'rag_strategy').execute()
    
    print('RAG Strategy Settings:')
    for item in result.data:
        print(f'  {item["key"]}: {item["value"]}')
    
    # Check for LLM provider specifically
    llm_result = supabase.table('archon_settings').select('*').eq('key', 'LLM_PROVIDER').execute()
    if llm_result.data:
        print(f'\nLLM_PROVIDER: {llm_result.data[0]["value"]}')
    else:
        print('\nLLM_PROVIDER: Not found in database')

if __name__ == '__main__':
    check_settings()
