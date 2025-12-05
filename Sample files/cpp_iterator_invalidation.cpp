#include <vector>
#include <iostream>
int main(){
    std::vector<int> v = {1,2,3,4};
    for(auto it = v.begin(); it != v.end(); ++it){
        if(*it == 2) v.erase(it); // BUG: invalidates iterator then ++it
        std::cout << *it << std::endl;
    }
}
