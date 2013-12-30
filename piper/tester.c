#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

#define MAX_RECV_BYTES 16384

int main(int argc, char *argv[])
{
  char buff[MAX_RECV_BYTES];
  FILE *fd = fopen("tmp.txt", "w");

//  setvbuf(stdout, NULL, _IOLBF, 0);
  printf("Tester: starting\n");

  while (1) {
    if (fgets(buff, MAX_RECV_BYTES, stdin)) {
      printf("Tester: received %s\n", buff);
      fwrite(buff, 1, strlen(buff), fd);
      fflush(fd);
      if (strncmp(buff, "exit", 4) == 0)
        break;
    } else {
      break;
    }
  }
  printf("Tester: done\n");
}

