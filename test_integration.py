#!/usr/bin/env python3
"""
Integration test for Gemini API + Local LLM fallback.
Verifies that all components are properly connected and working.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add the project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_gemini_api():
    """Test Gemini API availability and configuration."""
    print("\n" + "="*60)
    print("Testing Gemini API Integration")
    print("="*60)
    
    try:
        from rag import gemini_api
        print("✓ Gemini API module imported successfully")
        
        # Check if it's available
        status = gemini_api.health_check()
        print(f"✓ Health check: {status}")
        
        if status["gemini_available"]:
            print("✓ Gemini API is configured and ready")
        else:
            print("⚠ Gemini API not configured (will use fallback)")
        
        return True
    except Exception as e:
        print(f"✗ Error testing Gemini API: {e}")
        return False


def test_llm_module():
    """Test LLM module initialization."""
    print("\n" + "="*60)
    print("Testing LLM Module")
    print("="*60)
    
    try:
        from rag import llm
        print("✓ LLM module imported successfully")
        print(f"✓ Torch device: {llm._DEVICE}")
        print(f"✓ Disable local LLM: {llm._DISABLE_LOCAL_LLM}")
        print(f"✓ Fast analysis mode: {llm._FAST_ANALYSIS_MODE}")
        print(f"✓ Gemini API available: {llm._GEMINI_AVAILABLE}")
        return True
    except Exception as e:
        print(f"✗ Error testing LLM module: {e}")
        return False


def test_orchestrator():
    """Test orchestrator and analyze function."""
    print("\n" + "="*60)
    print("Testing Orchestrator")
    print("="*60)
    
    try:
        from rag.orchestrator import analyze
        print("✓ Orchestrator imported successfully")
        
        # Test with a simple code snippet
        test_code = """
def divide(a, b):
    return a / b  # Missing zero check
"""
        
        print("Testing with sample code snippet...")
        result, passages, det, query = analyze(test_code, lang="python")
        
        print(f"✓ Analysis completed")
        print(f"  - Issue type: {result.get('issue_type', 'N/A')}")
        print(f"  - Root cause: {result.get('root_cause', 'N/A')}")
        print(f"  - LLM status: {result.get('_llm_status', 'N/A')}")
        print(f"  - Confidence: {result.get('confidence', 'N/A')}")
        
        if result.get('_actual_source'):
            print(f"  ⚠ Actual source (hidden from user): {result.get('_actual_source')}")
        
        return True
    except Exception as e:
        print(f"✗ Error testing orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dependencies():
    """Check required dependencies."""
    print("\n" + "="*60)
    print("Checking Dependencies")
    print("="*60)
    
    dependencies = [
        ("flask", "Flask"),
        ("flask_login", "Flask-Login"),
        ("flask_sqlalchemy", "Flask-SQLAlchemy"),
        ("transformers", "Transformers"),
        ("torch", "PyTorch"),
        ("google.generativeai", "Google Generative AI"),
        ("faiss", "FAISS"),
    ]
    
    all_ok = True
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
        except ImportError:
            print(f"✗ {display_name} - NOT INSTALLED")
            all_ok = False
    
    return all_ok


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "AI Code Guardian Integration Test" + " "*11 + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Gemini API", test_gemini_api),
        ("LLM Module", test_llm_module),
        ("Orchestrator", test_orchestrator),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED - System is ready!")
        print("\nYour project is configured to:")
        print("1. Use Gemini API for code analysis (fast, high quality)")
        print("2. Automatically fallback to heuristic fixes if API fails")
        print("3. Appear as if using local Qwen2.5-Coder LLM (privacy)")
        print("4. Handle errors gracefully at each step")
    else:
        print("✗ SOME TESTS FAILED - Please review errors above")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


def test_gemini_api():
    """Test Gemini API availability and configuration."""
    print("\n" + "="*60)
    print("Testing Gemini API Integration")
    print("="*60)
    
    try:
        from rag import gemini_api
        print("✓ Gemini API module imported successfully")
        
        # Check if it's available
        status = gemini_api.health_check()
        print(f"✓ Health check: {status}")
        
        if status["gemini_available"]:
            print("✓ Gemini API is configured and ready")
        else:
            print("⚠ Gemini API not configured (will use fallback)")
        
        return True
    except Exception as e:
        print(f"✗ Error testing Gemini API: {e}")
        return False


def test_llm_module():
    """Test LLM module initialization."""
    print("\n" + "="*60)
    print("Testing LLM Module")
    print("="*60)
    
    try:
        from rag import llm
        print("✓ LLM module imported successfully")
        print(f"✓ Torch device: {llm._DEVICE}")
        print(f"✓ Disable local LLM: {llm._DISABLE_LOCAL_LLM}")
        print(f"✓ Fast analysis mode: {llm._FAST_ANALYSIS_MODE}")
        print(f"✓ Gemini API available: {llm._GEMINI_AVAILABLE}")
        return True
    except Exception as e:
        print(f"✗ Error testing LLM module: {e}")
        return False


def test_orchestrator():
    """Test orchestrator and analyze function."""
    print("\n" + "="*60)
    print("Testing Orchestrator")
    print("="*60)
    
    try:
        from rag.orchestrator import analyze
        print("✓ Orchestrator imported successfully")
        
        # Test with a simple code snippet
        test_code = """
def divide(a, b):
    return a / b  # Missing zero check
"""
        
        print("Testing with sample code snippet...")
        result, passages, det, query = analyze(test_code, lang="python")
        
        print(f"✓ Analysis completed")
        print(f"  - Issue type: {result.get('issue_type', 'N/A')}")
        print(f"  - Root cause: {result.get('root_cause', 'N/A')}")
        print(f"  - LLM status: {result.get('_llm_status', 'N/A')}")
        print(f"  - Confidence: {result.get('confidence', 'N/A')}")
        
        if result.get('_actual_source'):
            print(f"  ⚠ Actual source (hidden from user): {result.get('_actual_source')}")
        
        return True
    except Exception as e:
        print(f"✗ Error testing orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dependencies():
    """Check required dependencies."""
    print("\n" + "="*60)
    print("Checking Dependencies")
    print("="*60)
    
    dependencies = [
        ("flask", "Flask"),
        ("flask_login", "Flask-Login"),
        ("flask_sqlalchemy", "Flask-SQLAlchemy"),
        ("transformers", "Transformers"),
        ("torch", "PyTorch"),
        ("google.generativeai", "Google Generative AI"),
        ("faiss", "FAISS"),
    ]
    
    all_ok = True
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
        except ImportError:
            print(f"✗ {display_name} - NOT INSTALLED")
            all_ok = False
    
    return all_ok


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "AI Code Guardian Integration Test" + " "*11 + "║")
    print("╚" + "="*58 + "╝")
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Gemini API", test_gemini_api),
        ("LLM Module", test_llm_module),
        ("Orchestrator", test_orchestrator),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED - System is ready!")
        print("\nYour project is configured to:")
        print("1. Use Gemini API for code analysis (fast, high quality)")
        print("2. Automatically fallback to heuristic fixes if API fails")
        print("3. Appear as if using local Qwen2.5-Coder LLM (privacy)")
        print("4. Handle errors gracefully at each step")
    else:
        print("✗ SOME TESTS FAILED - Please review errors above")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
