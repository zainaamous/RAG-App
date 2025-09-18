#!/usr/bin/env python3
"""
Test script for debugging file upload issues on port 8090
"""
import requests
import tempfile
import os
import sys
from pathlib import Path

def test_health_endpoint():
    """Test the health endpoint"""
    try:
        response = requests.get("http://localhost:8090/api/health", timeout=10)
        print(f"Health check status: {response.status_code}")
        print(f"Health response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_file_upload():
    """Test file upload with a simple text file"""
    try:
        # Create a test file
        test_content = "This is a test document for upload testing.\nIt has multiple lines.\nTesting file upload functionality."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file_path = f.name
        
        try:
            # Test upload
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                response = requests.post("http://localhost:8090/api/ingest/file", files=files, timeout=30)
            
            print(f"Upload status: {response.status_code}")
            if response.status_code == 200:
                print(f"Upload successful: {response.json()}")
                return True
            else:
                print(f"Upload failed: {response.text}")
                return False
                
        finally:
            # Clean up test file
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
    except Exception as e:
        print(f"Upload test failed: {e}")
        return False

def test_csv_upload():
    """Test CSV file upload specifically"""
    try:
        # Create a test CSV file
        test_csv_content = "name,age,city\nJohn,25,New York\nJane,30,London\nBob,35,Paris"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(test_csv_content)
            temp_file_path = f.name
        
        try:
            # Test upload
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('test.csv', f, 'text/csv')}
                response = requests.post("http://localhost:8090/api/ingest/file", files=files, timeout=30)
            
            print(f"CSV Upload status: {response.status_code}")
            if response.status_code == 200:
                print(f"CSV Upload successful: {response.json()}")
                return True
            else:
                print(f"CSV Upload failed: {response.text}")
                return False
                
        finally:
            # Clean up test file
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
    except Exception as e:
        print(f"CSV Upload test failed: {e}")
        return False

def main():
    print("🔍 Testing Dashboard Server on Port 8090")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    health_ok = test_health_endpoint()
    
    if not health_ok:
        print("❌ Health check failed. Server may not be running or accessible.")
        print("Make sure the dashboard server is running on port 8090")
        return
    
    # Test 2: Text file upload
    print("\n2. Testing text file upload...")
    text_upload_ok = test_file_upload()
    
    # Test 3: CSV file upload
    print("\n3. Testing CSV file upload...")
    csv_upload_ok = test_csv_upload()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"Health Check: {'✅' if health_ok else '❌'}")
    print(f"Text Upload: {'✅' if text_upload_ok else '❌'}")
    print(f"CSV Upload: {'✅' if csv_upload_ok else '❌'}")
    
    if health_ok and text_upload_ok and csv_upload_ok:
        print("\n🎉 All tests passed! File upload is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()
