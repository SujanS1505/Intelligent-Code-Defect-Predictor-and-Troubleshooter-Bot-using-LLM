#include <iostream>
using namespace std;
void leak() {
    int* arr = new int[100];
    arr[0] = 42;
} // no delete[] → memory leak
int main() { leak(); }
