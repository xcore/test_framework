#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <netdb.h>
#include <unistd.h>
#include <errno.h>
#include <arpa/inet.h>

#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <ctype.h>

#define MAX_RECV_BYTES 16384
#define MAX_NUM_CONNECT_RETRIES 20

void print_and_exit(const char* format, ...)
{
  va_list argptr;
  va_start(argptr, format);
  vfprintf(stderr, format, argptr);
  va_end(argptr);
  exit(1);
}

void interrupt_handler(int sig)
{
  printf("\nClient: finishing\n");
  exit(1);
}

int connect_to_server(char *ip_addr_str, char *port_str)
{
  int sockfd = 0;
  int n = 0;
  struct sockaddr_in serv_addr;
  char *end_pointer = NULL;
  int port = 0;
  int connect_retries = 0;

  signal(SIGINT, interrupt_handler);

  // Need the fflush because there is no newline in the print
  printf("Client: connecting"); fflush(stdout);
  while (1) {
    if ((sockfd = socket(AF_INET, SOCK_STREAM, 0)) < 0)
      print_and_exit("ERROR: Could not create socket\n");

    memset(&serv_addr, 0, sizeof(serv_addr));

    // Parse the port parameter
    end_pointer = (char*)port_str;
    port = strtol(port_str, &end_pointer, 10);
    if (end_pointer == port_str)
      print_and_exit("ERROR: Failed to parse port\n");

    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);

    if (inet_pton(AF_INET, ip_addr_str, &serv_addr.sin_addr) <= 0)
      print_and_exit("ERROR: inet_pton error occured\n");

    if (connect(sockfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
      close(sockfd);

      if (connect_retries < MAX_NUM_CONNECT_RETRIES) {
        // Need the fflush because there is no newline in the print
        printf("."); fflush(stdout);
        sleep(1);
        connect_retries++;
      } else {
        print_and_exit("\nERROR: Connect failed\n");
      }
    } else {
      break;
    }
  }

  printf(" - connected\n");
  return sockfd;
}

void handle_socket(int sockfd)
{
  char buff[MAX_RECV_BYTES];
  int n = 0;
  fd_set readfds;
  int max_fd = fileno(stdin);

  if (sockfd > max_fd)
    max_fd = sockfd;

  while (1) {
    int selected = 0;

    FD_ZERO(&readfds);
    FD_SET(sockfd, &readfds);
    FD_SET(fileno(stdin), &readfds);
    
    selected = select(max_fd+1, &readfds, NULL, NULL, NULL);
    if ((selected < 0) && (errno != EINTR)) {
      printf("Client: select error\n");
      fflush(stdout);
    }

    if (FD_ISSET(sockfd, &readfds)) {
      if ((n = read(sockfd, buff, sizeof(buff))) > 0) {
        buff[n] = '\0'; // Ensure null termination
        printf("Client: received %s\n", buff);
      }
    }

    if (FD_ISSET(fileno(stdin), &readfds)) {
      int size = sizeof(buff);
      if (fgets(buff, size, stdin) == NULL) {
        printf("Client: nothing from fgets\n");
      } else {
        printf("Client: sending: %s\n", buff);
        write(sockfd, buff, strlen(buff));
      }
    }
  }
}

int main(int argc, char *argv[])
{
  int sockfd = connect_to_server("127.0.0.1", "5000");
  handle_socket(sockfd);
  return 0;
}
