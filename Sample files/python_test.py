# python_test.py

def analyze_data(data):
    # Bug 1: IndexError_or_Bounds (Heuristic will catch this pattern)
    if len(data) > 0:
        print(f"First item: {data[0]}")
        # BUG: Accessing an index that is out of bounds for the list [0, 1, 2]
        print(f"Last item: {data[3]}") 

def process_user_input(name):
    user_data = {"age": 25, "city": "NYC"}
    
    # Bug 2: AttributeError/NoneType (Heuristic will catch the .strip() pattern)
    if name is None:
        # BUG: Attempting to call .strip() on a None value
        print(f"User: {name.strip()}")
    else:
        print(f"User: {name}")

# Test calls
analyze_data([10, 20, 30])
process_user_input(None)