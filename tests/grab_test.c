#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc < 2) {
    printf("Usage: %s /dev/input/eventX\n", argv[0]);
    return 1;
  }

  int fd = open(argv[1], O_RDONLY);
  if (fd < 0) {
    perror("open");
    return 1;
  }

  printf("Opening %s (fd=%d)\n", argv[1], fd);
  // EVIOCGRAB
  int ret = ioctl(fd, EVIOCGRAB, 1);
  if (ret < 0) {
    printf("Grab failed: %d (errno=%d %s)\n", ret, errno, strerror(errno));
  } else {
    printf("Grabbed successfully!\n");
    printf("Sleeping 5s...\n");
    sleep(5);
    ioctl(fd, EVIOCGRAB, 0);
  }

  close(fd);
  return 0;
}
