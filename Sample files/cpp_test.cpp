// cpp_test.cpp
#include <iostream>
#include <vector>

void process_vector() {
    std::vector<int> numbers = {10, 20, 30};
    
    // Bug: Out of Bounds Access
    // The vector has indices 0, 1, 2. Accessing index 3 is out of bounds.
    int bad_value = numbers[3]; 

    std::cout << "Value at index 3: " << bad_value << std::endl;
}

int main() {
    process_vector();
    return 0;
}