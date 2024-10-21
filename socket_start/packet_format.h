#ifndef __FORMAT_h__
#define __FORMAT_h__

#define BUFFER_SIZE 1024

typedef struct packet_info{
	int client_id; //unique number for each client
	int rc; //0 is SUCCESS, 1 is FAILURE
	int operation; //RPC operation
	char file_name[256]; //file name
	char buffer[BUFFER_SIZE]; //data appending to the file
} packet_info_t;

typedef enum operation_type{
	CLIENT_INIT,
	LOCK_ACQUIRE,
	LOCK_RELEASE,
	APPEND_FILE,
	CLIENT_CLOSE
} operation_type_t;

#define PACKET_SIZE sizeof(packet_info_t)

#endif
