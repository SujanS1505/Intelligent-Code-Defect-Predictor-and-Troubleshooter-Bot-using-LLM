#include <string>
const std::string& foo(){ std::string s = "hi"; return s; } // BUG: returns ref to local
int main(){ auto& r = foo(); return r.size(); }
