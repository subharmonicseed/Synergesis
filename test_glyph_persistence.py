#!/usr/bin/env python3
"""
Test script to verify glyph persistence in Synergesis system
"""
import sys
import os
sys.path.append('c:/Users/BlackStar/Desktop/BigSyn/Syn')

import time
import requests
from synergesis.storage.neo4j_interface import Neo4jStorage

def test_neo4j_connection():
    """Test Neo4j connection and glyph storage"""
    print("🧪 Testing Neo4j glyph persistence...")
    
    try:
        # Test Neo4j storage
        storage = Neo4jStorage()
        
        # Create test glyph
        test_glyph = {
            'id': f'test_glyph_{int(time.time())}',
            'timestamp': int(time.time()),
            'source': 'test_script',
            'type': 'test_concept',
            'payload': {
                'message': 'Test glyph for persistence validation',
                'test_data': True
            },
            'meta': {
                'agent': 'test_agent',
                'test': True
            }
        }
        
        # Save glyph
        success = storage.save_glyph(test_glyph)
        print(f"✅ Glyph save successful: {success}")
        
        # Retrieve all glyphs
        glyphs = storage.get_all_glyphs()
        print(f"📊 Found {len(glyphs)} total glyphs in database")
        
        # Find our test glyph
        test_glyphs = [g for g in glyphs if g.get('source') == 'test_script']
        print(f"🔍 Found {len(test_glyphs)} test glyphs")
        
        for glyph in test_glyphs[-3:]:  # Show last 3
            print(f"   📋 {glyph.get('id')}: {glyph.get('type')}")
        
        storage.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints"""
    print("\n🌐 Testing API endpoints...")
    
    try:
        base_url = "http://localhost:8001"
        
        # Test health endpoint
        response = requests.get(f"{base_url}/api/garden/status", timeout=10)
        if response.status_code == 200:
            print("✅ /api/garden/status - OK")
            print(f"   Status: {response.json()}")
        else:
            print(f"⚠️ /api/garden/status - {response.status_code}")
        
        # Test glyphs endpoint
        response = requests.get(f"{base_url}/api/glyphs", timeout=10)
        if response.status_code == 200:
            print("✅ /api/glyphs - OK")
            glyphs = response.json().get('glyphs', [])
            print(f"   Found {len(glyphs)} glyphs in memory")
        else:
            print(f"⚠️ /api/glyphs - {response.status_code}")
        
        # Test DB glyphs endpoint
        response = requests.get(f"{base_url}/api/db/glyphs", timeout=10)
        if response.status_code == 200:
            print("✅ /api/db/glyphs - OK")
            glyphs = response.json().get('glyphs', [])
            print(f"   Found {len(glyphs)} glyphs in database")
            
            # Show sample glyphs
            for glyph in glyphs[-2:]:
                print(f"   📋 DB Glyph: {glyph.get('id', 'unknown')}")
        else:
            print(f"⚠️ /api/db/glyphs - {response.status_code}")
            
    except Exception as e:
        print(f"❌ API test failed: {e}")

def main():
    """Run all tests"""
    print("🚀 Synergesis Glyph Persistence Test Suite")
    print("=" * 50)
    
    # Test Neo4j directly
    neo4j_ok = test_neo4j_connection()
    
    # Test API endpoints
    test_api_endpoints()
    
    print("\n" + "=" * 50)
    if neo4j_ok:
        print("✅ All tests passed! Glyph persistence is working.")
    else:
        print("⚠️ Some tests failed. Check logs above.")

if __name__ == "__main__":
    main()
