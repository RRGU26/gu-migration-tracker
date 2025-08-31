#!/usr/bin/env python3
"""
Debug OpenSea API issues
"""
import asyncio
import aiohttp
import json
import sys
sys.path.append('src')

from config.config import Config

async def test_raw_api_call():
    """Test raw API call to see exactly what's happening"""
    print("Testing raw OpenSea API call...")
    print(f"API Key: {Config.OPENSEA_API_KEY[:10]}...{Config.OPENSEA_API_KEY[-4:]}")
    
    url = f"{Config.OPENSEA_BASE_URL}/collections/gu-origins/stats"
    
    headers = {
        'X-API-KEY': Config.OPENSEA_API_KEY,
        'User-Agent': 'GU-Migration-Tracker/1.0',
        'Accept': 'application/json'
    }
    
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=timeout) as response:
                print(f"Status Code: {response.status}")
                print(f"Response Headers: {dict(response.headers)}")
                
                response_text = await response.text()
                print(f"Response Body: {response_text[:500]}...")  # First 500 chars
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        print("JSON parsing successful")
                        print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                        return data
                    except json.JSONDecodeError as e:
                        print(f"JSON parsing failed: {e}")
                        return None
                else:
                    print(f"API returned error status: {response.status}")
                    return None
                    
    except Exception as e:
        print(f"Request failed: {e}")
        return None

async def test_collection_endpoints():
    """Test different collection endpoints"""
    endpoints_to_test = [
        f"{Config.OPENSEA_BASE_URL}/collections/gu-origins",
        f"{Config.OPENSEA_BASE_URL}/collections/gu-origins/stats", 
        f"{Config.OPENSEA_BASE_URL}/collections/genuine-undead",
        f"{Config.OPENSEA_BASE_URL}/collections/genuine-undead/stats"
    ]
    
    headers = {
        'X-API-KEY': Config.OPENSEA_API_KEY,
        'User-Agent': 'GU-Migration-Tracker/1.0',
        'Accept': 'application/json'
    }
    
    for endpoint in endpoints_to_test:
        print(f"\nTesting: {endpoint}")
        
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=headers, timeout=timeout) as response:
                    print(f"  Status: {response.status}")
                    
                    if response.status == 200:
                        text = await response.text()
                        try:
                            data = json.loads(text)
                            if isinstance(data, dict):
                                print(f"  Success! Keys: {list(data.keys())}")
                            else:
                                print(f"  Success! Type: {type(data)}")
                        except:
                            print(f"  Response length: {len(text)} chars")
                    else:
                        error_text = await response.text()
                        print(f"  Error: {error_text[:200]}")
                        
        except Exception as e:
            print(f"  Failed: {e}")
        
        # Wait between requests
        await asyncio.sleep(2)

async def main():
    print("OpenSea API Debug Test")
    print("=" * 40)
    
    # Test basic connectivity
    result = await test_raw_api_call()
    
    print(f"\n{'='*40}")
    print("Testing multiple endpoints...")
    await test_collection_endpoints()

if __name__ == '__main__':
    asyncio.run(main())