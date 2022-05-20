CC = gcc
CFLAGS = -Wall
INSTALL = `which install`

mcp3008: mcp3008.c
	$(CC) $(CFLAGS) mcp3008.c -o mcp3008

install: mcp3008
	$(INSTALL) ./mcp3008 /usr/local/bin/mcp3008

clean:
	rm -f mcp3008
