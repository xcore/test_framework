#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <sys/types.h>
#include <time.h> 

#define MAX_RECV_BYTES 16384

void interrupt_handler(int sig)
{
  printf("Server: finishing\n");
  exit(1);
}

void child_process(int child_to_parent_pipe[2], int parent_to_child_pipe[2])
{
  dup2(child_to_parent_pipe[1], STDOUT_FILENO);
  dup2(child_to_parent_pipe[1], STDERR_FILENO);
  dup2(parent_to_child_pipe[0], STDIN_FILENO);

  close(child_to_parent_pipe[0]);
  close(child_to_parent_pipe[1]);
  close(parent_to_child_pipe[0]);
  close(parent_to_child_pipe[1]);

//  execlp("python", "python", 0);
  execlp("tester", "tester", 0);

//  char buff[MAX_RECV_BYTES];
//  printf("Tester: starting\n");
//  while (1) {
//    if (fgets(buff, MAX_RECV_BYTES, stdin)) {
//      printf("Tester: received %s\n", buff);
//    } else {
//      printf("Tester: done\n");
//      return;
//    }
//  }
}

void parent_process(int child_to_parent_pipe[2], int parent_to_child_pipe[2], int sockfd)
{
  char buff[MAX_RECV_BYTES];
  fd_set readfds;
  int max_fd = child_to_parent_pipe[0];

  if (sockfd > max_fd)
    max_fd = sockfd;

  printf ("server %d %d = %d\n", sockfd, child_to_parent_pipe[0], max_fd);

  close(child_to_parent_pipe[1]);  // close the write end of the pipe in the parent
  close(parent_to_child_pipe[0]);  // close the read end of the pipe in the parent

  while (1) {
    int n = 0;
    int selected = 0;

    FD_ZERO(&readfds);
    FD_SET(sockfd, &readfds);
    FD_SET(child_to_parent_pipe[0], &readfds);

    selected = select(max_fd+1, &readfds, NULL, NULL, NULL);
    if ((selected < 0) && (errno != EINTR)) {
      printf("Server: select error\n");
      fflush(stdout);
    }
    printf("Server: select data\n");

    if (FD_ISSET(child_to_parent_pipe[0], &readfds)) {
      n = read(child_to_parent_pipe[0], buff, sizeof(buff));
      if (n > 0) {
        buff[n] = '\0'; // Ensure null-termination
        printf("Server: child sending %d %s\n", n, buff);
        write(sockfd, buff, strlen(buff)); 
      } else {
        close(sockfd);
        return;
      }
    }

    if (FD_ISSET(sockfd, &readfds)) {
      n = read(sockfd, buff, sizeof(buff));
      if (n > 0) {
        buff[n] = '\0'; // Ensure null termination
        printf("Server: received %s\n", buff);
        write(parent_to_child_pipe[1], buff, strlen(buff)); 
      } else {
        printf("Server: closing socket\n");
        close(sockfd);
        return;
      }
    }
  }
}

int main(int argc, char *argv[])
{
  int listenfd = 0, sockfd = 0;
  struct sockaddr_in serv_addr; 
  char sendBuff[MAX_RECV_BYTES];

  signal(SIGINT, interrupt_handler);

  listenfd = socket(AF_INET, SOCK_STREAM, 0);
  memset(&serv_addr, '0', sizeof(serv_addr));
  memset(sendBuff, '0', sizeof(sendBuff)); 

  serv_addr.sin_family = AF_INET;
  serv_addr.sin_addr.s_addr = htonl(INADDR_ANY);
  serv_addr.sin_port = htons(5000); 

  bind(listenfd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)); 
  listen(listenfd, 10); 

  while(1)
  {
    int child_to_parent_pipe[2];
    int parent_to_child_pipe[2];
    time_t ticks; 

    sockfd = accept(listenfd, (struct sockaddr*)NULL, NULL); 

    printf("Server: accepted\n");
    fflush(stdout);

    // Send connect time
    ticks = time(NULL);
    snprintf(sendBuff, sizeof(sendBuff), "%.24s\n", ctime(&ticks));
    write(sockfd, sendBuff, strlen(sendBuff) + 1); 

    pipe(child_to_parent_pipe);
    pipe(parent_to_child_pipe);

    if (fork() == 0) {
      child_process(child_to_parent_pipe, parent_to_child_pipe);
    } else {
      parent_process(child_to_parent_pipe, parent_to_child_pipe, sockfd);
    }

    printf("Server: closing connection\n");
    close(sockfd);

    close(child_to_parent_pipe[0]);
    close(child_to_parent_pipe[1]);
    close(parent_to_child_pipe[0]);
    close(parent_to_child_pipe[1]);
  }
}

