BIN = cfggen

# Flags
CFLAGS += -Wall -std=c99 -g -Og

SRC = $(wildcard *.c)
OBJ = $(SRC:.c=.o)
LIBS = -lm

ifeq ($(OS),Windows_NT)
	BIN := $(BIN).exe
endif

all: $(BIN)

$(OBJ): %.o: %.c
	$(CC) -c $(CFLAGS) $^ -o $@

$(BIN): $(OBJ)
	@mkdir -p bin
	rm -f bin/$(BIN)
	$(CC) $(OBJ) $(CFLAGS) -o bin/$(BIN) $(LIBS)

clean:
	rm -f bin/$(BIN) $(OBJ)
