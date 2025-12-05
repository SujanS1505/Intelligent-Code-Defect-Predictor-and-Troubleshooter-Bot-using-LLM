#include <stdio.h>
#include <string.h>
int main(){
    char buf[8];
    strcpy(buf, "this string is too long"); // BUG: overflow
    printf("%s\n", buf);
    return 0;
}
