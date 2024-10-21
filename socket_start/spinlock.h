#ifndef __SPINLOCK_h__
#define __SPINLOCK_h__

typedef struct spinlock {
    int lock_flag;
} spinlock_t;

int spinlock_init(spinlock_t *lock) {
    lock->lock_flag = 0;
    return 0;
}

void spinlock_acquire(spinlock_t *lock) {
    while(!__sync_bool_compare_and_swap(&lock->lock_flag, 0, 1));
    return;
}
void spinlock_release(spinlock_t *lock) {
    __sync_bool_compare_and_swap(&lock->lock_flag, 1, 0);
    return;
}

#endif
