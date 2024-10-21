#define MAX_FILENAME 256 
#define BUFFERSIZE 1024

/* we will have more status code in the future */
enum status {
    SUCCESS = 0,
    FILE_ERROR = 1
};

/* can further add any fields you want for lock acquire and release */
struct lock_args {
    int client_id;
};


/* add any fields you want */
struct response {
    status status;
};

/* add any fields you want */
struct file_args {
    string filename<MAX_FILENAME>;
    opaque content<BUFFERSIZE>;
    int client_id;
};

program LOCK_PROG {
    version LOCK_VERS {
        int client_init(int) = 1;
        response lock_acquire(lock_args) = 2; 
        response lock_release(lock_args) = 3; 
        response file_append(file_args) = 4;
        int client_close(int) = 5; 
    } = 1;
} = 0x12345678;
