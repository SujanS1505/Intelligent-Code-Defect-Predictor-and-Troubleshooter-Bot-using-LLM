#include <stdio.h>
#include <stdlib.h>
int main(){
    int *p = malloc(sizeof(int));
    *p = 42;
    free(p);
    printf("%d\n", *p); // BUG: use-after-free
    return 0;
}
