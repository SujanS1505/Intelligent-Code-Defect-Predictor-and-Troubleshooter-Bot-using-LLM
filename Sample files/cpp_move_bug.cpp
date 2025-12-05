#include <string>
#include <iostream>
struct S{
  std::string s;
  S(std::string x): s(std::move(x)){} // fine
  const std::string& get() const { return s; }
};
int main(){
  std::string x = "hello";
  S a(std::move(x));
  std::cout << x << std::endl; // BUG: using moved-from object
}
