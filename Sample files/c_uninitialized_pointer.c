#include <stdio.h>
int main(){
    int *p; // BUG: uninitialized pointer
    *p = 5; // undefined behavior
    printf("%d\n", *p);
    return 0;
}
