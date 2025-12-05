#include <stdio.h>
int main(){
    int i = -1;
    unsigned int u = 1;
    if (i < u) { // BUG: signed/unsigned comparison surprise
        printf("i < u\n");
    } else {
        printf("i >= u\n");
    }
    return 0;
}
