#include <errno.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h> 
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/types.h>

#define MAX_RECV_BYTES 16384

int g_sockfd = 0;

void interrupt_handler(int sig)
{
  printf("Server: finishing\n");
  close(g_sockfd);
  exit(0);
}

void print_and_exit(const char* format, ...)
{
  va_list argptr;
  va_start(argptr, format);
  vfprintf(stderr, format, argptr);
  va_end(argptr);
  exit(1);
}

/*
 * Tokenize a command string.
 * The caller must free the returned arguments pointer.
 */
char **tokenize(char *str, const char *const tokens)
{
  char **args = NULL;
  char *p = strtok(str, tokens);
  int n_spaces = 0;

  // Split the command string into tokens
  while (p) {
    args = realloc(args, sizeof(char*) * ++n_spaces);
    args[n_spaces-1] = p;
    p = strtok(NULL, tokens);
  }

  // realloc one extra element for the last NULL
  args = realloc(args, sizeof(char*) * (n_spaces+1));
  args[n_spaces] = 0;

  return args;
}

void child_process(int stdin_pipe[2], int stdout_pipe[2], int stderr_pipe[2], char *cmd_str)
{
  char **args = tokenize(cmd_str, " \n");

  // Map stdin/stdout/stderr to pipes
  dup2(stdin_pipe[0], 0);
  dup2(stdout_pipe[1], 1);
  dup2(stderr_pipe[1], 2);

  // Close all unused file descriptors
  close(stdout_pipe[0]);
  close(stdout_pipe[1]);
  close(stderr_pipe[0]);
  close(stderr_pipe[1]);
  close(stdin_pipe[0]);
  close(stdin_pipe[1]);

  // Call binary and ensure that stdout is put into line-bufferd mode
  char *const envs[] = {"DYLD_INSERT_LIBRARIES=/Users/peter/lib/line-buffer.so", NULL};
  execve(args[0], args, envs);

  free(args);
}

void parent_process(int stdin_pipe[2], int stdout_pipe[2], int stderr_pipe[2], int sockfd)
{
  int stdout_closed = 0;
  int stderr_closed = 0;
  char buff[MAX_RECV_BYTES];
  fd_set readfds;
  int max_fd = stdout_pipe[0];

  if (stderr_pipe[0] > max_fd)
    max_fd = stderr_pipe[0];
  if (sockfd > max_fd)
    max_fd = sockfd;

  close(stdin_pipe[0]);  // close the read end of the pipe
  close(stdout_pipe[1]);  // close the write end of the pipe
  close(stderr_pipe[1]);  // close the write end of the pipe

  while (1) {
    int n = 0;
    int selected = 0;

    FD_ZERO(&readfds);
    FD_SET(sockfd, &readfds);
    FD_SET(stdout_pipe[0], &readfds);
    FD_SET(stderr_pipe[0], &readfds);

    selected = select(max_fd+1, &readfds, NULL, NULL, NULL);
    if ((selected < 0) && (errno != EINTR)) {
      print_and_exit("ERRO: select error\n");
      fflush(stdout);
    }
    printf("Server: select data\n");

    if (FD_ISSET(stdout_pipe[0], &readfds)) {
      n = read(stdout_pipe[0], buff, sizeof(buff));
      if (n > 0) {
        buff[n] = '\0'; // Ensure null-termination
        printf("Server: stdout: %d %s\n", n, buff);
        write(sockfd, buff, strlen(buff)); 
      } else {
        printf("Server: stdout closed\n");
        stdout_closed = 1;
        if (stderr_closed) {
          close(sockfd);
          return;
        }
      }
    }

    if (FD_ISSET(stderr_pipe[0], &readfds)) {
      n = read(stderr_pipe[0], buff, sizeof(buff));
      if (n > 0) {
        buff[n] = '\0'; // Ensure null-termination
        printf("Server: stderr: %d %s\n", n, buff);
        write(sockfd, buff, strlen(buff)); 
      } else {
        printf("Server: stderr closed\n");
        stderr_closed = 1;
        if (stdout_closed) {
          close(sockfd);
          return;
        }
      }
    }

    if (FD_ISSET(sockfd, &readfds)) {
      n = read(sockfd, buff, sizeof(buff));
      if (n > 0) {
        buff[n] = '\0'; // Ensure null termination
        printf("Server: received %s\n", buff);
        write(stdin_pipe[1], buff, strlen(buff)); 
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
  struct sockaddr_in serv_addr; 
  char sendBuff[MAX_RECV_BYTES];
  int listenfd = 0;

  signal(SIGINT, interrupt_handler);
  setvbuf(stdout, NULL, _IOLBF, 0);

  listenfd = socket(AF_INET, SOCK_STREAM, 0);
  memset(&serv_addr, '0', sizeof(serv_addr));
  memset(sendBuff, '0', sizeof(sendBuff)); 

  serv_addr.sin_family = AF_INET;
  serv_addr.sin_addr.s_addr = htonl(INADDR_ANY);
  serv_addr.sin_port = htons(5000); 

  int yes=1;
  if (setsockopt(listenfd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) == -1)
    print_and_exit("ERROR: setsockopt");

  if (bind(listenfd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) == -1)
    print_and_exit("ERROR: bind failed\n"); 

  if (listen(listenfd, 10) == -1)
    print_and_exit("ERROR: listen failed\n"); 

  while(1) {
    int stdout_pipe[2];
    int stderr_pipe[2];
    int stdin_pipe[2];
    time_t ticks; 
    char cmd_buff[MAX_RECV_BYTES];
    int n = 0;

    printf("Server: waiting for connection\n");
    g_sockfd = accept(listenfd, (struct sockaddr*)NULL, NULL); 

    if (g_sockfd == -1) {
      printf("Server: accept failed\n");
      continue;
    }

    printf("Server: accepted\n");
    fflush(stdout);

    // Send connect time
    ticks = time(NULL);
    snprintf(sendBuff, sizeof(sendBuff), "%.24s\n", ctime(&ticks));
    write(g_sockfd, sendBuff, strlen(sendBuff) + 1); 

    // Receive command to run
    n = read(g_sockfd, cmd_buff, sizeof(cmd_buff));

    pipe(stdout_pipe);
    pipe(stderr_pipe);
    pipe(stdin_pipe);

    pid_t pid = fork();
    if (pid == 0) {
      child_process(stdin_pipe, stdout_pipe, stderr_pipe, cmd_buff);
    } else {
      int status = 0;
      parent_process(stdin_pipe, stdout_pipe, stderr_pipe, g_sockfd);
      
      // The connection to the client is closed, so kill the child if
      // it is still active
      printf("Server: waiting for child\n");
      if (waitpid(pid, &status, WNOHANG) == 0) {
        printf("Server: send SIGTERM\n");
        kill(pid, SIGTERM);

        // Allow child time to die
        sleep(1);

        if (waitpid(pid, &status, WNOHANG) == 0) {
          printf("Server: send SIGKILL\n");
          // the child process is still active
          kill(pid, SIGKILL);
        }
      } else {
        printf("Server: child ended\n");
      }
      wait(&status);
    }
    printf("Server: done\n");
    g_sockfd = 0;
  }
}

