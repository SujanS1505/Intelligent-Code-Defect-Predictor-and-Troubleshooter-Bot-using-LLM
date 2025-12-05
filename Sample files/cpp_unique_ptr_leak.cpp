#include <memory>
int main(){
    std::unique_ptr<int> p(new int(5));
    int* raw = p.release(); // BUG: released without delete -> leak
    (void)raw;
}
