#include <iostream>
using namespace std;
int main() {
    int nums[3] = {1,2,3};
    for (int i=0; i<=3; i++) cout << nums[i] << endl; // <= causes OOB
}
