#pragma once

#include <utility>
#include <type_traits>
#include <functional>
#include <memory>
#include <mutex>
#include <atomic>

namespace aegis {

/**
 * @class ScopeGuard
 * @brief RAII guard that executes cleanup on scope exit
 * 
 * Executes a cleanup function when the guard goes out of scope.
 * Useful for resource management and commit/rollback patterns.
 */
template<typename Func>
class ScopeGuard {
public:
    explicit ScopeGuard(Func&& cleanup) : cleanup_(std::forward<Func>(cleanup)), dismissed_(false) {}
    ~ScopeGuard() { if (!dismissed_) cleanup_(); }
    
    ScopeGuard(const ScopeGuard&) = delete;
    ScopeGuard& operator=(const ScopeGuard&) = delete;
    
    ScopeGuard(ScopeGuard&& other) noexcept : cleanup_(std::move(other.cleanup_)), dismissed_(other.dismissed_) {
        other.dismissed_ = true;
    }
    
    void dismiss() { dismissed_ = true; }
    
private:
    Func cleanup_;
    bool dismissed_;
};

/**
 * @brief Create a scope guard from a lambda or function
 */
template<typename Func>
ScopeGuard<Func> make_scope_guard(Func&& func) {
    return ScopeGuard<Func>(std::forward<Func>(func));
}

/**
 * @class SharedResource
 * @brief RAII wrapper for shared resources with reference counting
 */
template<typename T>
class SharedResource {
public:
    explicit SharedResource(T* resource = nullptr) 
        : resource_(resource), ref_count_(new uint32_t(1)) {}
    
    ~SharedResource() { release(); }
    
    SharedResource(const SharedResource& other) 
        : resource_(other.resource_), ref_count_(other.ref_count_) {
        if (ref_count_) ++(*ref_count_);
    }
    
    SharedResource& operator=(const SharedResource& other) {
        if (this != &other) {
            release();
            resource_ = other.resource_;
            ref_count_ = other.ref_count_;
            if (ref_count_) ++(*ref_count_);
        }
        return *this;
    }
    
    SharedResource(SharedResource&& other) noexcept 
        : resource_(other.resource_), ref_count_(other.ref_count_) {
        other.resource_ = nullptr;
        other.ref_count_ = nullptr;
    }
    
    SharedResource& operator=(SharedResource&& other) noexcept {
        if (this != &other) {
            release();
            resource_ = other.resource_;
            ref_count_ = other.ref_count_;
            other.resource_ = nullptr;
            other.ref_count_ = nullptr;
        }
        return *this;
    }
    
    T* get() const { return resource_; }
    T& operator*() const { return *resource_; }
    T* operator->() const { return resource_; }
    
    uint32_t use_count() const { return ref_count_ ? *ref_count_ : 0; }
    
private:
    void release() {
        if (ref_count_) {
            if (--(*ref_count_) == 0) {
                delete resource_;
                delete ref_count_;
            }
        }
    }
    
    T* resource_;
    uint32_t* ref_count_;
};

/**
 * @class LazyInit
 * @brief Thread-safe lazy initialization wrapper
 */
template<typename T>
class LazyInit {
public:
    template<typename... Args>
    T& get(Args&&... args) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!initialized_) {
            resource_ = std::make_unique<T>(std::forward<Args>(args)...);
            initialized_ = true;
        }
        return *resource_;
    }
    
    bool is_initialized() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return initialized_;
    }
    
    void reset() {
        std::lock_guard<std::mutex> lock(mutex_);
        resource_.reset();
        initialized_ = false;
    }
    
private:
    mutable std::mutex mutex_;
    std::unique_ptr<T> resource_;
    bool initialized_ = false;
};

/**
 * @class SpinLock
 * @brief Simple spinlock for low-contention scenarios
 */
class SpinLock {
public:
    SpinLock() = default;
    ~SpinLock() = default;
    
    void lock() {
        while (flag_.test_and_set(std::memory_order_acquire)) {
            // Spin - in production, add yield or backoff
        }
    }
    
    void unlock() {
        flag_.clear(std::memory_order_release);
    }
    
    // C++17 scoped locking
    void lock() const {
        const_cast<SpinLock*>(this)->lock();
    }
    
private:
    mutable std::atomic_flag flag_ = ATOMIC_FLAG_INIT;
};

/**
 * @class ScopedLock
 * @brief RAII scoped lock adapter
 */
template<typename Lock>
class ScopedLock {
public:
    explicit ScopedLock(Lock& lock) : lock_(lock) { lock_.lock(); }
    ~ScopedLock() { lock_.unlock(); }
    
    ScopedLock(const ScopedLock&) = delete;
    ScopedLock& operator=(const ScopedLock&) = delete;
    
private:
    Lock& lock_;
};

} // namespace aegis
