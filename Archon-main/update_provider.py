import os
from supabase import create_client

def update_provider():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not key:
        print('SUPABASE_URL or SUPABASE_SERVICE_KEY not set')
        return
    
    supabase = create_client(url, key)
    
    # Update the LLM_PROVIDER to mistral
    result = supabase.table('archon_settings').update({
        'value': 'mistral'
    }).eq('key', 'LLM_PROVIDER').execute()
    
    print(f'Updated LLM_PROVIDER to mistral: {result}')
    
    # Also update the LLM_BASE_URL to point to our local GPT-OSS service
    result = supabase.table('archon_settings').update({
        'value': 'http://mistral:8080/v1'
    }).eq('key', 'LLM_BASE_URL').execute()
    
    print(f'Updated LLM_BASE_URL to http://mistral:8080/v1: {result}')

if __name__ == '__main__':
    update_provider()
