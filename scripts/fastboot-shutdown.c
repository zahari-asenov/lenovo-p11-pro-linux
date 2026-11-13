// SPDX-License-Identifier: GPL-2.0-only
/* One-shot systemd shutdown hook: run only after a requested clean reboot. */
#include <fcntl.h>
#include <linux/reboot.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	char request[10] = {0};
	int fd;
	ssize_t len;

	if (argc != 2 || strcmp(argv[1], "reboot"))
		return 0;
	fd = open("/run/j706f-fastboot-once", O_RDONLY | O_NOFOLLOW);
	if (fd < 0)
		return 0;
	len = read(fd, request, sizeof(request));
	close(fd);
	if (len != 10 || memcmp(request, "bootloader", 10))
		return 0;
	unlink("/run/j706f-fastboot-once");
	sync();
	fprintf(stderr, "J706F: clean shutdown hook requesting bootloader\n");
	syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
		LINUX_REBOOT_CMD_RESTART2, "bootloader");
	perror("J706F reboot bootloader");
	return 1;
}
